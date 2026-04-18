from pathlib import Path

from contract_evidence_os.api.operator import OperatorAPI
from contract_evidence_os.runtime.service import RuntimeService


def test_operator_can_consolidate_rebuild_and_delete_amos_memory_scope(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text(
        "\n".join(
            [
                "Audit history must never be deleted.",
                "Every summary must cite source evidence.",
            ]
        ),
        encoding="utf-8",
    )
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    result = service.run_task(
        goal="Read the attachment and summarize the mandatory constraints.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )

    api = OperatorAPI(storage_root=root)
    before = api.memory_state(result.task_id)
    assert before["raw_episodes"]
    assert before["semantic_facts"]

    consolidation = api.consolidate_memory(result.task_id, reason="nightly consolidation")
    assert consolidation["created_durative_count"] >= 0

    rebuild = api.rebuild_memory(result.task_id, reason="refresh memory indexes")
    assert rebuild["rebuild_status"] == "completed"

    deletion = api.delete_memory_scope(result.task_id, actor="user", reason="forget this task memory")
    assert deletion["deleted_record_count"] >= 1

    after = api.memory_state(result.task_id)
    assert after["raw_episodes"] == []
    assert after["semantic_facts"] == []
    assert after["dashboard"] == []
