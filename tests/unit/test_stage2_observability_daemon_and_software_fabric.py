import json
import stat
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from contract_evidence_os.api.cli import build_parser as build_ceos_parser
from contract_evidence_os.api.cli import main as ceos_main
from contract_evidence_os.api.contracts import operator_api_contract
from contract_evidence_os.api.maintenance_main import build_parser as build_maintenance_parser
from contract_evidence_os.api.maintenance_main import main as maintenance_main
from contract_evidence_os.api.operator import OperatorAPI
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


def _build_runtime(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "runtime"
    attachment = tmp_path / "note.txt"
    attachment.write_text("Push stage-2 observability, daemon, and software fabric to release grade.\n", encoding="utf-8")
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    result = service.run_task(
        goal="Read the note and summarize the stage-2 operator-runtime requirements.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not erase audit lineage."],
    )
    harness = tmp_path / "cli-anything-advanced"
    _write_harness(harness)
    registered = service.register_cli_anything_harness(executable_path=str(harness))
    harness_id = str(registered["harness"]["harness_id"])
    service.invoke_cli_anything_harness(
        harness_id=harness_id,
        command_path=["inspect"],
        arguments=[],
        actor="tester",
        task_id=result.task_id,
        approved=True,
        dry_run=False,
    )
    service.invoke_cli_anything_harness(
        harness_id=harness_id,
        command_path=["fail-open"],
        arguments=[],
        actor="tester",
        task_id=result.task_id,
        approved=True,
        dry_run=False,
    )
    service.schedule_background_maintenance(
        scope_key=result.task_id,
        cadence_hours=1,
        actor="tester",
    )
    return root, result.task_id, harness_id


def test_stage2_cli_reports_daemon_flags_and_release_assets(tmp_path: Path) -> None:
    root, task_id, harness_id = _build_runtime(tmp_path)
    api = OperatorAPI(storage_root=root)

    macro = api.register_software_automation_macro(
        harness_id=harness_id,
        actor="tester",
        name="inspect-and-recover",
        description="Inspect the current app state and then reopen the current tab.",
        steps=[
            {"command_path": ["inspect"], "arguments": []},
            {"command_path": ["recover-tab"], "arguments": ["tab-1"]},
        ],
        automation_tags=["inspection", "recovery"],
    )
    invoked = api.invoke_software_automation_macro(
        macro_id=macro["macro"]["macro_id"],
        actor="tester",
        task_id=task_id,
        approved=True,
    )
    assert invoked["summary"]["step_count"] == 2

    api.metrics_report()
    api.metrics_report()
    history = api.metrics_history(window_hours=24)
    assert history["summary"]["snapshot_count"] >= 2
    assert history["summary"]["window_hours"] == 24

    maintenance = api.maintenance_report(task_id)
    assert maintenance["task_id"] == task_id
    assert "workers" in maintenance["report"]
    assert "recommendations" in maintenance["report"]

    harness_report = api.software_harness_report(harness_id)
    assert harness_report["report"]["manifest"]["manifest_id"].startswith("harness-manifest-")
    assert harness_report["report"]["macros"]
    assert harness_report["report"]["replay_diagnostics"]

    clusters = api.software_failure_clusters(harness_id=harness_id)
    assert clusters["items"]
    hints = api.software_recovery_hints(harness_id=harness_id)
    assert hints["items"]

    prometheus = api.prometheus_metrics()
    assert "ceos_maintenance_incident_count" in prometheus
    assert "ceos_software_action_receipt_count" in prometheus

    stdout = StringIO()
    with redirect_stdout(stdout):
        assert ceos_main(["--storage-root", str(root), "metrics-report", "--window-hours", "24"]) == 0
    cli_metrics = json.loads(stdout.getvalue())
    assert cli_metrics["summary"]["snapshot_count"] >= 2

    stdout = StringIO()
    with redirect_stdout(stdout):
        assert ceos_main(["--storage-root", str(root), "maintenance-report", "--task-id", task_id]) == 0
    cli_maintenance = json.loads(stdout.getvalue())
    assert cli_maintenance["task_id"] == task_id

    stdout = StringIO()
    with redirect_stdout(stdout):
        assert ceos_main(
            [
                "--storage-root",
                str(root),
                "software-action-receipts",
                "--task-id",
                task_id,
                "--with-replay-diagnostics",
            ]
        ) == 0
    cli_receipts = json.loads(stdout.getvalue())
    assert cli_receipts["replay_diagnostics"]

    stdout = StringIO()
    with redirect_stdout(stdout):
        assert maintenance_main(
            [
                "--storage-root",
                str(root),
                "--daemon",
                "--maintenance-worker-id",
                "daemon-stage2",
                "--host-id",
                "host-stage2",
                "--poll-interval-seconds",
                "0",
                "--heartbeat-seconds",
                "30",
                "--lease-seconds",
                "60",
                "--max-cycles",
                "1",
            ]
        ) == 0
    daemon_payload = json.loads(stdout.getvalue())
    assert daemon_payload["summary"]["cycles_completed"] == 1
    assert daemon_payload["daemon"]["worker_id"] == "daemon-stage2"

    project_root = Path(__file__).resolve().parents[2]
    assert (project_root / "docs" / "releases" / "migration-0.9.0.md").exists()
    assert (project_root / "docs" / "cli" / "ceos-help.snapshot.txt").exists()
    assert (project_root / "docs" / "cli" / "ceos-maintenance-help.snapshot.txt").exists()
    assert (project_root / "deploy" / "observability" / "prometheus.yml").exists()
    assert (project_root / "deploy" / "observability" / "grafana-dashboard.json").exists()
    assert (project_root / "deploy" / "launchd" / "com.contractevidenceos.maintenance.plist").exists()
    assert (project_root / "deploy" / "systemd" / "ceos-maintenance.service").exists()
    assert (project_root / "scripts" / "install-maintenance-service.sh").exists()
    assert (project_root / "scripts" / "uninstall-maintenance-service.sh").exists()

    ceos_help_snapshot = (project_root / "docs" / "cli" / "ceos-help.snapshot.txt").read_text(encoding="utf-8")
    maintenance_help_snapshot = (project_root / "docs" / "cli" / "ceos-maintenance-help.snapshot.txt").read_text(encoding="utf-8")
    assert ceos_help_snapshot == build_ceos_parser().format_help()
    assert maintenance_help_snapshot == build_maintenance_parser().format_help()

    snapshot = json.loads((project_root / "docs" / "api" / "operator-v1.snapshot.json").read_text(encoding="utf-8"))
    contract = operator_api_contract()
    assert snapshot["http"]["routes"] == contract["http"]["routes"]
    assert snapshot["cli"]["commands"] == contract["cli"]["commands"]
