import json
import threading
import urllib.request
from pathlib import Path

from contract_evidence_os.api.server import RemoteOperatorService
from contract_evidence_os.runtime.service import RuntimeService


def _write_demo_harness(tmp_path: Path) -> Path:
    harness = tmp_path / "cli-anything-demo"
    harness.write_text(
        """#!/usr/bin/env python3
import json
import sys

argv = sys.argv[1:]
if "--help" in argv or not argv:
    print("Usage: cli-anything-demo [OPTIONS] COMMAND [ARGS]...")
    print("")
    print("Options:")
    print("  --json  Output JSON")
    print("")
    print("Commands:")
    print("  status        Show current state")
    print("  delete-layer  Delete a layer")
    sys.exit(0)

json_mode = False
if argv and argv[0] == "--json":
    json_mode = True
    argv = argv[1:]

command = argv[0]
if command == "status":
    print(json.dumps({"status": "ready", "facts": ["demo is connected"], "artifact": "/tmp/demo-artifact.json"}) if json_mode else "ready")
    sys.exit(0)
if command == "delete-layer":
    print(json.dumps({"status": "deleted", "layer": "Background"}) if json_mode else "deleted")
    sys.exit(0)
print(json.dumps({"error": "unknown"}) if json_mode else "unknown", file=sys.stderr)
sys.exit(2)
""",
        encoding="utf-8",
    )
    harness.chmod(0o755)
    return harness


def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, method=method, data=data)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Request-Id", f"req-{abs(hash(url))}")
    request.add_header("X-Request-Nonce", f"nonce-{abs(hash(url))}")
    request.add_header("X-Idempotency-Key", f"idem-{abs(hash((method, url)))}")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_runtime_can_register_invoke_and_gate_cli_anything_harness(tmp_path: Path) -> None:
    runtime = RuntimeService(storage_root=tmp_path / "runtime")
    harness_path = _write_demo_harness(tmp_path)

    registration = runtime.register_cli_anything_harness(executable_path=str(harness_path))
    assert registration["harness"]["software_name"] == "demo"
    harness_id = registration["harness"]["harness_id"]

    low_risk = runtime.invoke_cli_anything_harness(
        harness_id=harness_id,
        command_path=["status"],
        arguments=[],
        actor="Builder",
    )
    assert low_risk["status"] == "completed"
    assert low_risk["result"]["status"] == "success"
    assert low_risk["evidence_refs"]
    assert runtime.query_audit(task_id=low_risk["task_id"])

    gated = runtime.invoke_cli_anything_harness(
        harness_id=harness_id,
        command_path=["delete-layer"],
        arguments=[],
        actor="Builder",
    )
    assert gated["status"] == "awaiting_approval"
    approvals = runtime.approval_inbox(task_id=gated["task_id"])
    assert len(approvals) == 1

    runtime.decide_approval(
        approvals[0].request_id,
        approver="operator",
        status="approved",
        rationale="Reviewed destructive software-control action.",
    )
    resumed = runtime.invoke_cli_anything_harness(
        harness_id=harness_id,
        command_path=["delete-layer"],
        arguments=[],
        actor="Builder",
        task_id=gated["task_id"],
        approved=True,
    )
    assert resumed["status"] == "completed"
    assert resumed["result"]["parsed_json"]["layer"] == "Background"


def test_remote_operator_service_exposes_cli_anything_control_endpoints(tmp_path: Path) -> None:
    runtime = RuntimeService(storage_root=tmp_path / "runtime")
    harness_path = _write_demo_harness(tmp_path)
    runtime.register_cli_anything_harness(executable_path=str(harness_path))

    remote = RemoteOperatorService(storage_root=tmp_path / "runtime", token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = remote.base_url
        harnesses = _request("GET", f"{base_url}/software/harnesses", "secret-token")
        assert len(harnesses["items"]) == 1
        harness_id = harnesses["items"][0]["harness_id"]

        validation = _request("POST", f"{base_url}/software/harnesses/{harness_id}/validate", "secret-token", {})
        assert validation["validation"]["status"] == "passed"

        invoked = _request(
            "POST",
            f"{base_url}/software/harnesses/{harness_id}/invoke",
            "secret-token",
            {"command_path": ["status"], "arguments": [], "actor": "remote-operator"},
        )
        assert invoked["status"] == "completed"
        assert invoked["result"]["parsed_json"]["status"] == "ready"
    finally:
        remote.shutdown()
