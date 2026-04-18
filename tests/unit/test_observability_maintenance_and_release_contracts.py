import json
import stat
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from contract_evidence_os.api.cli import main as ceos_main
from contract_evidence_os.api.contracts import operator_api_contract
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
                "    print('Usage: cli-anything-demo [--json] <command>')",
                "    print('')",
                "    print('Commands:')",
                "    print('  inspect inspect the current app state')",
                "    print('  delete-project remove a project permanently')",
                "    raise SystemExit(0)",
                "emit_json = False",
                "if args and args[0] == '--json':",
                "    emit_json = True",
                "    args = args[1:]",
                "command = args[0] if args else 'inspect'",
                "payload = {'command': command, 'status': 'ok', 'artifact': '/tmp/demo-artifact.txt'}",
                "print(json.dumps(payload) if emit_json else command)",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _build_runtime(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "runtime"
    attachment = tmp_path / "note.txt"
    attachment.write_text("Expose metrics, daemon maintenance, and software reports.\n", encoding="utf-8")
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    result = service.run_task(
        goal="Read the note and summarize the operator-reporting requirements.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not erase audit lineage."],
    )
    service.memory.retrieve_evidence_pack(query="metrics and maintenance", scope_key=result.task_id)
    harness = tmp_path / "cli-anything-demo"
    _write_harness(harness)
    registered = service.register_cli_anything_harness(executable_path=str(harness))
    harness_id = str(registered["harness"]["harness_id"])
    invoke = service.invoke_cli_anything_harness(
        harness_id=harness_id,
        command_path=["inspect"],
        arguments=[],
        actor="tester",
        task_id=result.task_id,
        approved=True,
        dry_run=False,
    )
    assert invoke["status"] == "completed"
    return root, result.task_id, harness_id


def test_operator_cli_and_maintenance_entrypoints_expose_metrics_reports_and_daemon_cycle(tmp_path: Path) -> None:
    root, task_id, harness_id = _build_runtime(tmp_path)
    api = OperatorAPI(storage_root=root)

    metrics = api.metrics_report()
    assert "maintenance" in metrics
    assert "software_control" in metrics
    assert "amos" in metrics
    assert "controller_versions" in metrics["amos"]

    software = api.software_control_report()
    assert software["summary"]["harness_count"] >= 1
    assert software["summary"]["action_receipt_count"] >= 1
    assert any(item["harness_id"] == harness_id for item in software["manifests"])

    daemon = api.run_resident_maintenance_daemon(
        task_id=task_id,
        worker_id="daemon-a",
        host_id="host-a",
        actor="runtime-admin",
        cycles=1,
    )
    assert daemon["worker"]["worker_id"] == "daemon-a"
    assert daemon["summary"]["cycles_completed"] == 1
    assert "reclaimed_workers" in daemon

    stdout = StringIO()
    with redirect_stdout(stdout):
        assert ceos_main(["--storage-root", str(root), "metrics-report"]) == 0
    cli_metrics = json.loads(stdout.getvalue())
    assert "maintenance" in cli_metrics

    stdout = StringIO()
    with redirect_stdout(stdout):
        assert ceos_main(["--storage-root", str(root), "software-control-report"]) == 0
    cli_software = json.loads(stdout.getvalue())
    assert cli_software["summary"]["harness_count"] >= 1

    stdout = StringIO()
    with redirect_stdout(stdout):
        assert maintenance_main(
            [
                "--storage-root",
                str(root),
                "--run-background-maintenance",
                "--maintenance-worker-id",
                "daemon-b",
                "--host-id",
                "host-b",
                "--daemon-cycles",
                "1",
            ]
        ) == 0
    maintenance_payload = json.loads(stdout.getvalue())
    assert maintenance_payload["summary"]["cycles_completed"] == 1


def test_release_assets_and_api_snapshot_align_with_runtime_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    release_note = (root / "docs" / "releases" / "0.9.0.md").read_text(encoding="utf-8")
    snapshot_text = (root / "docs" / "api" / "operator-v1.snapshot.json").read_text(encoding="utf-8")

    assert "0.9.0" in changelog
    assert "operator api v1" in release_note.lower()

    snapshot = json.loads(snapshot_text)
    contract = operator_api_contract()
    assert snapshot["version"] == contract["version"]
    assert snapshot["http"]["routes"] == contract["http"]["routes"]
    assert snapshot["cli"]["commands"] == contract["cli"]["commands"]
