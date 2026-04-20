from datetime import UTC, datetime
from pathlib import Path

from contract_evidence_os.memory.matrix import MemoryMatrix
from contract_evidence_os.storage.repository import SQLiteRepository


def _dt(day: int) -> datetime:
    return datetime(2026, 4, day, 12, 0, tzinfo=UTC)


def test_amos_maintenance_worker_claims_due_schedule_and_resumes_interrupted_run(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(
        repository=repository,
        artifact_root=tmp_path / "artifacts",
        shared_artifact_root=tmp_path / "shared-artifacts",
    )
    scope_key = "project:maintenance-worker-v9"

    candidate = matrix.create_candidate(
        task_id="task-981",
        scope_key=scope_key,
        lane="semantic",
        summary="project requires resident maintenance workers",
        content={
            "subject": "project",
            "predicate": "requires",
            "object": "resident_maintenance_workers",
            "head": "goal",
        },
        sources=["episode-maintenance-worker"],
    )
    matrix.govern_candidate(candidate.candidate_id)
    matrix.consolidate_candidate(candidate.candidate_id)

    schedule = matrix.schedule_background_maintenance(
        scope_key=scope_key,
        cadence_hours=24,
        actor="runtime-admin",
        start_at=_dt(18),
    )
    matrix.register_maintenance_worker(worker_id="maint-a", host_id="host-a", actor="runtime-admin")
    matrix.register_maintenance_worker(worker_id="maint-b", host_id="host-b", actor="runtime-admin")

    interrupted = matrix.run_maintenance_worker_cycle(
        worker_id="maint-a",
        at_time=_dt(18),
        interrupt_after_phase="recommendation",
    )
    blocked = matrix.run_maintenance_worker_cycle(
        worker_id="maint-b",
        at_time=_dt(18),
    )
    resumed = matrix.resume_background_maintenance(
        run_id=interrupted[0].run_id,
        actor="maint-a",
        reason="resume resident maintenance worker run",
        worker_id="maint-a",
    )
    schedules = matrix.list_memory_maintenance_schedules(scope_key=scope_key)
    workers = matrix.list_memory_maintenance_workers()

    assert interrupted[0].status == "interrupted"
    assert interrupted[0].schedule_id == schedule.schedule_id
    assert interrupted[0].claimed_by_worker_id == "maint-a"
    assert blocked == []
    assert resumed.status == "completed"
    assert resumed.resumed_from_run_id == interrupted[0].run_id
    assert schedules[0].claimed_by_worker_id is None
    assert any(item.worker_id == "maint-a" and item.last_heartbeat_at is not None for item in workers)


def test_amos_maintenance_incident_can_be_resolved_after_backend_restore(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(
        repository=repository,
        artifact_root=tmp_path / "artifacts",
        shared_artifact_root=tmp_path / "shared-artifacts",
    )
    scope_key = "project:maintenance-resolution-v9"

    candidate = matrix.create_candidate(
        task_id="task-982",
        scope_key=scope_key,
        lane="semantic",
        summary="project requires resolved maintenance incidents",
        content={
            "subject": "project",
            "predicate": "requires",
            "object": "resolved_maintenance_incidents",
            "head": "goal",
        },
        sources=["episode-maintenance-resolution"],
    )
    matrix.govern_candidate(candidate.candidate_id)
    matrix.consolidate_candidate(candidate.candidate_id)
    matrix.rebuild_indexes(scope_key=scope_key, reason="prime shared indexes")

    matrix.shared_artifact_root = None
    matrix.run_background_memory_maintenance(scope_keys=[scope_key], actor="memory-worker")
    incidents = matrix.list_memory_maintenance_incidents(scope_key=scope_key)
    degraded = matrix.maintenance_mode(scope_key=scope_key)

    matrix.shared_artifact_root = tmp_path / "shared-artifacts"
    resolved = matrix.resolve_maintenance_incident(
        incident_id=incidents[0].incident_id,
        actor="runtime-admin",
        resolution="shared backend restored",
    )
    healthy = matrix.maintenance_mode(scope_key=scope_key)

    assert degraded["mode"] == "degraded"
    assert resolved.status == "resolved"
    assert resolved.resolved_at is not None
    assert healthy["mode"] == "normal"


def test_amos_maintenance_promotion_apply_and_rollback_records_rollouts(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(
        repository=repository,
        artifact_root=tmp_path / "artifacts",
        shared_artifact_root=tmp_path / "shared-artifacts",
    )
    scope_key = "project:maintenance-rollout-v9"

    candidate = matrix.create_candidate(
        task_id="task-983",
        scope_key=scope_key,
        lane="semantic",
        summary="project requires maintenance controller rollout governance",
        content={
            "subject": "project",
            "predicate": "requires",
            "object": "maintenance_controller_rollout_governance",
            "head": "goal",
        },
        sources=["episode-maintenance-rollout"],
    )
    matrix.govern_candidate(candidate.candidate_id)
    matrix.consolidate_candidate(candidate.candidate_id)
    matrix.schedule_memory_operations_loop(scope_key=scope_key, cadence_hours=24, actor="runtime-admin", start_at=_dt(18))
    matrix.run_due_memory_operations(at_time=_dt(18), interrupt_after_phase="consolidation")
    matrix.run_background_memory_maintenance(scope_keys=[scope_key], actor="memory-worker", at_time=_dt(19))

    matrix.train_maintenance_controller(scope_key=scope_key)
    matrix.run_maintenance_recommendation_canary(scope_key=scope_key)
    recommendation = matrix.recommend_maintenance_policy_promotion(scope_key=scope_key)
    applied = matrix.apply_maintenance_promotion(
        scope_key=scope_key,
        recommendation_id=recommendation.recommendation_id,
        actor="runtime-admin",
        reason="promote learned maintenance controller",
    )
    active = matrix.maintenance_controller_state(scope_key=scope_key)
    learned_recommendation = matrix.recommend_memory_maintenance(scope_key=scope_key)
    rolled_back = matrix.rollback_maintenance_rollout(
        rollout_id=applied.rollout_id,
        actor="runtime-admin",
        reason="rollback maintenance controller rollout",
    )
    restored = matrix.maintenance_controller_state(scope_key=scope_key)
    rollouts = matrix.list_memory_maintenance_rollouts(scope_key=scope_key)

    assert applied.action == "apply"
    assert active.active_controller_version == recommendation.controller_version
    assert learned_recommendation.controller_version == recommendation.controller_version
    assert rolled_back.action == "rollback"
    assert restored.active_controller_version == "v1"
    assert len(rollouts) >= 2
