from pathlib import Path

from contract_evidence_os.evals.dataset import MemoryLifecycleBenchmarkCase, MemoryLifecycleBenchmarkDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.service import RuntimeService


def test_amos_memory_operations_v7_benchmark_reports_maintenance_loop_metrics(tmp_path: Path) -> None:
    dataset = MemoryLifecycleBenchmarkDataset(
        cases=[
            MemoryLifecycleBenchmarkCase(
                case_id="memory-ops-v7-001",
                goal="Summarize how AMOS should run learned background maintenance over time.",
                attachments=[],
                preferences={"output_style": "structured"},
                prohibitions=["Do not erase audit lineage."],
                query="What should AMOS remember about learned background maintenance?",
            )
        ],
    )
    harness = EvaluationHarness()
    comparison = harness.compare_memory_lifecycle_strategies(
        dataset=dataset,
        runtime_factories={
            "baseline": lambda runtime_root: RuntimeService(storage_root=runtime_root, routing_strategy="quality"),
        },
        working_root=tmp_path / "benchmarks",
    )

    report = comparison["baseline"]
    assert "maintenance_schedule_recovery_rate" in report.metrics
    assert "maintenance_canary_promotion_rate" in report.metrics
    assert "shared_backend_fallback_rate" in report.metrics
    assert "maintenance_analytics_visibility_rate" in report.metrics
