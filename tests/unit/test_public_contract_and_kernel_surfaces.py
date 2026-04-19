import json
import os
import stat
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from contract_evidence_os.api.cli import main
from contract_evidence_os.api.operator import OperatorAPI
from contract_evidence_os.runtime.service import RuntimeService


def _write_harness(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "import sys",
                "",
                "args = sys.argv[1:]",
                "if args == ['--help']:",
                "    print('Usage: cli-anything-demo [--json] <command>')",
                "    print('')",
                "    print('Commands:')",
                "    print('  inspect inspect the current app state')",
                "    print('  export-report export a structured report')",
                "    print('  delete-project remove a project permanently')",
                "    raise SystemExit(0)",
                "emit_json = False",
                "if args and args[0] == '--json':",
                "    emit_json = True",
                "    args = args[1:]",
                "command = args[0] if args else 'inspect'",
                "payload = {",
                "    'command': command,",
                "    'status': 'ok',",
                "    'artifact': '/tmp/demo-artifact.txt',",
                "    'summary': f'executed {command}',",
                "}",
                "if emit_json:",
                "    print(json.dumps(payload))",
                "else:",
                "    print(f'executed {command}')",
                "",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _build_runtime_with_harness(tmp_path: Path) -> tuple[Path, str, str]:
    attachment = tmp_path / "notes.txt"
    attachment.write_text(
        "Remember the AMOS kernel should stay source-grounded and software control must remain governed.\n",
        encoding="utf-8",
    )
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    result = service.run_task(
        goal="Read the note and summarize the memory and software-control constraints.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not erase audit lineage."],
    )
    service.memory.retrieve_evidence_pack(query="memory and software constraints", scope_key=result.task_id)
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


def test_operator_api_exposes_memory_kernel_and_software_control_views(tmp_path: Path) -> None:
    root, task_id, harness_id = _build_runtime_with_harness(tmp_path)
    api = OperatorAPI(storage_root=root)

    kernel = api.memory_kernel_state(task_id)
    assert kernel["task_id"] == task_id
    assert kernel["write_receipts"]
    assert kernel["evidence_packs"]
    assert "consolidation_policy" in kernel
    assert "repair_policy" in kernel
    assert kernel["timeline_view"]["scope_key"] == task_id
    assert kernel["project_state_view"]["scope_key"] == task_id

    manifest = api.software_harness_manifest(harness_id)
    assert manifest["manifest"]["harness_id"] == harness_id
    assert manifest["manifest"]["app_capability"]["software_name"] == "demo"
    assert manifest["manifest"]["commands"]
    assert manifest["manifest"]["risk_classes"]

    receipts = api.software_action_receipts(task_id=task_id)
    assert receipts["items"]
    assert receipts["items"][0]["harness_id"] == harness_id

    report = api.system_report()
    assert "memory" in report
    assert "software_control" in report
    assert report["memory"]["write_receipt_count"] >= 1
    assert report["software_control"]["action_receipt_count"] >= 1


def test_cli_exposes_public_contract_kernel_and_software_commands(tmp_path: Path) -> None:
    root, task_id, harness_id = _build_runtime_with_harness(tmp_path)

    stdout = StringIO()
    with redirect_stdout(stdout):
        assert main(["--storage-root", str(root), "system-report"]) == 0
    system_payload = json.loads(stdout.getvalue())
    assert "memory" in system_payload
    assert "software_control" in system_payload

    stdout = StringIO()
    with redirect_stdout(stdout):
        assert main(["--storage-root", str(root), "memory-kernel-state", "--task-id", task_id]) == 0
    kernel_payload = json.loads(stdout.getvalue())
    assert kernel_payload["task_id"] == task_id
    assert kernel_payload["write_receipts"]

    stdout = StringIO()
    with redirect_stdout(stdout):
        assert main(["--storage-root", str(root), "software-harness-manifest", "--harness-id", harness_id]) == 0
    manifest_payload = json.loads(stdout.getvalue())
    assert manifest_payload["manifest"]["harness_id"] == harness_id

    stdout = StringIO()
    with redirect_stdout(stdout):
        assert main(["--storage-root", str(root), "software-action-receipts", "--task-id", task_id]) == 0
    receipt_payload = json.loads(stdout.getvalue())
    assert receipt_payload["items"]
