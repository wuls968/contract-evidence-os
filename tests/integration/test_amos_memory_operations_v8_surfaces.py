import json
import threading
import urllib.request
from pathlib import Path

from contract_evidence_os.api.operator import OperatorAPI
from contract_evidence_os.api.server import RemoteOperatorService
from contract_evidence_os.runtime.service import RuntimeService


def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, method=method, data=data)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Request-Id", f"req-{method.lower()}-{abs(hash(url)) % 100000}")
    request.add_header("X-Request-Nonce", f"nonce-{abs(hash(url)) % 100000}")
    request.add_header("X-Idempotency-Key", f"idem-{abs(hash(url)) % 100000}")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_operator_and_remote_service_expose_maintenance_drift_and_incidents(tmp_path: Path) -> None:
    attachment = tmp_path / "notes.txt"
    attachment.write_text("AMOS should expose maintenance drift and incident state.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    service.memory.shared_artifact_root = root / "shared-artifacts"
    result = service.run_task(
        goal="Read the attachment and summarize maintenance drift and incident visibility requirements.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not erase audit lineage."],
    )
    service.memory.rebuild_indexes(scope_key=result.task_id, reason="prime drift indexes")
    service.memory.shared_artifact_root = None
    service.memory.run_background_memory_maintenance(scope_keys=[result.task_id], actor="worker")

    api = OperatorAPI(storage_root=root)
    incidents = api.memory_maintenance_incidents(result.task_id)
    assert "items" in incidents

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        mode = _request(
            "GET",
            f"{remote.base_url}/tasks/{result.task_id}/memory/maintenance-mode",
            "secret-token",
        )
        assert "mode" in mode

        drift = _request(
            "GET",
            f"{remote.base_url}/tasks/{result.task_id}/memory/maintenance-drift",
            "secret-token",
        )
        assert "items" in drift
    finally:
        remote.shutdown()
