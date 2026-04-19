from __future__ import annotations

from pathlib import Path

import fakeredis

from contract_evidence_os.evals.dataset import SystemScaleTaskCase, SystemScaleTaskDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.service import RuntimeService


class _FakePostgresClient:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str], dict[str, object]] = {}

    def ping(self) -> bool:
        return True

    def upsert_record(self, *, record_type: str, record_id: str, scope_key: str, payload: dict[str, object]) -> None:
        self.records[(record_type, record_id)] = {
            "record_type": record_type,
            "record_id": record_id,
            "scope_key": scope_key,
            "payload": payload,
        }

    def load_record(self, *, record_type: str, record_id: str) -> dict[str, object] | None:
        return self.records.get((record_type, record_id))

    def list_records(self, *, record_type: str, scope_key: str | None = None) -> list[dict[str, object]]:
        rows = [row for row in self.records.values() if row["record_type"] == record_type]
        if scope_key is not None:
            rows = [row for row in rows if row["scope_key"] == scope_key]
        return rows


def _factory(strategy_name: str, shared_state_kind: str):
    shared_redis = fakeredis.FakeRedis(decode_responses=True)
    shared_postgres = _FakePostgresClient()

    def _build(root: Path) -> RuntimeService:
        return RuntimeService(
            storage_root=root,
            routing_strategy=strategy_name,
            coordination_backend_kind="redis",
            queue_backend_kind="redis",
            external_backend_client=shared_redis,
            shared_state_backend_kind=shared_state_kind,
            shared_state_backend_client=shared_postgres if shared_state_kind == "postgres" else None,
            trust_mode="hmac",
        )

    return _build


def test_reliability_security_eval_tracks_forecast_reconciliation_and_trust_metrics(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text("Evidence lineage must remain traceable.\n", encoding="utf-8")

    dataset = SystemScaleTaskDataset(
        cases=[
            SystemScaleTaskCase(
                case_id="reliability-001",
                tasks=[
                    {
                        "goal": "Read the attachment, verify it, and preserve evidence lineage.",
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

    reports = EvaluationHarness().compare_reliability_and_security_strategies(
        dataset=dataset,
        runtime_factories={
            "redis-reactive": _factory("quality", "sqlite"),
            "hybrid-predictive": _factory("quality", "postgres"),
        },
        working_root=tmp_path / "benchmarks",
    )

    for report in reports.values():
        assert "lease_conflict_rate" in report.metrics
        assert "renewal_forecast_usefulness" in report.metrics
        assert "reconciliation_success_rate" in report.metrics
        assert "provider_quota_adherence_rate" in report.metrics
        assert "secure_sensitive_action_rejection_rate" in report.metrics
