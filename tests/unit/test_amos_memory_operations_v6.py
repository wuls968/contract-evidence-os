from datetime import UTC, datetime
from pathlib import Path

from contract_evidence_os.memory.matrix import MemoryMatrix
from contract_evidence_os.storage.repository import SQLiteRepository


def _dt(day: int) -> datetime:
    return datetime(2026, 4, day, 12, 0, tzinfo=UTC)


def test_amos_shared_artifact_backend_can_be_repaired_and_recommended(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(
        repository=repository,
        artifact_root=tmp_path / "artifacts",
        shared_artifact_root=tmp_path / "shared-artifacts",
    )
    scope_key = "project:shared-artifacts-v6"

    candidate = matrix.create_candidate(
        task_id="task-801",
        scope_key=scope_key,
        lane="semantic",
        summary="project requires shared memory index mirrors",
        content={
            "subject": "project",
            "predicate": "requires",
            "object": "shared_memory_index_mirrors",
            "head": "goal",
        },
        sources=["episode-shared-artifacts"],
    )
    matrix.govern_candidate(candidate.candidate_id)
    matrix.consolidate_candidate(candidate.candidate_id)
    matrix.rebuild_indexes(scope_key=scope_key, reason="materialize mirrored indexes")

    shared_artifacts = [item for item in matrix.list_memory_artifacts(scope_key=scope_key) if item.backend_kind == "shared_fs"]
    assert shared_artifacts
    Path(shared_artifacts[0].path).unlink()

    health = matrix.artifact_backend_health(scope_key=scope_key)
    recommendation = matrix.recommend_memory_maintenance(scope_key=scope_key)
    repair = matrix.repair_artifact_backend(
        scope_key=scope_key,
        backend_kind="shared_fs",
        actor="runtime-admin",
        reason="repair missing shared memory indexes",
    )

    shared_health = next(item for item in health if item.backend_kind == "shared_fs")
    assert shared_health.missing_artifact_count >= 1
    assert "repair_shared_artifacts" in recommendation.actions
    assert repair.repaired_artifact_count >= 1
    assert all(
        Path(item.path).exists()
        for item in matrix.list_memory_artifacts(scope_key=scope_key)
        if item.backend_kind == "shared_fs"
    )


def test_amos_repair_learning_state_changes_canary_controller_version_and_penalty(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(repository=repository)
    scope_keys = ["project:repair-learn-alpha", "project:repair-learn-beta", "project:repair-learn-gamma"]

    for index, (scope_key, obj, when) in enumerate(
        [
            (scope_keys[0], "AMOS design", _dt(10)),
            (scope_keys[1], "policy tuning", _dt(11)),
            (scope_keys[2], "repair fabric", _dt(12)),
        ]
    ):
        candidate = matrix.create_candidate(
            task_id=f"task-802-{index}",
            scope_key=scope_key,
            lane="semantic",
            summary=f"user working on {obj}",
            content={
                "subject": "user",
                "predicate": "working_on",
                "object": obj,
                "valid_from": when.isoformat(),
                "head": "goal",
            },
            sources=[f"episode-repair-learning-{index}"],
        )
        matrix.govern_candidate(candidate.candidate_id)
        matrix.consolidate_candidate(candidate.candidate_id)

    baseline = matrix.run_contradiction_repair_canary(
        scope_keys=scope_keys,
        subject="user",
        predicate="working_on",
    )
    learning = matrix.train_repair_controller(scope_keys=scope_keys)
    learned = matrix.run_contradiction_repair_canary(
        scope_keys=scope_keys,
        subject="user",
        predicate="working_on",
    )

    assert baseline.controller_version == "v1"
    assert learning.controller_version == "v2"
    assert learned.controller_version == "v2"
    assert learned.metrics["learned_risk_penalty"] > 0.0


def test_amos_background_maintenance_resumes_interrupted_loop_and_records_run(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(
        repository=repository,
        artifact_root=tmp_path / "artifacts",
        shared_artifact_root=tmp_path / "shared-artifacts",
    )
    scope_key = "project:bg-maintenance-v6"

    candidate = matrix.create_candidate(
        task_id="task-803",
        scope_key=scope_key,
        lane="semantic",
        summary="project needs background memory maintenance",
        content={
            "subject": "project",
            "predicate": "requires",
            "object": "background_memory_maintenance",
            "head": "goal",
        },
        sources=["episode-background-maintenance"],
    )
    matrix.govern_candidate(candidate.candidate_id)
    matrix.consolidate_candidate(candidate.candidate_id)
    matrix.schedule_memory_operations_loop(scope_key=scope_key, cadence_hours=24, actor="runtime-admin", start_at=_dt(18))
    interrupted = matrix.run_due_memory_operations(at_time=_dt(18), interrupt_after_phase="consolidation")

    recommendation = matrix.recommend_memory_maintenance(scope_key=scope_key)
    runs = matrix.run_background_memory_maintenance(scope_keys=[scope_key], actor="memory-worker", at_time=_dt(19))
    diagnostics = matrix.memory_operations_diagnostics(scope_key=scope_key)

    assert interrupted[0].status == "interrupted"
    assert "resume_interrupted_loop" in recommendation.actions
    assert runs[0].status == "completed"
    assert "resume_interrupted_loop" in runs[0].executed_actions
    assert diagnostics.interrupted_loop_count == 0


def test_amos_background_maintenance_canary_and_applies_safe_repairs(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(repository=repository)
    scope_keys = ["project:bg-repair-alpha", "project:bg-repair-beta"]

    for index, (scope_key, obj, when) in enumerate(
        [
            (scope_keys[0], "AMOS design", _dt(10)),
            (scope_keys[1], "policy tuning", _dt(15)),
        ]
    ):
        candidate = matrix.create_candidate(
            task_id=f"task-804-{index}",
            scope_key=scope_key,
            lane="semantic",
            summary=f"user working on {obj}",
            content={
                "subject": "user",
                "predicate": "working_on",
                "object": obj,
                "valid_from": when.isoformat(),
                "head": "goal",
            },
            sources=[f"episode-bg-repair-{index}"],
        )
        matrix.govern_candidate(candidate.candidate_id)
        matrix.consolidate_candidate(candidate.candidate_id)

    matrix.repair_cross_scope_contradictions(
        scope_keys=scope_keys,
        subject="user",
        predicate="working_on",
    )
    recommendation = matrix.recommend_memory_maintenance(scope_key=scope_keys[0])
    runs = matrix.run_background_memory_maintenance(scope_keys=[scope_keys[0]], actor="memory-worker")

    repairs = matrix.list_memory_contradiction_repairs(scope_keys=scope_keys)
    applied = [item for item in repairs if item.repair_status == "applied"]

    assert "evaluate_repair_backlog" in recommendation.actions
    assert runs[0].status == "completed"
    assert "apply_safe_repair" in runs[0].executed_actions
    assert applied
    assert matrix.list_repair_action_runs(repair_id=applied[0].repair_id)
