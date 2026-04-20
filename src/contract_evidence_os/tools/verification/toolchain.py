"""Verification and evaluation toolchain."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from contract_evidence_os.tools.sandbox.tool import CodeExecutionSandbox
from contract_evidence_os.tools.shell.tool import ShellPatchTool


@dataclass
class VerificationToolchain:
    """Run test and recomputation checks through typed tools."""

    shell: ShellPatchTool = field(default_factory=ShellPatchTool)
    sandbox: CodeExecutionSandbox = field(default_factory=CodeExecutionSandbox)

    def run_pytest(self, cwd: Path, test_targets: list[str]) -> dict[str, object]:
        command = ["python3", "-m", "pytest", *test_targets]
        _, result = self.shell.run(command, cwd=cwd)
        return result.output_payload

    def recompute_python(self, cwd: Path, code: str) -> dict[str, object]:
        _, result = self.sandbox.run_python(code, cwd=cwd)
        return result.output_payload
