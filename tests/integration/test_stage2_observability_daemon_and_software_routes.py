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
                "    print('Usage: cli-anything-advanced [--json] <command> [args]')",
                "    print('')",
                "    print('Commands:')",
                "    print('  inspect inspect the current app state')",
                "    print('  recover-tab reopen a broken tab')",
                "    print('  fail-open simulate a flaky failure path')",
                "    raise SystemExit(0)",
                "emit_json = False",
                "if args and args[0] == '--json':",
                "    emit_json = True",
                "    args = args[1:]",
                "command = args[0] if args else 'inspect'",
                "if command == 'fail-open':",
                "    payload = {'command': command, 'status': 'failed', 'error': 'window not ready'}",
                "    print(json.dumps(payload) if emit_json else 'failed')",
                "    raise SystemExit(1)",
                "payload = {'command': command, 'status': 'ok', 'artifact': '/tmp/advanced-artifact.txt', 'args': args[1:]}",
                "print(json.dumps(payload) if emit_json else command)",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _request(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, object]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, method=method, data=data)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Request-Id", f"req-{method.lower()}-{abs(hash(url)) % 100000}")
    request.add_header("X-Request-Nonce", f"nonce-{abs(hash(url)) % 100000}")
    request.add_header("X-Idempotency-Key", f"idem-{abs(hash(url)) % 100000}")
    with urllib.request.urlopen(request, timeout=5) as response:
        body = response.read().decode("utf-8")
        if response.headers.get_content_type() == "application/json":
            return response.status, json.loads(body)
        return response.status, body


def test_stage2_remote_routes_cover_metrics_history_prometheus_daemon_and_software_reports(tmp_path: Path) -> None:
    attachment = tmp_path / "note.txt"
    attachment.write_text("Expose stage-2 operator runtime surfaces.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    runtime = RuntimeService(storage_root=root)
    result = runtime.run_task(
        goal="Read the note and summarize stage-2 route requirements.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not erase audit lineage."],
    )
    harness = tmp_path / "cli-anything-advanced"
    _write_harness(harness)
    registration = runtime.register_cli_anything_harness(executable_path=str(harness))
    harness_id = str(registration["harness"]["harness_id"])
    runtime.invoke_cli_anything_harness(
        harness_id=harness_id,
        command_path=["inspect"],
        arguments=[],
        actor="tester",
        task_id=result.task_id,
        approved=True,
    )
    runtime.invoke_cli_anything_harness(
        harness_id=harness_id,
        command_path=["fail-open"],
        arguments=[],
        actor="tester",
        task_id=result.task_id,
        approved=True,
    )
    runtime.schedule_background_maintenance(scope_key=result.task_id, cadence_hours=1, actor="tester")
    macro = runtime.register_software_automation_macro(
        harness_id=harness_id,
        actor="tester",
        name="inspect-and-recover",
        description="Inspect and then recover the current tab.",
        steps=[
            {"command_path": ["inspect"], "arguments": []},
            {"command_path": ["recover-tab"], "arguments": ["tab-1"]},
        ],
        automation_tags=["inspection", "recovery"],
    )
    runtime.metrics_report()
    runtime.metrics_report()

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        status, metrics_history = _request("GET", f"{remote.base_url}/v1/reports/metrics/history?window_hours=24", "secret-token")
        assert status == 200
        assert metrics_history["summary"]["snapshot_count"] >= 2

        status, maintenance = _request("GET", f"{remote.base_url}/v1/reports/maintenance?task_id={result.task_id}", "secret-token")
        assert status == 200
        assert maintenance["task_id"] == result.task_id

        status, exporter = _request("GET", f"{remote.base_url}/metrics", "secret-token")
        assert status == 200
        assert "ceos_software_action_receipt_count" in exporter

        status, harness_report = _request("GET", f"{remote.base_url}/v1/software/harnesses/{harness_id}/report", "secret-token")
        assert status == 200
        assert harness_report["report"]["manifest"]["manifest_id"].startswith("harness-manifest-")

        status, clusters = _request("GET", f"{remote.base_url}/v1/software/failure-clusters?harness_id={harness_id}", "secret-token")
        assert status == 200
        assert clusters["items"]

        status, hints = _request("GET", f"{remote.base_url}/v1/software/recovery-hints?harness_id={harness_id}", "secret-token")
        assert status == 200
        assert hints["items"]

        status, invoked = _request(
            "POST",
            f"{remote.base_url}/v1/software/harnesses/{harness_id}/macros/{macro.macro_id}/invoke",
            "secret-token",
            {"actor": "remote-operator", "task_id": result.task_id, "approved": True},
        )
        assert status == 200
        assert invoked["summary"]["step_count"] == 2

        status, daemon = _request(
            "POST",
            f"{remote.base_url}/v1/tasks/{result.task_id}/memory/maintenance-workers/daemon",
            "secret-token",
            {
                "worker_id": "daemon-remote",
                "host_id": "host-remote",
                "actor": "remote-operator",
                "daemon": True,
                "poll_interval_seconds": 0,
                "heartbeat_seconds": 30,
                "lease_seconds": 60,
                "max_cycles": 1,
            },
        )
        assert status == 200
        assert daemon["summary"]["cycles_completed"] == 1

        status, daemon_state = _request(
            "GET",
            f"{remote.base_url}/v1/tasks/{result.task_id}/memory/maintenance-daemon",
            "secret-token",
        )
        assert status == 200
        assert daemon_state["task_id"] == result.task_id
    finally:
        remote.shutdown()
