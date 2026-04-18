import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from contract_evidence_os.api.server import RemoteOperatorService
from contract_evidence_os.runtime.coordination import WorkerCapabilityRecord
from contract_evidence_os.runtime.service import RuntimeService


def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, method=method, data=data)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _request_with_status(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, method=method, data=data)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Request-Id", f"req-{method.lower()}-{hash(url) & 0xffff}")
    request.add_header("X-Request-Nonce", f"nonce-{hash(url) & 0xffff}")
    request.add_header("X-Idempotency-Key", f"idem-{hash(url) & 0xffff}")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_remote_operator_service_supports_status_and_remote_approval_resume(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text(
        "\n".join(
            [
                "Audit history must never be deleted.",
                "Every important summary must cite evidence.",
                "Destructive actions require explicit approval.",
            ]
        ),
        encoding="utf-8",
    )
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    awaiting = service.run_task(
        goal="Read the attachment, build a structured delivery, verify it, and publish externally.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )
    assert awaiting.status == "awaiting_approval"

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = remote.base_url
        status = _request("GET", f"{base_url}/tasks/{awaiting.task_id}/status", "secret-token")
        assert status["status"] == "awaiting_approval"

        approvals = _request("GET", f"{base_url}/approvals?task_id={awaiting.task_id}", "secret-token")
        assert len(approvals["items"]) == 1
        request_id = approvals["items"][0]["request_id"]

        decision = _request(
            "POST",
            f"{base_url}/approvals/{request_id}/decision",
            "secret-token",
            {"approver": "remote-operator", "status": "approved", "rationale": "Reviewed remotely."},
        )
        assert decision["status"] == "approved"

        resumed = _request("POST", f"{base_url}/tasks/{awaiting.task_id}/resume", "secret-token", {})
        assert resumed["status"] == "completed"

        handoff = _request("GET", f"{base_url}/tasks/{awaiting.task_id}/handoff", "secret-token")
        assert handoff["task_id"] == awaiting.task_id
    finally:
        remote.shutdown()


def test_remote_operator_service_exposes_backend_and_service_credential_controls(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    service.register_worker(
        worker_id="worker-1",
        worker_role="worker",
        process_identity="pid-100",
        capabilities=WorkerCapabilityRecord(
            version="1.0",
            worker_id="worker-1",
            provider_access=list(service.provider_manager.providers),
            tool_access=["file_retrieval"],
            role_specialization=["Researcher", "Verifier"],
            supports_degraded_mode=True,
            supports_high_risk=True,
            max_parallel_tasks=1,
        ),
        host_id="host-a",
        service_identity="worker-service",
        endpoint_address="tcp://host-a:9101",
    )

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = remote.base_url
        backend = _request("GET", f"{base_url}/backend/state", "secret-token")
        assert backend["descriptors"]
        hosts = _request("GET", f"{base_url}/workers", "secret-token")
        assert hosts["hosts"]

        status, created = _request_with_status(
            "POST",
            f"{base_url}/auth/service-credentials",
            "secret-token",
            {"service_name": "dispatcher-1", "service_role": "dispatcher", "scopes": ["worker-service", "runtime-admin"]},
        )
        assert status == 200
        assert created["credential"]["status"] == "active"

        status, rotated = _request_with_status(
            "POST",
            f"{base_url}/auth/rotate",
            "secret-token",
            {"credential_id": created["credential"]["credential_id"], "reason": "test rotation"},
        )
        assert status == 200
        assert rotated["credential"]["status"] == "active"
    finally:
        remote.shutdown()
