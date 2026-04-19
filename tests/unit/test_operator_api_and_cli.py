import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from contract_evidence_os.api.cli import main
from contract_evidence_os.api.operator import OperatorAPI
from contract_evidence_os.runtime.service import RuntimeService


def _build_awaiting_approval_task(tmp_path: Path) -> tuple[Path, str]:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text(
        "\n".join(
            [
                "Audit history must never be deleted.",
                "Every important summary must cite evidence.",
                "Destructive actions require explicit approval.",
            ]
        ),
        encoding="utf-8",
    )
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    result = service.run_task(
        goal="Read the attachment and summarize the mandatory constraints with evidence before publication.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )
    assert result.status == "awaiting_approval"
    return root, result.task_id


def test_operator_api_exposes_dashboard_and_handoff_state(tmp_path: Path) -> None:
    root, task_id = _build_awaiting_approval_task(tmp_path)
    api = OperatorAPI(storage_root=root)

    dashboard = api.task_dashboard(task_id)

    assert dashboard["status"] == "awaiting_approval"
    assert dashboard["current_phase"] == "awaiting_approval"
    assert dashboard["handoff_packet"]["task_id"] == task_id
    assert dashboard["open_questions"]
    assert dashboard["next_actions"]
    assert dashboard["approval_queue"]


def test_cli_can_inspect_handoff_and_open_questions(tmp_path: Path) -> None:
    root, task_id = _build_awaiting_approval_task(tmp_path)

    handoff_stdout = StringIO()
    with redirect_stdout(handoff_stdout):
        assert main(["--storage-root", str(root), "inspect-handoff", "--task-id", task_id]) == 0
    handoff_payload = json.loads(handoff_stdout.getvalue())
    assert handoff_payload["task_id"] == task_id

    questions_stdout = StringIO()
    with redirect_stdout(questions_stdout):
        assert main(["--storage-root", str(root), "inspect-open-questions", "--task-id", task_id]) == 0
    questions_payload = json.loads(questions_stdout.getvalue())
    assert questions_payload


def test_cli_doctor_reports_console_readiness(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.local.json").write_text("{}", encoding="utf-8")

    doctor_stdout = StringIO()
    with redirect_stdout(doctor_stdout):
        assert main(["--storage-root", str(root), "doctor"]) == 0

    payload = json.loads(doctor_stdout.getvalue())
    assert "startup" in payload
    assert "system" in payload
    assert "config" in payload
    assert "provider_check" in payload
    assert "frontend" in payload
