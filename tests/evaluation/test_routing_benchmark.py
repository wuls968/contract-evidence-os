from pathlib import Path

from contract_evidence_os.evals.dataset import GoldenTaskCase, GoldenTaskDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.evolution.engine import EvolutionEngine
from contract_evidence_os.runtime.service import RuntimeService


def test_eval_harness_compares_two_routing_strategies_and_gates_candidates(tmp_path: Path) -> None:
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

    dataset = GoldenTaskDataset(
        cases=[
            GoldenTaskCase(
                case_id="golden-001",
                goal="Read the attachment and summarize the mandatory constraints with evidence.",
                attachments=[str(attachment)],
                preferences={"output_style": "structured"},
                prohibitions=["Do not delete audit history."],
                expected_facts=[
                    "Audit history must never be deleted.",
                    "Every important summary must cite evidence.",
                    "Destructive actions require explicit approval.",
                ],
                min_evidence_ref_count=3,
            )
        ]
    )

    harness = EvaluationHarness()
    comparison = harness.compare_strategies(
        dataset=dataset,
        runtime_factories={
            "economy": lambda storage_root: RuntimeService(storage_root=storage_root, routing_strategy="economy"),
            "quality": lambda storage_root: RuntimeService(storage_root=storage_root, routing_strategy="quality"),
        },
        working_root=tmp_path / "benchmarks",
    )

    assert comparison["quality"].metrics["evidence_coverage_rate"] >= comparison["economy"].metrics["evidence_coverage_rate"]
    assert comparison["quality"].metrics["shadow_verification_score"] >= comparison["economy"].metrics["shadow_verification_score"]

    engine = EvolutionEngine()
    candidate = engine.propose_candidate(
        candidate_type="routing_rule",
        source_traces=["audit-001"],
        target_component="runtime.routing",
        hypothesis="Quality routing improves evidence coverage over economy routing for this dataset.",
    )

    weak_eval = engine.evaluate_candidate(candidate.candidate_id, report=comparison["economy"])
    assert weak_eval.status == "failed"

    strong_candidate = engine.propose_candidate(
        candidate_type="routing_rule",
        source_traces=["audit-002"],
        target_component="runtime.routing",
        hypothesis="Quality routing should be promotable when benchmarked against the dataset.",
    )
    strong_eval = engine.evaluate_candidate(strong_candidate.candidate_id, report=comparison["quality"])
    canary = engine.run_canary(strong_candidate.candidate_id, success_rate=1.0, anomaly_count=0)
    promoted = engine.promote_candidate(strong_candidate.candidate_id)

    assert strong_eval.status == "passed"
    assert canary.status == "promoted"
    assert promoted.promotion_result == "promoted"
