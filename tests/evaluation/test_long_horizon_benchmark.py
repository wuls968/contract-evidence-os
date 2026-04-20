from pathlib import Path

from contract_evidence_os.evals.dataset import LongHorizonTaskCase, LongHorizonTaskDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.evals.models import StrategyEvaluationReport
from contract_evidence_os.evolution.engine import EvolutionEngine
from contract_evidence_os.runtime.service import RuntimeService


def _factory(strategy_name: str):
    def _build(root: Path) -> RuntimeService:
        return RuntimeService(storage_root=root, routing_strategy=strategy_name)

    return _build


def test_long_horizon_evals_compare_strategies_and_gate_continuity_candidates(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text(
        "\n".join(
            [
                "Audit history must never be deleted.",
                "Every important summary must cite evidence.",
                "Destructive actions require explicit approval.",
            ]
        ),
        encoding="utf-8",
    )
    dataset = LongHorizonTaskDataset(
        cases=[
            LongHorizonTaskCase(
                case_id="lh-001",
                goal="Read the attachment and summarize the mandatory constraints with evidence before publication.",
                attachments=[str(attachment)],
                preferences={"output_style": "structured"},
                prohibitions=["Do not delete audit history."],
                expected_facts=[
                    "Audit history must never be deleted.",
                    "Every important summary must cite evidence.",
                    "Destructive actions require explicit approval.",
                ],
                session_interrupts=["planned", "after_node_execute"],
                require_approval=True,
                min_evidence_ref_count=3,
            )
        ]
    )

    reports = EvaluationHarness().compare_long_horizon_strategies(
        dataset=dataset,
        runtime_factories={"quality": _factory("quality"), "economy": _factory("economy")},
        working_root=tmp_path / "benchmarks",
    )

    assert set(reports) == {"quality", "economy"}
    for report in reports.values():
        assert report.metrics["resumed_task_completion_rate"] == 1.0
        assert report.metrics["handoff_quality"] > 0.0
        assert report.metrics["continuity_reconstruction_accuracy"] > 0.0
        assert report.metrics["open_question_resolution_rate"] > 0.0

    engine = EvolutionEngine()
    promoted_candidate = engine.propose_candidate(
        candidate_type="routing_rule",
        source_traces=["trace-001"],
        target_component="continuity.handoff",
        hypothesis="Rank approval-bound next actions ahead of fresh retrieval work after resume.",
    )
    passed = engine.evaluate_candidate(promoted_candidate.candidate_id, report=reports["quality"])
    assert passed.status == "passed"

    rejected_candidate = engine.propose_candidate(
        candidate_type="prompt_profile",
        source_traces=["trace-002"],
        target_component="continuity.compaction",
        hypothesis="Aggressively compress contradictions even if they disappear from the hot context.",
    )
    weak_report = StrategyEvaluationReport(
        strategy_name="weak",
        metrics={
            "factual_correctness_rate": 0.9,
            "policy_violation_rate": 0.0,
            "evidence_coverage_rate": 1.0,
            "resumed_task_completion_rate": 0.0,
            "handoff_quality": 0.2,
            "continuity_reconstruction_accuracy": 0.2,
            "open_question_resolution_rate": 0.0,
        },
    )
    failed = engine.evaluate_candidate(rejected_candidate.candidate_id, report=weak_report)
    assert failed.status == "failed"
