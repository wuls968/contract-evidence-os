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
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_remote_operator_service_exposes_governance_state_and_controls(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text(
        "\n".join(
            [
                "Audit history must never be deleted.",
                "Every important summary must cite evidence.",
            ]
        ),
        encoding="utf-8",
    )
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    result = service.run_task(
        goal="Read the attachment, build a structured delivery, and verify it.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = remote.base_url
        mode = _request("GET", f"{base_url}/tasks/{result.task_id}/governance", "secret-token")
        assert mode["execution_mode"]["task_id"] == result.task_id
        assert "provider_scorecards" in mode
        assert "tool_scorecards" in mode

        override = _request(
            "POST",
            f"{base_url}/tasks/{result.task_id}/governance",
            "secret-token",
            {"action": "force_low_cost_mode", "operator": "remote-operator", "reason": "cap spend"},
        )
        assert override["status"] == "accepted"
    finally:
        remote.shutdown()
