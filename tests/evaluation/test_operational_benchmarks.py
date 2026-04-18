from pathlib import Path

from contract_evidence_os.evals.dataset import OperationalTaskCase, OperationalTaskDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.service import RuntimeService


def _factory(strategy_name: str):
    def _build(root: Path) -> RuntimeService:
        return RuntimeService(storage_root=root, routing_strategy=strategy_name)

    return _build


def test_operational_eval_tracks_routing_budget_and_concurrency_metrics(tmp_path: Path) -> None:
    attachment_a = tmp_path / "requirements-a.txt"
    attachment_b = tmp_path / "requirements-b.txt"
    attachment_a.write_text("Audit history must never be deleted.\n", encoding="utf-8")
    attachment_b.write_text("Every important summary must cite evidence.\n", encoding="utf-8")

    dataset = OperationalTaskDataset(
        cases=[
            OperationalTaskCase(
                case_id="ops-001",
                goal="Read both attachments, build a structured delivery, and verify it.",
                attachments=[str(attachment_a), str(attachment_b)],
                preferences={"output_style": "structured", "max_cost": "0.05"},
                prohibitions=["Do not delete audit history."],
                expected_facts=[
                    "Audit history must never be deleted.",
                    "Every important summary must cite evidence.",
                ],
                require_concurrency=True,
                require_budget_mode=True,
            )
        ]
    )

    reports = EvaluationHarness().compare_operational_strategies(
        dataset=dataset,
        runtime_factories={"quality": _factory("quality"), "economy": _factory("economy")},
        working_root=tmp_path / "benchmarks",
    )

    for report in reports.values():
        assert "provider_fallback_success_rate" in report.metrics
        assert "budget_adherence_rate" in report.metrics
        assert "concurrency_gain_vs_overhead" in report.metrics
