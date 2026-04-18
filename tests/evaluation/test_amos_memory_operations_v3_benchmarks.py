from pathlib import Path

from contract_evidence_os.evals.dataset import MemoryLifecycleBenchmarkCase, MemoryLifecycleBenchmarkDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.service import RuntimeService


def _factory(name: str):
    def _build(root: Path) -> RuntimeService:
        return RuntimeService(storage_root=root, routing_strategy=name)

    return _build


def test_amos_memory_operations_v3_benchmark_reports_artifact_synthesis_canary_and_repair_metrics(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text("Audit history and contradiction handling must remain operator-visible.\n", encoding="utf-8")

    dataset = MemoryLifecycleBenchmarkDataset(
        cases=[
            MemoryLifecycleBenchmarkCase(
                case_id="memory-ops-v3-001",
                goal="Read the attachment and summarize the mandatory constraints.",
                attachments=[str(attachment)],
                preferences={"output_style": "structured"},
                prohibitions=["Do not delete audit history."],
                query="什么约束要求保留审计历史并处理冲突？",
                expected_terms=["audit history", "contradiction"],
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
    assert "artifact_rebuild_rate" in report.metrics
    assert "project_state_synthesis_rate" in report.metrics
    assert "admission_canary_readiness_rate" in report.metrics
    assert "cross_scope_repair_visibility_rate" in report.metrics
