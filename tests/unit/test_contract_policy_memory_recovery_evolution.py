from pathlib import Path

from contract_evidence_os.agents.registry import default_passports
from contract_evidence_os.contracts.compiler import ContractCompiler
from contract_evidence_os.evolution.engine import EvolutionEngine
from contract_evidence_os.memory.matrix import MemoryMatrix
from contract_evidence_os.policy.lattice import PermissionLattice
from contract_evidence_os.recovery.engine import RecoveryEngine
from contract_evidence_os.verification.shadow import ShadowVerifier


def test_contract_compiler_extracts_constraints_and_evidence_requirements(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text(
        "Never delete audit history.\nEvery summary must cite source evidence.\n",
        encoding="utf-8",
    )

    compiler = ContractCompiler()
    contract = compiler.compile(
        goal="Read the attachment and summarize the mandatory constraints.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["do not delete audit history"],
    )

    assert "structured_summary" in contract.deliverables
    assert "delete audit history" in " ".join(contract.forbidden_actions).lower()
    assert any("source" in item.lower() for item in contract.evidence_requirements)
    assert contract.risk_level in {"low", "moderate"}


def test_permission_lattice_denies_out_of_scope_high_risk_action() -> None:
    researcher = default_passports()["Researcher"]
    lattice = PermissionLattice()

    allowed = lattice.authorize(
        passport=researcher,
        action="read",
        tool_name="file_retrieval",
        risk_level="low",
    )
    denied = lattice.authorize(
        passport=researcher,
        action="destructive_action",
        tool_name="shell_patch",
        risk_level="high",
    )

    assert allowed.allowed is True
    assert denied.allowed is False
    assert denied.reason


def test_shadow_verifier_blocks_when_required_evidence_is_missing() -> None:
    compiler = ContractCompiler()
    contract = compiler.compile(
        goal="Summarize the task safely.",
        attachments=[],
        preferences={},
        prohibitions=[],
    )

    report = ShadowVerifier().verify(contract=contract, evidence_graph=None, delivery_claims=[])

    assert report.status == "blocked"
    assert report.findings


def test_memory_matrix_promotes_validated_records() -> None:
    matrix = MemoryMatrix()

    memory = matrix.write(
        memory_type="episodic",
        summary="Retrieved a file and extracted grounded constraints.",
        content={"pattern": "file_retrieval_then_extract"},
        sources=["audit-001"],
    )
    matrix.validate(memory.memory_id)
    promotion = matrix.promote(memory.memory_id)

    promoted = matrix.get(memory.memory_id)

    assert promoted is not None
    assert promoted.state == "promoted"
    assert promotion.new_state == "promoted"


def test_recovery_engine_restores_checkpoint_state() -> None:
    engine = RecoveryEngine()
    checkpoint = engine.save_checkpoint(
        task_id="task-001",
        plan_node_id="node-001",
        state={"phase": "executing", "attempt": 1},
    )

    restored = engine.restore_checkpoint(checkpoint.checkpoint_id)

    assert restored == {"phase": "executing", "attempt": 1}


def test_evolution_engine_evaluates_and_promotes_safe_candidate() -> None:
    engine = EvolutionEngine()
    candidate = engine.propose_candidate(
        candidate_type="skill_capsule",
        source_traces=["audit-001", "audit-002"],
        target_component="memory.procedural",
        hypothesis="Promote repeated verified retrieval traces into a reusable capsule.",
    )

    evaluation = engine.evaluate_candidate(candidate.candidate_id, regression_failures=0, gain=0.15)
    canary = engine.run_canary(candidate.candidate_id, success_rate=1.0, anomaly_count=0)
    promoted = engine.promote_candidate(candidate.candidate_id)

    assert evaluation.status == "passed"
    assert canary.status == "promoted"
    assert promoted.promotion_result == "promoted"
