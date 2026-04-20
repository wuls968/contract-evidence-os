from pathlib import Path

from contract_evidence_os.evals.harness import EvaluationHarness
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
    print("  status")
    print("  delete-layer")
    sys.exit(0)

json_mode = False
if argv and argv[0] == "--json":
    json_mode = True
    argv = argv[1:]

if argv[0] == "status":
    print(json.dumps({"status": "ready", "artifact": "/tmp/demo-artifact.json"}) if json_mode else "ready")
    sys.exit(0)
if argv[0] == "delete-layer":
    print(json.dumps({"status": "deleted"}) if json_mode else "deleted")
    sys.exit(0)
sys.exit(2)
""",
        encoding="utf-8",
    )
    harness.chmod(0o755)
    return harness


def test_software_control_eval_compares_governed_and_permissive_policies(tmp_path: Path) -> None:
    harness_path = _write_demo_harness(tmp_path)

    governed = RuntimeService(storage_root=tmp_path / "governed")
    permissive = RuntimeService(storage_root=tmp_path / "permissive")

    governed.register_cli_anything_harness(executable_path=str(harness_path))
    permissive.register_cli_anything_harness(
        executable_path=str(harness_path),
        policy_overrides={"high_risk_patterns": [], "destructive_patterns": [], "blocked_patterns": []},
    )

    reports = EvaluationHarness().compare_software_control_strategies(
        runtimes={"governed": governed, "permissive": permissive},
        commands=[
            {"command_path": ["status"], "arguments": []},
            {"command_path": ["delete-layer"], "arguments": []},
        ],
    )

    assert "governed" in reports
    assert "permissive" in reports
    assert "approval_gate_preservation_rate" in reports["governed"].metrics
    assert "software_control_completion_rate" in reports["permissive"].metrics
