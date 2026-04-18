from pathlib import Path

from contract_evidence_os.evals.dataset import MemoryLifecycleBenchmarkCase, MemoryLifecycleBenchmarkDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.service import RuntimeService


def test_amos_memory_operations_v6_benchmark_reports_background_learning_and_artifact_metrics(tmp_path: Path) -> None:
    dataset = MemoryLifecycleBenchmarkDataset(
        cases=[
            MemoryLifecycleBenchmarkCase(
                case_id="memory-ops-v6-001",
                goal="Summarize how AMOS should maintain auditable long-term memory over time.",
                attachments=[],
                preferences={"output_style": "structured"},
                prohibitions=["Do not erase audit lineage."],
                query="What should AMOS remember about long-term memory maintenance?",
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
    assert "shared_artifact_backend_repair_rate" in report.metrics
    assert "repair_learning_state_rate" in report.metrics
    assert "background_maintenance_resume_rate" in report.metrics
    assert "background_safe_repair_apply_rate" in report.metrics
