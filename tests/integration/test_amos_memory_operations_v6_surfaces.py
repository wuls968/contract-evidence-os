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


def test_operator_and_remote_service_expose_background_maintenance_and_artifact_health(tmp_path: Path) -> None:
    attachment = tmp_path / "notes.txt"
    attachment.write_text("AMOS should support background memory maintenance and shared artifact repair.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    service.memory.shared_artifact_root = root / "shared-artifacts"
    result = service.run_task(
        goal="Read the attachment and summarize the background memory maintenance requirements.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not erase audit lineage."],
    )

    api = OperatorAPI(storage_root=root)
    api.schedule_memory_operations_loop(
        result.task_id,
        cadence_hours=24,
        actor="operator",
    )
    api.memory_operations_loop(
        result.task_id,
        reason="interrupt for background maintenance",
        interrupt_after="consolidation",
    )

    recommendation = api.memory_maintenance_recommendation(result.task_id)
    assert "actions" in recommendation["recommendation"]

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        maintenance = _request(
            "POST",
            f"{remote.base_url}/tasks/{result.task_id}/memory/background-maintenance",
            "secret-token",
            {"actor": "remote-operator"},
        )
        assert maintenance["items"]

        health = _request(
            "GET",
            f"{remote.base_url}/tasks/{result.task_id}/memory/artifact-health",
            "secret-token",
        )
        assert "items" in health

        recommendations = _request(
            "GET",
            f"{remote.base_url}/tasks/{result.task_id}/memory/maintenance-recommendations",
            "secret-token",
        )
        assert "items" in recommendations
    finally:
        remote.shutdown()
