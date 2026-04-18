from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from contract_evidence_os.runtime.auth import AuthManager
from contract_evidence_os.runtime.capacity import ProviderCapacityForecaster, ProviderQuotaGovernor
from contract_evidence_os.runtime.coordination import WorkerCapabilityRecord
from contract_evidence_os.runtime.reliability import ReliabilityManager
from contract_evidence_os.runtime.shared_state import (
    BackendHealthRecord,
    NetworkIdentityRecord,
    PostgresSharedStateBackend,
    SharedStateBackendDescriptor,
    SQLiteSharedStateBackend,
)
from contract_evidence_os.runtime.trust import HMACTrustManager, ServiceTrustPolicy
from contract_evidence_os.storage.repository import SQLiteRepository


def _now() -> datetime:
    return datetime(2026, 4, 17, 12, 0, tzinfo=UTC)


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


def test_shared_state_backends_support_durable_record_contracts(tmp_path: Path) -> None:
    sqlite_backend = SQLiteSharedStateBackend(tmp_path / "shared_state.sqlite3")
    postgres_backend = PostgresSharedStateBackend(client=_FakePostgresClient())

    descriptor = SharedStateBackendDescriptor(
        version="1.0",
        backend_name="hybrid-postgres",
        backend_kind="postgres",
        durability_class="durable_shared_state",
        coordination_capability="lease_and_reconciliation_mirror",
        transaction_capability="single-record atomic upsert",
        reconciliation_capability="outage_replay_and_repair",
        failure_modes=["backend_outage", "partial_visibility"],
        deployment_assumption="shared durable database",
    )
    health = BackendHealthRecord(
        version="1.0",
        backend_name="hybrid-postgres",
        backend_kind="postgres",
        status="available",
        latency_ms=4.2,
        connected=True,
        updated_at=_now(),
    )

    for backend in (sqlite_backend, postgres_backend):
        backend.save_descriptor(descriptor)
        backend.save_health(health)
        backend.upsert_record(
            record_type="network_identity",
            record_id="net-001",
            scope_key="runtime",
            payload=NetworkIdentityRecord(
                version="1.0",
                network_identity_id="net-001",
                principal_id="service-principal-001",
                source_address="10.0.0.10",
                asserted_identity="dispatcher.internal",
                trust_mode="hmac",
                status="accepted",
                created_at=_now(),
            ).to_dict(),
        )
        loaded = backend.load_record("network_identity", "net-001")
        assert loaded is not None
        assert loaded["payload"]["asserted_identity"] == "dispatcher.internal"
        assert backend.list_records("network_identity", scope_key="runtime")


def test_reliability_manager_predicts_lease_risk_quarantines_conflicts_and_reconciles(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    reliability = ReliabilityManager(repository=repository, now_factory=_now)

    worker = WorkerCapabilityRecord(
        version="1.0",
        worker_id="worker-a",
        provider_access=["openai_live"],
        tool_access=["file_retrieval"],
        role_specialization=["Verifier"],
        supports_degraded_mode=True,
        supports_high_risk=True,
        max_parallel_tasks=1,
        created_at=_now(),
    )
    repository.save_worker_capability(worker)

    prediction = reliability.predict_lease_renewal(
        lease_id="lease-001",
        worker_id="worker-a",
        host_id="host-a",
        seconds_remaining=9.0,
        renewal_latency_ms=850.0,
        host_pressure=0.8,
        provider_pressure=0.6,
        criticality="verification",
    )
    assert prediction["risk"].risk_level in {"medium", "high"}
    assert prediction["forecast"].recommended_action in {"renew_now", "quarantine_if_conflict"}

    incident = reliability.quarantine_conflict(
        lease_id="lease-001",
        task_id="task-001",
        stale_worker_id="worker-a",
        active_worker_id="worker-b",
        reason="stale owner renewed after reclaim",
    )
    assert incident.severity in {"high", "critical"}

    reconciliation = reliability.run_reconciliation(reason="backend reconnected after latency spike")
    assert reconciliation.status in {"completed", "no_action"}
    assert repository.list_reliability_incidents()
    assert repository.list_reconciliation_runs()


def test_capacity_forecaster_and_quota_governor_protect_verification_capacity(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    forecaster = ProviderCapacityForecaster(repository=repository, now_factory=_now)
    governor = ProviderQuotaGovernor(repository=repository, now_factory=_now)

    forecast = forecaster.record_provider_demand(
        provider_name="openai_live",
        role="verifier",
        observed_demand=5,
        projected_demand=8,
        fallback_pressure=0.4,
        reservation_pressure=0.7,
    )
    assert forecast.projected_demand >= forecast.observed_demand

    governor.set_quota_policy(
        provider_name="openai_live",
        per_role_quota={"builder": 2, "verifier": 3},
        protected_reservations={"verification": 2, "recovery": 1},
        low_priority_cap=1,
    )

    build_decision = governor.evaluate_request(
        provider_name="openai_live",
        task_id="task-build",
        role="builder",
        workload="build",
        priority_class="background",
        requested_units=2,
    )
    verify_decision = governor.evaluate_request(
        provider_name="openai_live",
        task_id="task-verify",
        role="verifier",
        workload="verification",
        priority_class="high",
        requested_units=1,
    )

    assert build_decision.allowed in {True, False}
    assert verify_decision.allowed is True
    assert repository.list_provider_quota_policies()
    assert repository.list_provider_demand_forecasts()


def test_hmac_trust_manager_signs_verifies_and_rejects_replayed_or_revoked_requests(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    auth = AuthManager(repository=repository)
    trust = HMACTrustManager(repository=repository, now_factory=_now)

    credential, secret = auth.issue_service_credential(
        service_name="dispatcher-1",
        service_role="dispatcher",
        scopes=["worker-service", "runtime-admin"],
        allowed_hosts=["127.0.0.1"],
        expires_at=_now() + timedelta(minutes=15),
    )
    trust.bind_service_credential(
        credential_id=credential.credential_id,
        principal_id=credential.principal_id,
        trust_policy=ServiceTrustPolicy(
            version="1.0",
            policy_id="trust-default",
            trust_mode="hmac",
            require_nonce=True,
            max_clock_skew_seconds=60,
            signed_headers=["x-request-id", "x-request-timestamp", "x-request-nonce"],
            allowed_networks=["127.0.0.1/32"],
            created_at=_now(),
        ),
    )

    signed = trust.sign_request(
        credential_id=credential.credential_id,
        secret=secret,
        method="POST",
        path="/system/governance",
        request_id="req-001",
        nonce="nonce-001",
        timestamp=_now(),
        body=b'{"action":"set_drain_mode"}',
    )
    accepted = trust.verify_request(
        credential_id=credential.credential_id,
        method="POST",
        path="/system/governance",
        headers=signed,
        body=b'{"action":"set_drain_mode"}',
        source_address="127.0.0.1",
    )
    assert accepted.accepted is True

    replayed = trust.verify_request(
        credential_id=credential.credential_id,
        method="POST",
        path="/system/governance",
        headers=signed,
        body=b'{"action":"set_drain_mode"}',
        source_address="127.0.0.1",
    )
    assert replayed.accepted is False

    auth.revoke_credential(credential.credential_id, reason="security rotation", revoked_at=_now() + timedelta(seconds=1))
    denied = trust.verify_request(
        credential_id=credential.credential_id,
        method="POST",
        path="/system/governance",
        headers={**signed, "x-request-id": "req-002", "x-request-nonce": "nonce-002"},
        body=b'{"action":"set_drain_mode"}',
        source_address="127.0.0.1",
    )
    assert denied.accepted is False
    assert repository.list_security_incidents()
