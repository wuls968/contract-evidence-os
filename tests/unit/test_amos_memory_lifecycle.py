from datetime import UTC, datetime
from pathlib import Path

from contract_evidence_os.memory.matrix import MemoryMatrix
from contract_evidence_os.storage.repository import SQLiteRepository


def _dt(day: int) -> datetime:
    return datetime(2026, 4, day, 12, 0, tzinfo=UTC)


def test_amos_memory_tombstones_scope_and_hides_deleted_material(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(repository=repository)

    episode = matrix.record_raw_episode(
        task_id="task-100",
        episode_type="task_request",
        actor="user",
        scope_key="project:amos-delete",
        project_id="amos-delete",
        content={"text": "记住这个项目偏好结构化输出。"},
        source="conversation",
        consent="granted",
        trust=1.0,
        dialogue_time=_dt(17),
        event_time_start=_dt(17),
    )
    candidate = matrix.create_candidate(
        task_id="task-100",
        scope_key="project:amos-delete",
        lane="semantic",
        summary="user prefers structured output in the amos-delete project",
        content={
            "subject": "user",
            "predicate": "prefers_output_style",
            "object": "structured",
            "head": "preference",
        },
        sources=[episode.episode_id],
    )
    matrix.govern_candidate(candidate.candidate_id)
    matrix.consolidate_candidate(candidate.candidate_id)

    before = matrix.retrieve_evidence_pack(query="我喜欢什么输出风格？", scope_key="project:amos-delete")
    assert before.raw_episode_ids
    assert before.semantic_fact_ids
    assert before.matrix_pointer_ids

    deletion = matrix.tombstone_scope(
        scope_key="project:amos-delete",
        actor="user",
        reason="user requested forgetting this project scope",
    )
    assert deletion.deleted_record_count >= 3
    assert matrix.list_memory_tombstones(scope_key="project:amos-delete")

    after = matrix.retrieve_evidence_pack(query="我喜欢什么输出风格？", scope_key="project:amos-delete")
    assert after.raw_episode_ids == []
    assert after.semantic_fact_ids == []
    assert after.matrix_pointer_ids == []
    assert matrix.dashboard(scope_key="project:amos-delete") == []


def test_amos_sleep_time_consolidation_creates_durative_memory_and_rebuilds_index(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(repository=repository)

    first = matrix.create_candidate(
        task_id="task-101",
        scope_key="user:amos",
        lane="semantic",
        summary="user has been working on AMOS memory design",
        content={
            "subject": "user",
            "predicate": "working_on",
            "object": "AMOS memory design",
            "valid_from": _dt(10).isoformat(),
            "head": "goal",
        },
        sources=["episode-early"],
    )
    second = matrix.create_candidate(
        task_id="task-101",
        scope_key="user:amos",
        lane="semantic",
        summary="user is still working on AMOS memory design",
        content={
            "subject": "user",
            "predicate": "working_on",
            "object": "AMOS memory design",
            "valid_from": _dt(17).isoformat(),
            "head": "goal",
        },
        sources=["episode-late"],
    )
    matrix.govern_candidate(first.candidate_id)
    matrix.consolidate_candidate(first.candidate_id)
    matrix.govern_candidate(second.candidate_id)
    matrix.consolidate_candidate(second.candidate_id)

    consolidation = matrix.run_sleep_consolidation(
        scope_key="user:amos",
        reason="nightly temporal consolidation",
    )
    assert consolidation.created_durative_count >= 1
    assert consolidation.superseded_fact_count >= 1
    duratives = matrix.list_durative_memories(scope_key="user:amos")
    assert duratives
    assert any("working_on" in item.predicate for item in duratives)

    rebuild = matrix.rebuild_indexes(scope_key="user:amos", reason="refresh after consolidation")
    assert rebuild.rebuilt_pointer_count >= 1
    pack = matrix.retrieve_evidence_pack(query="我最近一直在做什么？", scope_key="user:amos")
    assert pack.semantic_fact_ids
    assert pack.matrix_pointer_ids
