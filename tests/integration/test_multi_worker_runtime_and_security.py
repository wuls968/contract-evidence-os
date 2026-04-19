import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from contract_evidence_os.api.server import RemoteOperatorService
from contract_evidence_os.runtime.coordination import WorkerCapabilityRecord
from contract_evidence_os.runtime.service import RuntimeService


def _request(
    method: str,
    url: str,
    token: str,
    *,
    request_id: str,
    nonce: str,
    payload: dict | None = None,
) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, method=method, data=data)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Request-Id", request_id)
    request.add_header("X-Request-Nonce", nonce)
    request.add_header("X-Idempotency-Key", request_id)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_runtime_recovers_from_stale_worker_and_resumes_on_second_worker(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text("Audit history must never be deleted.\n", encoding="utf-8")
    service = RuntimeService(storage_root=tmp_path / "runtime", routing_strategy="quality")

    queued = service.submit_task(
        goal="Read the attachment, build a structured delivery, and verify it.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
        priority_class="standard",
    )
    service.register_worker(
        worker_id="worker-1",
        worker_role="worker",
        process_identity="pid-100",
        capabilities=WorkerCapabilityRecord(
            version="1.0",
            worker_id="worker-1",
            provider_access=["openai_live", "anthropic_live"],
            tool_access=["file_retrieval"],
            role_specialization=["Researcher", "Verifier"],
            supports_degraded_mode=True,
            supports_high_risk=False,
            max_parallel_tasks=1,
        ),
    )
    service.register_worker(
        worker_id="worker-2",
        worker_role="worker",
        process_identity="pid-200",
        capabilities=WorkerCapabilityRecord(
            version="1.0",
            worker_id="worker-2",
            provider_access=["openai_live", "anthropic_live"],
            tool_access=["file_retrieval"],
            role_specialization=["Researcher", "Verifier"],
            supports_degraded_mode=True,
            supports_high_risk=True,
            max_parallel_tasks=1,
        ),
    )

    first = service.dispatch_next_queued_task(worker_id="worker-1", interrupt_after="planned")
    assert first["status"] == "interrupted"

    reclaimed = service.reclaim_stale_workers(force_expire=True)
    assert reclaimed["reclaimed_leases"] >= 1

    second = service.dispatch_next_queued_task(worker_id="worker-2")
    assert second["status"] in {"completed", "blocked", "awaiting_approval"}

    replay = service.replay_task(queued.task_id)
    assert replay["queue_leases"]
    assert replay["worker_registry"]


def test_remote_operator_service_requires_scopes_and_rejects_sensitive_replay(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text("Audit history must never be deleted.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    service.submit_task(
        goal="Read the attachment and verify it.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
        priority_class="standard",
    )

    remote = RemoteOperatorService(storage_root=root, token="bootstrap-token", host="127.0.0.1", port=0)
    viewer_credential, viewer_token = remote.api.auth.issue_credential(
        principal_name="viewer",
        principal_type="operator",
        scopes=["viewer"],
    )
    admin_credential, admin_token = remote.api.auth.issue_credential(
        principal_name="admin",
        principal_type="operator",
        scopes=["viewer", "runtime-admin", "policy-admin", "approver"],
    )
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = remote.base_url
        status, queue_view = _request("GET", f"{base_url}/queue/status", viewer_token, request_id="req-001", nonce="nonce-001")
        assert status == 200
        assert queue_view["queued_tasks"] >= 1

        status, denied = _request(
            "POST",
            f"{base_url}/system/governance",
            viewer_token,
            request_id="req-002",
            nonce="nonce-002",
            payload={"action": "set_drain_mode", "operator": "viewer", "reason": "should fail"},
        )
        assert status == 403
        assert denied["error"] == "forbidden"

        status, accepted = _request(
            "POST",
            f"{base_url}/system/governance",
            admin_token,
            request_id="req-003",
            nonce="nonce-003",
            payload={"action": "set_drain_mode", "operator": "admin", "reason": "secured drain"},
        )
        assert status == 200
        assert accepted["status"] == "accepted"

        replay_status, replayed = _request(
            "POST",
            f"{base_url}/system/governance",
            admin_token,
            request_id="req-003",
            nonce="nonce-003",
            payload={"action": "set_drain_mode", "operator": "admin", "reason": "secured drain"},
        )
        assert replay_status in {401, 409}
        assert replayed["error"] in {"replayed_request", "unauthorized"}
    finally:
        remote.shutdown()
