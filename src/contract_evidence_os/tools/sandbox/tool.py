"""Python execution sandbox."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.tools.models import ToolInvocation, ToolResult, ToolSpec


@dataclass
class CodeExecutionSandbox:
    """Run Python snippets in a subprocess and capture outputs."""

    spec: ToolSpec = field(
        default_factory=lambda: ToolSpec(
            version="1.0",
            tool_id="python-sandbox",
            name="sandbox_exec",
            description="Run Python snippets for deterministic recomputation.",
            input_schema={"type": "object", "required": ["code"]},
            output_schema={"type": "object", "required": ["stdout", "stderr", "exit_code"]},
            risk_level="moderate",
            permission_requirements=["execute"],
            retry_policy={"max_attempts": 1},
            timeout_policy={"seconds": 20},
            audit_hooks=["record_sandbox_run"],
            evidence_hooks=["capture_computation_output"],
            validation_hooks=["sandbox_policy_check"],
            mock_provider="mock-sandbox-provider",
            simulator_provider="sim-sandbox-provider",
        )
    )

    def run_python(self, code: str, cwd: Path) -> tuple[ToolInvocation, ToolResult]:
        invocation = ToolInvocation(
            version="1.0",
            invocation_id=f"invoke-{uuid4().hex[:10]}",
            tool_id=self.spec.tool_id,
            actor="Verifier",
            input_payload={"code": code, "cwd": str(cwd)},
            requested_at=utc_now(),
            correlation_id=f"sandbox:{cwd}:{hash(code)}",
            idempotency_key=f"python_sandbox:{cwd}:{hash(code)}",
        )
        started_at = utc_now()
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(cwd),
            capture_output=True,
            text=True,
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
            error=None if status == "success" else completed.stderr.strip() or "sandbox execution failed",
            started_at=started_at,
            completed_at=utc_now(),
            correlation_id=invocation.correlation_id,
            provenance={"executor": "python", "cwd": str(cwd)},
            confidence=1.0,
            provider_mode="live",
            deterministic=True,
            failure_classification=None if status == "success" else "sandbox_execution_failed",
            suggested_follow_up_action="inspect stderr and rerun inside verifier lane",
        )
        return invocation, result
