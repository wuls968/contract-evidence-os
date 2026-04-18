import os
from pathlib import Path

from contract_evidence_os.storage.repository import SQLiteRepository
from contract_evidence_os.tools.anything_cli.models import (
    SoftwareBuildRequest,
    SoftwareControlBridgeConfig,
    SoftwareControlPolicy,
)
from contract_evidence_os.tools.anything_cli.tool import CLIAnythingHarnessTool


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
    print("  export-file   Export the current project")
    print("  delete-layer  Delete a layer")
    sys.exit(0)

json_mode = False
if argv and argv[0] == "--json":
    json_mode = True
    argv = argv[1:]

command = argv[0]
if command == "status":
    payload = {"status": "ready", "software": "demo", "artifacts": ["/tmp/demo-status.json"]}
    print(json.dumps(payload) if json_mode else "ready")
    sys.exit(0)
if command == "export-file":
    payload = {"status": "exported", "artifact": "/tmp/demo-export.txt"}
    print(json.dumps(payload) if json_mode else "exported")
    sys.exit(0)
if command == "delete-layer":
    payload = {"status": "deleted", "layer": "Background"}
    print(json.dumps(payload) if json_mode else "deleted")
    sys.exit(0)

print(json.dumps({"error": "unknown command"}) if json_mode else "unknown command", file=sys.stderr)
sys.exit(2)
""",
        encoding="utf-8",
    )
    harness.chmod(0o755)
    return harness


def test_cli_anything_tool_discovers_registers_validates_and_governs_invocations(
    tmp_path: Path,
    monkeypatch,
) -> None:
    harness_path = _write_demo_harness(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}")

    tool = CLIAnythingHarnessTool()
    discovered = tool.discover(search_roots=[tmp_path])

    assert len(discovered) == 1
    harness_record = discovered[0]
    assert harness_record.software_name == "demo"
    assert harness_record.executable_path == str(harness_path)
    assert harness_record.supports_json is True

    registered, commands, policy = tool.register(executable_path=str(harness_path))
    assert registered.harness_id == harness_record.harness_id
    assert {tuple(item.command_path) for item in commands} >= {
        ("status",),
        ("export-file",),
        ("delete-layer",),
    }
    assert policy.require_json_output is True

    validation = tool.validate(registered)
    assert validation.status == "passed"
    assert validation.checks["help_available"] is True
    assert validation.checks["json_mode_detected"] is True

    invocation, result, parsed = tool.invoke(
        harness=registered,
        policy=policy,
        command_path=["status"],
        arguments=[],
        actor="Builder",
        approved=False,
    )
    assert invocation.tool_id == "cli-anything-demo"
    assert result.status == "success"
    assert parsed is not None
    assert parsed["status"] == "ready"
    assert result.output_payload["parsed_json"]["software"] == "demo"

    _, blocked, _ = tool.invoke(
        harness=registered,
        policy=policy,
        command_path=["delete-layer"],
        arguments=[],
        actor="Builder",
        approved=False,
    )
    assert blocked.status == "failed"
    assert blocked.failure_classification == "approval_required"


def test_repository_round_trips_cli_anything_records(tmp_path: Path) -> None:
    repo = SQLiteRepository(tmp_path / "ceos.sqlite3")
    harness_path = _write_demo_harness(tmp_path)
    tool = CLIAnythingHarnessTool()
    harness, commands, policy = tool.register(executable_path=str(harness_path))

    repo.save_software_harness(harness)
    for command in commands:
        repo.save_software_command(command)
    repo.save_software_control_policy(policy)

    bridge = SoftwareControlBridgeConfig(
        version="1.0",
        bridge_id="bridge-001",
        source_kind="cli-anything",
        repo_path="/tmp/CLI-Anything",
        codex_skill_path="/Users/a0000/.codex/skills/cli-anything",
        enabled=True,
        builder_capabilities=["build", "refine", "validate"],
    )
    repo.save_software_control_bridge(bridge)

    build_request = SoftwareBuildRequest(
        version="1.0",
        build_request_id="build-001",
        source_kind="cli-anything",
        target="/Applications/Demo.app",
        mode="build",
        focus="status and export flows",
        repo_path="/tmp/CLI-Anything",
        status="pending",
    )
    repo.save_software_build_request(build_request)

    assert repo.load_software_harness(harness.harness_id) == harness
    assert repo.list_software_commands(harness.harness_id)
    assert repo.load_software_control_policy(harness.harness_id) == policy
    assert repo.list_software_control_bridges()[0] == bridge
    assert repo.list_software_build_requests()[0] == build_request


def test_software_control_policy_flags_high_risk_command_patterns() -> None:
    policy = SoftwareControlPolicy(
        version="1.0",
        policy_id="policy-001",
        harness_id="harness-demo",
        source_kind="cli-anything",
        require_json_output=True,
        allow_repl=False,
        high_risk_patterns=["delete", "remove"],
        destructive_patterns=["delete-layer"],
        blocked_patterns=["format-disk"],
        default_timeout_seconds=20,
        evidence_capture_mode="summary_and_json",
    )

    assert policy.classify(["status"]) == ("low", False, False)
    assert policy.classify(["delete-layer"]) == ("destructive", True, False)
    assert policy.classify(["format-disk"]) == ("blocked", True, True)
