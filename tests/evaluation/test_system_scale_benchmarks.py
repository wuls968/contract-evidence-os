from pathlib import Path

from contract_evidence_os.evals.dataset import SystemScaleTaskCase, SystemScaleTaskDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.service import RuntimeService


def _factory(strategy_name: str):
    def _build(root: Path) -> RuntimeService:
        return RuntimeService(storage_root=root, routing_strategy=strategy_name)

    return _build


def test_system_scale_eval_tracks_queue_pressure_provider_survival_and_policy_gain(tmp_path: Path) -> None:
    attachment_a = tmp_path / "requirements-a.txt"
    attachment_b = tmp_path / "requirements-b.txt"
    attachment_a.write_text("Audit history must never be deleted.\n", encoding="utf-8")
    attachment_b.write_text("Every important summary must cite evidence.\n", encoding="utf-8")

    dataset = SystemScaleTaskDataset(
        cases=[
            SystemScaleTaskCase(
                case_id="system-001",
                tasks=[
                    {
                        "goal": "Read attachment A and verify it.",
                        "attachments": [str(attachment_a)],
                        "preferences": {"output_style": "structured", "max_cost": "0.05"},
                        "prohibitions": ["Do not delete audit history."],
                        "priority_class": "standard",
                    },
                    {
                        "goal": "Read attachment B and verify it.",
                        "attachments": [str(attachment_b)],
                        "preferences": {"output_style": "structured", "max_cost": "0.05"},
                        "prohibitions": ["Do not delete audit history."],
                        "priority_class": "recovery",
                    },
                ],
                simulate_provider_pressure=True,
                expect_defer_or_queue=True,
            )
        ]
    )

    reports = EvaluationHarness().compare_system_scale_strategies(
        dataset=dataset,
        runtime_factories={"quality": _factory("quality"), "economy": _factory("economy")},
        working_root=tmp_path / "benchmarks",
    )

    for report in reports.values():
        assert "queue_latency" in report.metrics
        assert "admission_success_rate" in report.metrics
        assert "provider_pressure_survival_rate" in report.metrics
        assert "policy_promotion_gain_rate" in report.metrics
