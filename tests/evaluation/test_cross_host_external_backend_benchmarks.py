from pathlib import Path

import fakeredis

from contract_evidence_os.evals.dataset import SystemScaleTaskCase, SystemScaleTaskDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.service import RuntimeService


def _factory(strategy_name: str, backend_kind: str):
    shared_client = fakeredis.FakeRedis(decode_responses=True) if backend_kind == "redis" else None

    def _build(root: Path) -> RuntimeService:
        return RuntimeService(
            storage_root=root,
            routing_strategy=strategy_name,
            coordination_backend_kind=backend_kind,
            queue_backend_kind=backend_kind,
            external_backend_client=shared_client,
        )

    return _build


def test_cross_host_external_backend_eval_tracks_backend_and_host_turnover_metrics(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text("Every important summary must cite evidence.\n", encoding="utf-8")

    dataset = SystemScaleTaskDataset(
        cases=[
            SystemScaleTaskCase(
                case_id="cross-host-001",
                tasks=[
                    {
                        "goal": "Read the attachment and verify it.",
                        "attachments": [str(attachment)],
                        "preferences": {"output_style": "structured"},
                        "prohibitions": ["Do not delete audit history."],
                        "priority_class": "standard",
                    }
                ],
                simulate_provider_pressure=True,
                expect_defer_or_queue=True,
            )
        ]
    )

    reports = EvaluationHarness().compare_cross_host_backend_strategies(
        dataset=dataset,
        runtime_factories={
            "sqlite-reference": _factory("quality", "sqlite"),
            "redis-external": _factory("quality", "redis"),
        },
        working_root=tmp_path / "benchmarks",
    )

    for report in reports.values():
        assert "cross_host_lease_conflict_rate" in report.metrics
        assert "lease_renewal_success_rate" in report.metrics
        assert "work_steal_safety_rate" in report.metrics
        assert "provider_fairness_under_load" in report.metrics
        assert "secure_action_rejection_rate" in report.metrics
