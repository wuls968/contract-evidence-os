from pathlib import Path

from contract_evidence_os.evals.dataset import MemoryBenchmarkCase, MemoryBenchmarkDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.service import RuntimeService


def _factory(name: str):
    def _build(root: Path) -> RuntimeService:
        return RuntimeService(storage_root=root, routing_strategy=name)

    return _build


def test_amos_memory_benchmark_reports_temporal_and_conflict_metrics(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text("Audit history must never be deleted.\n", encoding="utf-8")

    dataset = MemoryBenchmarkDataset(
        cases=[
            MemoryBenchmarkCase(
                case_id="memory-001",
                goal="Read the attachment and summarize the mandatory constraints.",
                attachments=[str(attachment)],
                preferences={"output_style": "structured"},
                prohibitions=["Do not delete audit history."],
                query="什么约束要求不能删除审计历史？",
                expected_terms=["audit history", "delete"],
            )
        ]
    )

    reports = EvaluationHarness().compare_memory_strategies(
        dataset=dataset,
        runtime_factories={"amos-default": _factory("quality")},
        working_root=tmp_path / "benchmarks",
    )

    report = reports["amos-default"]
    assert "memory_pack_recall_rate" in report.metrics
    assert "temporal_consistency_rate" in report.metrics
    assert "conflict_resolution_rate" in report.metrics
    assert "source_grounding_rate" in report.metrics
