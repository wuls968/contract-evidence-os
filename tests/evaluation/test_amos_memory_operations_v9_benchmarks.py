from pathlib import Path

from contract_evidence_os.evals.dataset import MemoryLifecycleBenchmarkCase, MemoryLifecycleBenchmarkDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.service import RuntimeService


def test_amos_memory_operations_v9_benchmark_reports_worker_resolution_and_rollout_metrics(tmp_path: Path) -> None:
    dataset = MemoryLifecycleBenchmarkDataset(
        cases=[
            MemoryLifecycleBenchmarkCase(
                case_id="memory-ops-v9-001",
                goal="Summarize how AMOS should run resident maintenance workers and govern rollout rollback.",
                attachments=[],
                preferences={"output_style": "structured"},
                prohibitions=["Do not erase audit lineage."],
                query="What should AMOS remember about maintenance workers, incident resolution, and rollout rollback?",
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
    assert "maintenance_worker_claim_rate" in report.metrics
    assert "maintenance_incident_resolution_rate" in report.metrics
    assert "maintenance_rollout_rollback_visibility_rate" in report.metrics
