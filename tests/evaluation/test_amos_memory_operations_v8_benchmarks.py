from pathlib import Path

from contract_evidence_os.evals.dataset import MemoryLifecycleBenchmarkCase, MemoryLifecycleBenchmarkDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.service import RuntimeService


def test_amos_memory_operations_v8_benchmark_reports_drift_and_incident_metrics(tmp_path: Path) -> None:
    dataset = MemoryLifecycleBenchmarkDataset(
        cases=[
            MemoryLifecycleBenchmarkCase(
                case_id="memory-ops-v8-001",
                goal="Summarize how AMOS should survive maintenance drift and degraded backend conditions.",
                attachments=[],
                preferences={"output_style": "structured"},
                prohibitions=["Do not erase audit lineage."],
                query="What should AMOS remember about drift and degraded maintenance handling?",
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
    assert "artifact_drift_reconciliation_rate" in report.metrics
    assert "maintenance_incident_visibility_rate" in report.metrics
    assert "maintenance_degraded_survival_rate" in report.metrics
