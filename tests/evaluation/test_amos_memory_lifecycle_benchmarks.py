from pathlib import Path

from contract_evidence_os.evals.dataset import MemoryLifecycleBenchmarkCase, MemoryLifecycleBenchmarkDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.service import RuntimeService


def _factory(name: str):
    def _build(root: Path) -> RuntimeService:
        return RuntimeService(storage_root=root, routing_strategy=name)

    return _build


def test_amos_memory_lifecycle_benchmark_reports_deletion_and_consolidation_metrics(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text("Audit history must never be deleted.\n", encoding="utf-8")

    dataset = MemoryLifecycleBenchmarkDataset(
        cases=[
            MemoryLifecycleBenchmarkCase(
                case_id="memory-life-001",
                goal="Read the attachment and summarize the mandatory constraints.",
                attachments=[str(attachment)],
                preferences={"output_style": "structured"},
                prohibitions=["Do not delete audit history."],
                query="什么约束要求不能删除审计历史？",
                expected_terms=["audit history", "delete"],
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
    assert "memory_deletion_compliance_rate" in report.metrics
    assert "durative_reconstruction_rate" in report.metrics
    assert "rebuild_consistency_rate" in report.metrics
    assert "consolidation_effectiveness_rate" in report.metrics
