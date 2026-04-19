from contract_evidence_os.agents.registry import default_passports
from contract_evidence_os.evolution.engine import EvolutionEngine
from contract_evidence_os.policy.lattice import PermissionLattice


def test_destructive_action_remains_blocked_without_explicit_approval() -> None:
    lattice = PermissionLattice()
    researcher = default_passports()["Researcher"]

    outcome = lattice.authorize(
        passport=researcher,
        action="destructive_action",
        tool_name="file_retrieval",
        risk_level="high",
    )

    assert outcome.allowed is False
    assert outcome.approval_required is True


def test_failed_canary_rolls_back_candidate() -> None:
    engine = EvolutionEngine()
    candidate = engine.propose_candidate(
        candidate_type="skill_capsule",
        source_traces=["audit-001"],
        target_component="memory.procedural",
        hypothesis="Unsafe candidate should not promote.",
    )
    engine.evaluate_candidate(candidate.candidate_id, regression_failures=0, gain=0.1)
    engine.run_canary(candidate.candidate_id, success_rate=0.6, anomaly_count=2)

    promoted = engine.promote_candidate(candidate.candidate_id)

    assert promoted.promotion_result == "rolled_back"
