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


def test_operator_and_remote_service_expose_timeline_and_hard_purge_controls(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text("Audit history must never be deleted.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    result = service.run_task(
        goal="Read the attachment and summarize the mandatory constraints.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )

    api = OperatorAPI(storage_root=root)
    timeline = api.memory_timeline(result.task_id)
    assert timeline["segments"]

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        rebuilt = _request(
            "POST",
            f"{remote.base_url}/tasks/{result.task_id}/memory/rebuild",
            "secret-token",
            {"reason": "refresh timeline indexes"},
        )
        assert rebuilt["rebuild_status"] == "completed"

        purged = _request(
            "POST",
            f"{remote.base_url}/tasks/{result.task_id}/memory/hard-purge",
            "secret-token",
            {"actor": "runtime-admin", "reason": "hard purge task scope"},
        )
        assert purged["purged_record_count"] >= 1
    finally:
        remote.shutdown()

    after = api.memory_state(result.task_id)
    assert after["raw_episodes"] == []
    assert after["semantic_facts"] == []

