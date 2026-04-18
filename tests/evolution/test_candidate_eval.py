from pathlib import Path

from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.evolution.engine import EvolutionEngine
from contract_evidence_os.runtime.service import RuntimeService


def test_evaluation_harness_computes_core_metrics(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text(
        "Audit history must never be deleted.\nEvery important summary must cite evidence.\n",
        encoding="utf-8",
    )

    service = RuntimeService(storage_root=tmp_path / "runtime")
    result = service.run_task(
        goal="Read the attachment and summarize the mandatory constraints with evidence.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )

    engine = EvolutionEngine()
    candidate = engine.propose_candidate(
        candidate_type="skill_capsule",
        source_traces=[event.event_id for event in result.audit_events],
        target_component="memory.procedural",
        hypothesis="Promote verified retrieval traces into a reusable capsule.",
    )
    evaluation = engine.evaluate_candidate(candidate.candidate_id, regression_failures=0, gain=0.2)
    canary = engine.run_canary(candidate.candidate_id, success_rate=1.0, anomaly_count=0)

    metrics = EvaluationHarness().compute_metrics(
        task_runs=[result],
        evaluations=[evaluation],
        canaries=[canary],
        incidents=[],
    )

    assert metrics["task_completion_rate"] == 1.0
    assert metrics["evidence_coverage_rate"] == 1.0
    assert metrics["shadow_verification_score"] == 1.0
    assert metrics["evolution_gain_rate"] > 0
