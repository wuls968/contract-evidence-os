from pathlib import Path

import pytest

from contract_evidence_os.runtime.service import RuntimeInterrupted, RuntimeService


def test_runtime_resumes_from_interruption_without_duplicate_execution(tmp_path: Path) -> None:
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

    service = RuntimeService(storage_root=tmp_path / "runtime", routing_strategy="quality")

    with pytest.raises(RuntimeInterrupted) as interrupted:
        service.run_task(
            goal="Read the attachment and summarize the mandatory constraints with evidence.",
            attachments=[str(attachment)],
            preferences={"output_style": "structured"},
            prohibitions=["Do not delete audit history."],
            interrupt_after="after_node_execute",
        )

    task_id = interrupted.value.task_id
    assert service.get_task_status(task_id) == "interrupted"

    resumed = service.resume_task(task_id)

    assert resumed.status == "completed"
    assert service.get_task_status(task_id) == "completed"
    assert len(service.repository.list_tool_invocations(task_id)) == 1

    replay = service.replay_task(task_id)
    assert replay["delivery"]["facts"] == resumed.delivery["facts"]


def test_lineage_queries_and_incident_packets_are_usable(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text(
        "Audit history must never be deleted.\nEvery important summary must cite evidence.\n",
        encoding="utf-8",
    )

    service = RuntimeService(storage_root=tmp_path / "runtime", routing_strategy="quality")
    result = service.run_task(
        goal="Read the attachment and summarize the mandatory constraints with evidence.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )

    extraction = next(node for node in result.evidence_graph.nodes if node.node_type == "extraction")
    lineage = service.evidence_lineage(result.task_id, extraction.node_id)

    assert {node.node_type for node in lineage["nodes"]} == {"source", "extraction"}
    assert lineage["edges"]

    blocked = service.run_task(
        goal="Read the attachment and summarize the mandatory constraints with evidence.",
        attachments=[str(tmp_path / "missing.txt")],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )
    packet = service.incident_packet(blocked.task_id)

    assert blocked.status == "blocked"
    assert packet["task"]["status"] == "blocked"
    assert packet["incidents"]
    assert packet["audit_events"]
