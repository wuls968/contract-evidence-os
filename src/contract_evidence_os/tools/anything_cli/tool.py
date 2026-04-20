"""Governed adapter for installed CLI-Anything harness executables."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.tools.anything_cli.models import (
    SoftwareCommandDescriptor,
    SoftwareControlPolicy,
    SoftwareHarnessRecord,
    SoftwareHarnessValidation,
)
from contract_evidence_os.tools.models import ToolInvocation, ToolResult


@dataclass
class CLIAnythingHarnessTool:
    """Discover, validate, and invoke CLI-Anything harnesses safely."""

    def discover(self, search_roots: list[Path | str] | None = None) -> list[SoftwareHarnessRecord]:
        candidates: list[Path] = []
        seen: set[str] = set()
        roots = [Path(item) for item in search_roots or []]
        for root in roots:
            if not root.exists():
                continue
            if root.is_file() and root.name.startswith("cli-anything-"):
                resolved = str(root.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    candidates.append(root)
                continue
            for path in sorted(root.iterdir()):
                if path.is_file() and path.name.startswith("cli-anything-") and os.access(path, os.X_OK):
                    resolved = str(path.resolve())
                    if resolved not in seen:
                        seen.add(resolved)
                        candidates.append(path)
        for entry in os.environ.get("PATH", "").split(os.pathsep):
            if not entry:
                continue
            root = Path(entry)
            if not root.exists():
                continue
            for path in sorted(root.glob("cli-anything-*")):
                if path.is_file() and os.access(path, os.X_OK):
                    resolved = str(path.resolve())
                    if resolved not in seen:
                        seen.add(resolved)
                        candidates.append(path)
        return [self._describe_harness(path, discovery_mode="discovered") for path in candidates]

    def register(
        self,
        *,
        executable_path: str,
        discovery_mode: str = "manual",
        policy_overrides: dict[str, object] | None = None,
    ) -> tuple[SoftwareHarnessRecord, list[SoftwareCommandDescriptor], SoftwareControlPolicy]:
        executable = Path(executable_path).expanduser().resolve()
        harness = self._describe_harness(executable, discovery_mode=discovery_mode)
        commands = self._extract_commands(harness)
        harness.command_count = len(commands)
        policy = self._build_policy(harness, overrides=policy_overrides)
        return harness, commands, policy

    def validate(self, harness: SoftwareHarnessRecord) -> SoftwareHarnessValidation:
        help_output = self._run_help(Path(harness.executable_path))
        checks = {
            "help_available": help_output.returncode == 0,
            "json_mode_detected": "--json" in help_output.stdout,
            "commands_detected": "Commands:" in help_output.stdout,
            "repl_mode_documented": "Usage:" in help_output.stdout,
        }
        issues = [name for name, passed in checks.items() if not passed]
        return SoftwareHarnessValidation(
            version="1.0",
            validation_id=f"software-validation-{uuid4().hex[:10]}",
            harness_id=harness.harness_id,
            status="passed" if not issues else "failed",
            checks=checks,
            issues=issues,
            executable_version="unknown",
        )

    def invoke(
        self,
        *,
        harness: SoftwareHarnessRecord,
        policy: SoftwareControlPolicy,
        command_path: list[str],
        arguments: list[str],
        actor: str,
        approved: bool,
        dry_run: bool = False,
    ) -> tuple[ToolInvocation, ToolResult, dict[str, object] | None]:
        executable = Path(harness.executable_path)
        rendered_command = " ".join([str(executable), *command_path, *arguments])
        invocation = ToolInvocation(
            version="1.0",
            invocation_id=f"invoke-{uuid4().hex[:10]}",
            tool_id=harness.executable_name,
            actor=actor,
            input_payload={"command_path": command_path, "arguments": arguments, "harness_id": harness.harness_id, "dry_run": dry_run},
            requested_at=utc_now(),
            correlation_id=f"{harness.harness_id}:{':'.join(command_path)}",
            idempotency_key=f"{harness.harness_id}:{' '.join(command_path)}:{' '.join(arguments)}:{int(dry_run)}",
        )
        started_at = utc_now()
        risk_level, approval_required, blocked = policy.classify(command_path)
        if blocked:
            result = ToolResult(
                version="1.0",
                invocation_id=invocation.invocation_id,
                tool_id=invocation.tool_id,
                status="failed",
                output_payload={"stdout": "", "stderr": "", "command_path": command_path},
                error="command blocked by software control policy",
                started_at=started_at,
                completed_at=utc_now(),
                correlation_id=invocation.correlation_id,
                provenance={"executable_path": str(executable), "command": rendered_command, "policy": policy.policy_id},
                confidence=1.0,
                provider_mode="live",
                deterministic=True,
                failure_classification="policy_blocked",
                suggested_follow_up_action="choose a safer command path or adjust the harness policy",
            )
            return invocation, result, None
        if approval_required and not approved:
            result = ToolResult(
                version="1.0",
                invocation_id=invocation.invocation_id,
                tool_id=invocation.tool_id,
                status="failed",
                output_payload={"stdout": "", "stderr": "", "command_path": command_path},
                error="software control approval required",
                started_at=started_at,
                completed_at=utc_now(),
                correlation_id=invocation.correlation_id,
                provenance={"executable_path": str(executable), "command": rendered_command, "policy": policy.policy_id},
                confidence=1.0,
                provider_mode="live",
                deterministic=True,
                failure_classification="approval_required",
                suggested_follow_up_action="request approval and retry with approved=True",
            )
            return invocation, result, None
        if dry_run:
            result = ToolResult(
                version="1.0",
                invocation_id=invocation.invocation_id,
                tool_id=invocation.tool_id,
                status="success",
                output_payload={"stdout": "", "stderr": "", "command_path": command_path, "dry_run": True},
                error=None,
                started_at=started_at,
                completed_at=utc_now(),
                correlation_id=invocation.correlation_id,
                provenance={"executable_path": str(executable), "command": rendered_command, "policy": policy.policy_id},
                confidence=1.0,
                provider_mode="simulator",
                deterministic=True,
                suggested_follow_up_action="review the planned command before live execution",
            )
            return invocation, result, None

        command = [str(executable)]
        if policy.require_json_output:
            command.append("--json")
        command.extend(command_path)
        command.extend(arguments)
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=policy.default_timeout_seconds)
        status = "success" if completed.returncode == 0 else "failed"
        parsed: dict[str, object] | None = None
        failure_classification = None if status == "success" else "command_failed"
        if completed.stdout.strip():
            try:
                parsed = json.loads(completed.stdout)
            except json.JSONDecodeError:
                if policy.require_json_output and status == "success":
                    status = "failed"
                    failure_classification = "structured_output_failure"
        artifacts: list[str] = []
        if isinstance(parsed, dict):
            artifact = parsed.get("artifact")
            if isinstance(artifact, str):
                artifacts.append(artifact)
            listed = parsed.get("artifacts")
            if isinstance(listed, list):
                artifacts.extend([str(item) for item in listed])
        result = ToolResult(
            version="1.0",
            invocation_id=invocation.invocation_id,
            tool_id=invocation.tool_id,
            status=status,
            output_payload={
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "exit_code": completed.returncode,
                "parsed_json": parsed,
                "command_path": command_path,
            },
            error=None if status == "success" else completed.stderr.strip() or "software control command failed",
            started_at=started_at,
            completed_at=utc_now(),
            correlation_id=invocation.correlation_id,
            provenance={
                "source_kind": harness.source_kind,
                "harness_id": harness.harness_id,
                "executable_path": str(executable),
                "command": rendered_command,
                "policy": policy.policy_id,
                "risk_level": risk_level,
            },
            confidence=0.95 if status == "success" else 0.7,
            provider_mode="live",
            deterministic=True,
            failure_classification=failure_classification,
            suggested_follow_up_action="inspect parsed_json and artifacts for downstream evidence capture" if status == "success" else "inspect stderr, harness policy, and command selection",
            artifact_refs=artifacts,
        )
        return invocation, result, parsed

    def _describe_harness(self, executable: Path, discovery_mode: str) -> SoftwareHarnessRecord:
        name = executable.name
        software_name = name.removeprefix("cli-anything-") if name.startswith("cli-anything-") else name
        harness_root = self._infer_harness_root(executable)
        skill_path = self._infer_skill_path(harness_root, software_name)
        help_output = self._run_help(executable)
        supports_json = "--json" in help_output.stdout
        supports_repl = "Usage:" in help_output.stdout
        commands = self._parse_help_commands(help_output.stdout)
        return SoftwareHarnessRecord(
            version="1.0",
            harness_id=f"software-harness-{software_name}",
            source_kind="cli-anything",
            software_name=software_name,
            executable_name=name,
            executable_path=str(executable),
            harness_root=str(harness_root),
            skill_path=skill_path,
            discovery_mode=discovery_mode,
            status="registered" if discovery_mode == "manual" else "discovered",
            supports_json=supports_json,
            supports_repl=supports_repl,
            default_risk_level="moderate",
            command_count=len(commands),
            metadata={"help_excerpt": help_output.stdout.splitlines()[:12]},
        )

    def _extract_commands(self, harness: SoftwareHarnessRecord) -> list[SoftwareCommandDescriptor]:
        help_output = self._run_help(Path(harness.executable_path))
        commands: list[SoftwareCommandDescriptor] = []
        for command_name, description in self._parse_help_commands(help_output.stdout):
            risk_level = "low"
            approval_required = False
            lowered = command_name.lower()
            if any(token in lowered for token in {"delete", "remove", "drop", "erase"}):
                risk_level = "destructive"
                approval_required = True
            elif any(token in lowered for token in {"edit", "write", "export"}):
                risk_level = "moderate"
            commands.append(
                SoftwareCommandDescriptor(
                    version="1.0",
                    command_id=f"{harness.harness_id}:{command_name}",
                    harness_id=harness.harness_id,
                    command_path=[command_name],
                    description=description,
                    risk_level=risk_level,
                    approval_required=approval_required,
                    supports_json=harness.supports_json,
                )
            )
        return commands

    def _build_policy(
        self,
        harness: SoftwareHarnessRecord,
        overrides: dict[str, object] | None,
    ) -> SoftwareControlPolicy:
        payload = {
            "version": "1.0",
            "policy_id": f"software-policy-{harness.software_name}",
            "harness_id": harness.harness_id,
            "source_kind": harness.source_kind,
            "require_json_output": harness.supports_json,
            "allow_repl": False,
            "high_risk_patterns": ["delete", "remove", "overwrite", "publish", "send", "submit"],
            "destructive_patterns": ["delete-layer", "delete", "remove-project", "drop-database", "format-disk"],
            "blocked_patterns": ["format-disk", "factory-reset"],
            "default_timeout_seconds": 20,
            "evidence_capture_mode": "summary_and_json",
        }
        if overrides:
            payload.update(overrides)
        return SoftwareControlPolicy(**payload)

    def _run_help(self, executable: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(executable), "--help"], capture_output=True, text=True, check=False)

    def _infer_harness_root(self, executable: Path) -> Path:
        direct_parent = executable.parent
        if (direct_parent / "setup.py").exists():
            return direct_parent
        for candidate in executable.parents:
            if (candidate / "setup.py").exists():
                return candidate
            if (candidate / "agent-harness" / "setup.py").exists():
                return candidate / "agent-harness"
        return direct_parent

    def _infer_skill_path(self, harness_root: Path, software_name: str) -> str:
        package_skill = harness_root / "cli_anything" / software_name / "skills" / "SKILL.md"
        if package_skill.exists():
            return str(package_skill)
        global_skill = Path.home() / ".codex" / "skills" / "cli-anything" / "SKILL.md"
        return str(global_skill) if global_skill.exists() else ""

    def _parse_help_commands(self, text: str) -> list[tuple[str, str]]:
        commands: list[tuple[str, str]] = []
        in_commands = False
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if not line:
                continue
            if line.strip() == "Commands:":
                in_commands = True
                continue
            if not in_commands:
                continue
            if not raw_line.startswith("  "):
                break
            parts = line.split()
            if not parts:
                continue
            command = parts[0]
            description = " ".join(parts[1:]).strip()
            commands.append((command, description))
        return commands
