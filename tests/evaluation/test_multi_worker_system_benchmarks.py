from pathlib import Path

from contract_evidence_os.evals.dataset import SystemScaleTaskCase, SystemScaleTaskDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.service import RuntimeService


def _factory(strategy_name: str):
    def _build(root: Path) -> RuntimeService:
        return RuntimeService(storage_root=root, routing_strategy=strategy_name)

    return _build


def test_multi_worker_eval_tracks_lease_safety_auth_rejection_and_provider_pool_fairness(tmp_path: Path) -> None:
    attachment_a = tmp_path / "requirements-a.txt"
    attachment_b = tmp_path / "requirements-b.txt"
    attachment_a.write_text("Audit history must never be deleted.\n", encoding="utf-8")
    attachment_b.write_text("Every important summary must cite evidence.\n", encoding="utf-8")

    dataset = SystemScaleTaskDataset(
        cases=[
            SystemScaleTaskCase(
                case_id="multi-worker-001",
                tasks=[
                    {
                        "goal": "Read attachment A and verify it.",
                        "attachments": [str(attachment_a)],
                        "preferences": {"output_style": "structured"},
                        "prohibitions": ["Do not delete audit history."],
                        "priority_class": "standard",
                    },
                    {
                        "goal": "Read attachment B and verify it.",
                        "attachments": [str(attachment_b)],
                        "preferences": {"output_style": "structured"},
                        "prohibitions": ["Do not delete audit history."],
                        "priority_class": "recovery",
                    },
                ],
                simulate_provider_pressure=True,
                expect_defer_or_queue=True,
            )
        ]
    )

    reports = EvaluationHarness().compare_multi_worker_strategies(
        dataset=dataset,
        runtime_factories={"single-worker": _factory("quality"), "multi-worker": _factory("economy")},
        working_root=tmp_path / "benchmarks",
    )

    for report in reports.values():
        assert "lease_conflict_rate" in report.metrics
        assert "stale_lease_recovery_time" in report.metrics
        assert "provider_pool_fairness" in report.metrics
        assert "secure_action_rejection_rate" in report.metrics
