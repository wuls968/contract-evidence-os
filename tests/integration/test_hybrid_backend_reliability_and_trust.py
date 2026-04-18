from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
import json
import threading

import fakeredis

from contract_evidence_os.api.server import RemoteOperatorService
from contract_evidence_os.runtime.coordination import WorkerCapabilityRecord
from contract_evidence_os.runtime.service import RuntimeService
from contract_evidence_os.runtime.shared_state import PostgresSharedStateBackend
from contract_evidence_os.runtime.trust import ServiceTrustPolicy


def _now() -> datetime:
    return datetime(2026, 4, 17, 14, 0, tzinfo=UTC)


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


def test_runtime_supports_hybrid_shared_state_reconciliation_and_hmac_trust(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text("Verification must preserve citations.\n", encoding="utf-8")

    redis_client = fakeredis.FakeRedis(decode_responses=True)
    postgres_client = _FakePostgresClient()
    runtime = RuntimeService(
        storage_root=tmp_path / "runtime",
        routing_strategy="quality",
        queue_backend_kind="redis",
        coordination_backend_kind="redis",
        external_backend_client=redis_client,
        shared_state_backend_kind="postgres",
        shared_state_backend_client=postgres_client,
        trust_mode="hmac",
    )

    runtime.submit_task(
        goal="Read the attachment and verify it with evidence.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )
    runtime.register_worker(
        worker_id="worker-a",
        worker_role="worker",
        process_identity="pid-a",
        host_id="host-a",
        service_identity="worker-service",
        endpoint_address="tcp://host-a:9101",
        capabilities=WorkerCapabilityRecord(
            version="1.0",
            worker_id="worker-a",
            provider_access=list(runtime.provider_manager.providers),
            tool_access=["file_retrieval"],
            role_specialization=["Researcher", "Verifier"],
            supports_degraded_mode=True,
            supports_high_risk=True,
            max_parallel_tasks=1,
        ),
    )
    first = runtime.dispatch_next_queued_task(worker_id="worker-a", interrupt_after="planned")
    assert first["status"] == "interrupted"

    runtime.record_backend_outage(
        backend_name="redis",
        fault_domain="queue_coordination",
        summary="simulated coordination outage",
    )
    reconciliation = runtime.run_reconciliation(reason="redis reconnected after interruption")
    assert reconciliation["status"] in {"completed", "no_action"}
    assert runtime.repository.list_reconciliation_runs()

    durable = PostgresSharedStateBackend(client=postgres_client)
    assert durable.list_records("reconciliation_run")

    service = RemoteOperatorService(
        storage_root=tmp_path / "runtime",
        token="bootstrap-token",
        port=0,
        queue_backend_kind="redis",
        coordination_backend_kind="redis",
        external_backend_client=redis_client,
        shared_state_backend_kind="postgres",
        shared_state_backend_client=postgres_client,
        trust_mode="hmac",
    )
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    try:
        issued = service.api.auth.issue_service_credential(
            service_name="dispatcher-1",
            service_role="dispatcher",
            scopes=["runtime-admin", "worker-service"],
            allowed_hosts=["127.0.0.1"],
            expires_at=service.api.trust.now_factory() + timedelta(minutes=15),
        )
        credential, secret = issued
        service.api.trust.bind_service_credential(
            credential_id=credential.credential_id,
            principal_id=credential.principal_id,
            trust_policy=ServiceTrustPolicy(
                version="1.0",
                policy_id="service-trust-dispatcher",
                trust_mode="hmac",
                require_nonce=True,
                max_clock_skew_seconds=120,
                signed_headers=["x-request-id", "x-request-timestamp", "x-request-nonce"],
                allowed_networks=["127.0.0.1/32"],
                created_at=service.api.trust.now_factory(),
            ),
        )
        headers = service.api.trust.sign_request(
            credential_id=credential.credential_id,
            secret=secret,
            method="POST",
            path="/system/governance",
            request_id="req-hybrid-001",
            nonce="nonce-hybrid-001",
            timestamp=service.api.trust.now_factory(),
            body=b'{"action":"set_low_cost_mode","operator":"dispatcher-1","reason":"quota pressure","payload":{"idempotency_key":"gov-001"}}',
        )
        request = Request(
            f"{service.base_url}/system/governance",
            data=b'{"action":"set_low_cost_mode","operator":"dispatcher-1","reason":"quota pressure","payload":{"idempotency_key":"gov-001"}}',
            headers={
                "Authorization": "Bearer bootstrap-token",
                "Content-Type": "application/json",
                "X-Request-Id": headers["x-request-id"],
                "X-Request-Nonce": headers["x-request-nonce"],
                "X-Request-Timestamp": headers["x-request-timestamp"],
                "X-Service-Credential": credential.credential_id,
                "X-Service-Signature": headers["x-service-signature"],
            },
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["status"] in {"active", "accepted", "normal", "low-cost"}
    finally:
        service.shutdown()
