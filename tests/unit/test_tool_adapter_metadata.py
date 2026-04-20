from pathlib import Path

from contract_evidence_os.tools.files.tool import FileRetrievalTool
from contract_evidence_os.tools.sandbox.tool import CodeExecutionSandbox


def test_file_tool_emits_provenance_confidence_and_mode(tmp_path: Path) -> None:
    target = tmp_path / "requirements.txt"
    target.write_text("Audit history must never be deleted.\n", encoding="utf-8")

    tool = FileRetrievalTool()
    invocation, result, source = tool.invoke(str(target), actor="Researcher")

    assert source is not None
    assert result.status == "success"
    assert result.confidence is not None
    assert result.provenance["locator"] == str(target)
    assert result.provider_mode == "live"
    assert result.deterministic is True
    assert invocation.idempotency_key


def test_sandbox_tool_exposes_structured_failure_metadata(tmp_path: Path) -> None:
    sandbox = CodeExecutionSandbox()
    invocation, result = sandbox.run_python("raise RuntimeError('boom')", cwd=tmp_path)

    assert invocation.idempotency_key
    assert result.status == "failed"
    assert result.confidence == 1.0
    assert result.provider_mode == "live"
    assert result.provenance["executor"] == "python"
