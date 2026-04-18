from pathlib import Path

from contract_evidence_os.evals.dataset import MemoryLifecycleBenchmarkCase, MemoryLifecycleBenchmarkDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.service import RuntimeService


def _factory(name: str):
    def _build(root: Path) -> RuntimeService:
        return RuntimeService(storage_root=root, routing_strategy=name)

    return _build


def test_amos_memory_operations_v4_benchmark_reports_rebuild_repair_and_ops_loop_metrics(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text("Memory recovery must support selective rebuild, repair rollback, and long-running ops loops.\n", encoding="utf-8")

    dataset = MemoryLifecycleBenchmarkDataset(
        cases=[
            MemoryLifecycleBenchmarkCase(
                case_id="memory-ops-v4-001",
                goal="Read the attachment and summarize the mandatory memory recovery constraints.",
                attachments=[str(attachment)],
                preferences={"output_style": "structured"},
                prohibitions=["Do not delete audit history."],
                query="哪些约束要求 selective rebuild、repair rollback 和 memory ops loop？",
                expected_terms=["memory recovery", "rebuild", "rollback"],
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
    assert "selective_rebuild_recovery_rate" in report.metrics
    assert "repair_apply_rollback_rate" in report.metrics
    assert "admission_canary_evolution_link_rate" in report.metrics
    assert "memory_operations_loop_rate" in report.metrics
