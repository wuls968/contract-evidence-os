from pathlib import Path

import pytest

from contract_evidence_os.api.operator import OperatorAPI
from contract_evidence_os.runtime.service import RuntimeInterrupted, RuntimeService


def _write_requirements(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "Audit history must never be deleted.",
                "Every important summary must cite evidence.",
                "Destructive actions require explicit approval.",
            ]
        ),
        encoding="utf-8",
    )


def test_multi_session_continuity_and_approval_resume(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    _write_requirements(attachment)
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")

    with pytest.raises(RuntimeInterrupted) as planned:
        service.run_task(
            goal="Read the attachment and summarize the mandatory constraints with evidence before publication.",
            attachments=[str(attachment)],
            preferences={"output_style": "structured"},
            prohibitions=["Do not delete audit history."],
            interrupt_after="planned",
        )

    task_id = planned.value.task_id
    planned_handoff = service.repository.latest_handoff_packet(task_id)
    assert planned_handoff is not None
    assert planned_handoff.next_recommended_actions
    assert service.repository.list_next_actions(task_id)
    assert service.repository.latest_context_compaction(task_id) is not None

    with pytest.raises(RuntimeInterrupted) as after_node:
        service.resume_task(task_id, interrupt_after="after_node_execute")

    assert after_node.value.task_id == task_id
    mid_handoff = service.repository.latest_handoff_packet(task_id)
    assert mid_handoff is not None
    assert "node-retrieve-source-0" in mid_handoff.completed_nodes
    assert service.repository.latest_workspace_snapshot(task_id) is not None

    awaiting = service.resume_task(task_id)
    assert awaiting.status == "awaiting_approval"

    pending = service.approval_inbox(task_id=task_id)
    assert len(pending) == 1
    assert pending[0].status == "pending"

    operator = OperatorAPI(storage_root=root)
    status = operator.task_status(task_id)
    assert status["status"] == "awaiting_approval"
    assert operator.handoff_packet(task_id).packet_id == service.repository.latest_handoff_packet(task_id).packet_id
    assert operator.open_questions(task_id)
    assert operator.next_actions(task_id)

    intervention = operator.intervene_task(
        task_id=task_id,
        action="force_checkpoint",
        operator="operator",
        reason="Capture explicit approval wait boundary.",
        payload={"phase": "approval_wait"},
    )
    assert intervention.action == "force_checkpoint"
    assert operator.checkpoints(task_id)

    decision = operator.decide_approval(
        request_id=pending[0].request_id,
        approver="operator",
        status="approved",
        rationale="Reviewed evidence and contract clause.",
    )
    assert decision.status == "approved"

    resumed = operator.resume_task(task_id)
    assert resumed.status == "completed"

    working_set = operator.continuity_working_set(task_id, role_name="Strategist")
    assert working_set.pending_approval_ids == []

    trace_bundle = operator.trace_bundle(task_id)
    assert trace_bundle["handoff"] is not None
    assert trace_bundle["telemetry"]
