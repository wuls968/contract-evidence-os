import json
import threading
import urllib.request
from pathlib import Path

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


def test_remote_operator_service_exposes_v1_contract_and_versioned_routes(tmp_path: Path) -> None:
    attachment = tmp_path / "notes.txt"
    attachment.write_text("Expose a versioned operator contract for AMOS and software control.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    result = service.run_task(
        goal="Read the note and summarize the versioned operator contract requirements.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not erase audit lineage."],
    )

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        contract = _request("GET", f"{remote.base_url}/v1/service/api-contract", "secret-token")
        assert contract["version"] == "v1"
        assert contract["http"]["routes"]
        assert contract["cli"]["commands"]

        kernel = _request("GET", f"{remote.base_url}/v1/tasks/{result.task_id}/memory/kernel", "secret-token")
        assert kernel["task_id"] == result.task_id
        assert "timeline_view" in kernel

        report = _request("GET", f"{remote.base_url}/v1/reports/system", "secret-token")
        assert "memory" in report
        assert "software_control" in report
    finally:
        remote.shutdown()
