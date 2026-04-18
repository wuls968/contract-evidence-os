from pathlib import Path

from contract_evidence_os.tools.sandbox.tool import CodeExecutionSandbox
from contract_evidence_os.tools.shell.tool import ShellPatchTool


def test_shell_tool_executes_safe_command(tmp_path: Path) -> None:
    tool = ShellPatchTool()
    invocation, result = tool.run(["pwd"], cwd=tmp_path)

    assert invocation.tool_id == "shell-patch"
    assert result.status == "success"
    assert str(tmp_path) in result.output_payload["stdout"]


def test_sandbox_executes_python_code(tmp_path: Path) -> None:
    sandbox = CodeExecutionSandbox()
    invocation, result = sandbox.run_python("print('sandbox-ok')", cwd=tmp_path)

    assert invocation.tool_id == "python-sandbox"
    assert result.status == "success"
    assert "sandbox-ok" in result.output_payload["stdout"]
