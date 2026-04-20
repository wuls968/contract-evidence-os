import json
import stat
import threading
import urllib.request
from pathlib import Path

from contract_evidence_os.api.server import RemoteOperatorService
from contract_evidence_os.runtime.service import RuntimeService


def _write_harness(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "import sys",
                "args = sys.argv[1:]",
                "if args == ['--help']:",
                "    print('Usage: cli-anything-demo [--json] <command>')",
                "    print('')",
                "    print('Commands:')",
                "    print('  inspect inspect the current app state')",
                "    raise SystemExit(0)",
                "emit_json = False",
                "if args and args[0] == '--json':",
                "    emit_json = True",
                "    args = args[1:]",
                "payload = {'command': args[0] if args else 'inspect', 'status': 'ok', 'artifact': '/tmp/demo-artifact.txt'}",
                "print(json.dumps(payload) if emit_json else payload['command'])",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


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


def test_remote_operator_service_exposes_metrics_software_report_and_daemon_endpoint(tmp_path: Path) -> None:
    attachment = tmp_path / "note.txt"
    attachment.write_text("Expose metrics and resident maintenance daemon surfaces.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    runtime = RuntimeService(storage_root=root)
    result = runtime.run_task(
        goal="Read the note and summarize metrics and daemon requirements.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not erase audit lineage."],
    )
    runtime.memory.retrieve_evidence_pack(query="metrics and daemon", scope_key=result.task_id)
    harness = tmp_path / "cli-anything-demo"
    _write_harness(harness)
    registration = runtime.register_cli_anything_harness(executable_path=str(harness))
    runtime.invoke_cli_anything_harness(
        harness_id=str(registration["harness"]["harness_id"]),
        command_path=["inspect"],
        arguments=[],
        actor="tester",
        task_id=result.task_id,
        approved=True,
    )

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        metrics = _request("GET", f"{remote.base_url}/v1/reports/metrics", "secret-token")
        assert "maintenance" in metrics
        assert "software_control" in metrics

        software = _request("GET", f"{remote.base_url}/v1/reports/software-control", "secret-token")
        assert software["summary"]["harness_count"] >= 1
        assert software["summary"]["action_receipt_count"] >= 1

        daemon = _request(
            "POST",
            f"{remote.base_url}/v1/tasks/{result.task_id}/memory/maintenance-workers/daemon",
            "secret-token",
            {"worker_id": "daemon-remote", "host_id": "host-remote", "actor": "remote-operator", "cycles": 1},
        )
        assert daemon["task_id"] == result.task_id
        assert daemon["summary"]["cycles_completed"] == 1
        assert daemon["worker"]["worker_id"] == "daemon-remote"
    finally:
        remote.shutdown()
