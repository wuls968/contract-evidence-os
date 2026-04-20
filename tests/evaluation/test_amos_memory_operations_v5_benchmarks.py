from pathlib import Path

from contract_evidence_os.evals.dataset import MemoryLifecycleBenchmarkCase, MemoryLifecycleBenchmarkDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.service import RuntimeService


def _factory(name: str):
    def _build(root: Path) -> RuntimeService:
        return RuntimeService(storage_root=root, routing_strategy=name)

    return _build


def test_amos_memory_operations_v5_benchmark_reports_safety_promotion_and_recovery_metrics(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text("Memory repair must support safety gating, promotion recommendations, and scheduled recovery.\n", encoding="utf-8")

    dataset = MemoryLifecycleBenchmarkDataset(
        cases=[
            MemoryLifecycleBenchmarkCase(
                case_id="memory-ops-v5-001",
                goal="Read the attachment and summarize the advanced memory repair constraints.",
                attachments=[str(attachment)],
                preferences={"output_style": "structured"},
                prohibitions=["Do not delete audit history."],
                query="哪些约束要求 repair safety、promotion recommendation 和 scheduled recovery？",
                expected_terms=["repair", "promotion", "recovery"],
                delete_after_run=True,
                require_consolidation=True,
            )
        ]
    )

    reports = EvaluationHarness().compare_memory_lifecycle_strategies(
        dataset=dataset,
        runtime_factories={"amos-default": _factory("quality")},
        working_root=tmp_path / "benchmarks",
    )

    report = reports["amos-default"]
    assert "repair_safety_gate_rate" in report.metrics
    assert "repair_rollout_analytics_visibility_rate" in report.metrics
    assert "admission_promotion_recommendation_rate" in report.metrics
    assert "memory_ops_schedule_recovery_rate" in report.metrics
