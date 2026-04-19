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


def test_operator_and_remote_service_expose_ops_schedule_resume_diagnostics_and_promotions(tmp_path: Path) -> None:
    attachment = tmp_path / "notes.txt"
    attachment.write_text("AMOS should support periodic memory repair loops and promotion recommendations.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    result = service.run_task(
        goal="Read the attachment and summarize the periodic memory repair requirements.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not erase audit lineage."],
    )

    api = OperatorAPI(storage_root=root)
    schedule = api.schedule_memory_operations_loop(
        result.task_id,
        cadence_hours=24,
        actor="operator",
    )
    assert schedule["cadence_hours"] == 24

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        interrupted = _request(
            "POST",
            f"{remote.base_url}/tasks/{result.task_id}/memory/operations-loop",
            "secret-token",
            {"reason": "scheduled run", "interrupt_after": "consolidation"},
        )
        assert interrupted["status"] == "interrupted"

        resumed = _request(
            "POST",
            f"{remote.base_url}/tasks/{result.task_id}/memory/operations-loop/{interrupted['run_id']}/resume",
            "secret-token",
            {"actor": "remote-operator", "reason": "resume scheduled run"},
        )
        assert resumed["status"] == "completed"

        diagnostics = _request(
            "GET",
            f"{remote.base_url}/tasks/{result.task_id}/memory/ops-diagnostics",
            "secret-token",
        )
        assert "interrupted_loop_count" in diagnostics["diagnostics"]

        promotions = _request(
            "GET",
            f"{remote.base_url}/tasks/{result.task_id}/memory/admission-promotions",
            "secret-token",
        )
        assert "items" in promotions
    finally:
        remote.shutdown()
