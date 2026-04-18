"""Shell inspection and patch-adjacent execution tool."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.tools.models import ToolInvocation, ToolResult, ToolSpec


@dataclass
class ShellPatchTool:
    """Run non-destructive shell commands with typed receipts."""

    spec: ToolSpec = field(
        default_factory=lambda: ToolSpec(
            version="1.0",
            tool_id="shell-patch",
            name="shell_patch",
            description="Execute safe shell commands with dry-run support.",
            input_schema={"type": "object", "required": ["command", "cwd"]},
            output_schema={"type": "object", "required": ["stdout", "stderr", "exit_code"]},
            risk_level="moderate",
            permission_requirements=["read", "execute"],
            retry_policy={"max_attempts": 1},
            timeout_policy={"seconds": 20},
            audit_hooks=["record_shell_invocation"],
            evidence_hooks=["capture_stdout_excerpt"],
            validation_hooks=["safe_command_check"],
            mock_provider="mock-shell-provider",
            simulator_provider="sim-shell-provider",
        )
    )

    def run(
        self,
        command: list[str] | str,
        cwd: Path,
        destructive: bool = False,
        dry_run: bool = False,
    ) -> tuple[ToolInvocation, ToolResult]:
        rendered_command = command if isinstance(command, str) else " ".join(command)
        invocation = ToolInvocation(
            version="1.0",
            invocation_id=f"invoke-{uuid4().hex[:10]}",
            tool_id=self.spec.tool_id,
            actor="Builder",
            input_payload={"command": command, "cwd": str(cwd), "dry_run": dry_run},
            requested_at=utc_now(),
            correlation_id=f"shell:{cwd}:{rendered_command}",
            idempotency_key=f"shell_patch:{cwd}:{rendered_command}:{int(dry_run)}",
        )
        started_at = utc_now()

        if destructive:
            result = ToolResult(
                version="1.0",
                invocation_id=invocation.invocation_id,
                tool_id=self.spec.tool_id,
                status="failed",
                output_payload={"stdout": "", "stderr": "", "exit_code": 1},
                error="destructive commands require explicit approval",
                started_at=started_at,
                completed_at=utc_now(),
                correlation_id=invocation.correlation_id,
                provenance={"cwd": str(cwd), "command": rendered_command},
                confidence=1.0,
                provider_mode="live",
                deterministic=True,
                failure_classification="approval_required",
                suggested_follow_up_action="request approval or use dry_run",
            )
            return invocation, result

        if dry_run:
            result = ToolResult(
                version="1.0",
                invocation_id=invocation.invocation_id,
                tool_id=self.spec.tool_id,
                status="success",
                output_payload={"stdout": "", "stderr": "", "exit_code": 0, "dry_run": True},
                error=None,
                started_at=started_at,
                completed_at=utc_now(),
                correlation_id=invocation.correlation_id,
                provenance={"cwd": str(cwd), "command": rendered_command},
                confidence=1.0,
                provider_mode="simulator",
                deterministic=True,
                suggested_follow_up_action="review dry-run output before live execution",
            )
            return invocation, result

        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            shell=isinstance(command, str),
            check=False,
        )
        status = "success" if completed.returncode == 0 else "failed"
        result = ToolResult(
            version="1.0",
            invocation_id=invocation.invocation_id,
            tool_id=self.spec.tool_id,
            status=status,
            output_payload={
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "exit_code": completed.returncode,
            },
            error=None if status == "success" else completed.stderr.strip() or "shell command failed",
            started_at=started_at,
            completed_at=utc_now(),
            correlation_id=invocation.correlation_id,
            provenance={"cwd": str(cwd), "command": rendered_command},
            confidence=1.0,
            provider_mode="live",
            deterministic=True,
            failure_classification=None if status == "success" else "command_failed",
            suggested_follow_up_action="inspect stderr and retry or choose a safer fallback",
        )
        return invocation, result
