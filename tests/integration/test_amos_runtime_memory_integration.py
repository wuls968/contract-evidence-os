from pathlib import Path

from contract_evidence_os.runtime.service import RuntimeService


def test_runtime_persists_amos_memory_layers_for_completed_tasks(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text(
        "\n".join(
            [
                "Audit history must never be deleted.",
                "Every summary must cite source evidence.",
                "Destructive actions require explicit approval.",
            ]
        ),
        encoding="utf-8",
    )

    runtime = RuntimeService(storage_root=tmp_path / "runtime")
    result = runtime.run_task(
        goal="Read the attachment and summarize the mandatory constraints.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )

    raw_episodes = runtime.memory.list_raw_episodes(task_id=result.task_id)
    assert raw_episodes

    working = runtime.memory.latest_working_memory_snapshot(result.task_id)
    assert working is not None
    assert working.active_goal

    facts = runtime.memory.list_temporal_semantic_facts(scope_key=result.task_id)
    assert facts
    assert any("delete audit history" in fact.object.lower() or "structured" in fact.object.lower() for fact in facts)

    pack = runtime.memory.retrieve_evidence_pack(
        query="什么约束要求不能删除审计历史？",
        scope_key=result.task_id,
    )
    assert pack.raw_episode_ids
    assert pack.semantic_fact_ids
    assert pack.matrix_pointer_ids

    dashboard = runtime.memory.dashboard(scope_key=result.task_id)
    assert dashboard
    assert any(item.source_kind in {"semantic_fact", "raw_episode", "procedural_pattern"} for item in dashboard)
