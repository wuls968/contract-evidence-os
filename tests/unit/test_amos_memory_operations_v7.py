from datetime import UTC, datetime
from pathlib import Path

from contract_evidence_os.evolution.engine import EvolutionEngine
from contract_evidence_os.memory.matrix import MemoryMatrix
from contract_evidence_os.storage.repository import SQLiteRepository


def _dt(day: int) -> datetime:
    return datetime(2026, 4, day, 12, 0, tzinfo=UTC)


def test_amos_background_maintenance_schedule_interrupt_resume_and_analytics(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(
        repository=repository,
        artifact_root=tmp_path / "artifacts",
        shared_artifact_root=tmp_path / "shared-artifacts",
    )
    scope_key = "project:maintenance-schedule-v7"

    candidate = matrix.create_candidate(
        task_id="task-901",
        scope_key=scope_key,
        lane="semantic",
        summary="project requires scheduled background maintenance",
        content={
            "subject": "project",
            "predicate": "requires",
            "object": "scheduled_background_maintenance",
            "head": "goal",
        },
        sources=["episode-bg-maintenance-schedule"],
    )
    matrix.govern_candidate(candidate.candidate_id)
    matrix.consolidate_candidate(candidate.candidate_id)

    matrix.schedule_background_maintenance(
        scope_key=scope_key,
        cadence_hours=24,
        actor="runtime-admin",
        start_at=_dt(18),
    )
    interrupted = matrix.run_due_background_maintenance(
        at_time=_dt(18),
        interrupt_after_phase="recommendation",
    )
    resumed = matrix.resume_background_maintenance(
        run_id=interrupted[0].run_id,
        actor="memory-worker",
        reason="resume interrupted background maintenance",
    )
    analytics = matrix.list_memory_maintenance_analytics(scope_key=scope_key)

    assert interrupted[0].status == "interrupted"
    assert interrupted[0].interrupted_phase == "recommendation"
    assert resumed.status == "completed"
    assert resumed.resumed_from_run_id == interrupted[0].run_id
    assert analytics


def test_amos_maintenance_canary_generates_promotion_recommendation_and_evolution_signal(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(
        repository=repository,
        artifact_root=tmp_path / "artifacts",
        shared_artifact_root=tmp_path / "shared-artifacts",
    )
    evolution = EvolutionEngine(repository=repository)
    scope_key = "project:maintenance-canary-v7"

    candidate = matrix.create_candidate(
        task_id="task-902",
        scope_key=scope_key,
        lane="semantic",
        summary="project requires learned maintenance routing",
        content={
            "subject": "project",
            "predicate": "requires",
            "object": "learned_maintenance_routing",
            "head": "goal",
        },
        sources=["episode-maintenance-canary"],
    )
    matrix.govern_candidate(candidate.candidate_id)
    matrix.consolidate_candidate(candidate.candidate_id)
    matrix.schedule_memory_operations_loop(scope_key=scope_key, cadence_hours=24, actor="runtime-admin", start_at=_dt(18))
    matrix.run_due_memory_operations(at_time=_dt(18), interrupt_after_phase="consolidation")
    matrix.run_background_memory_maintenance(scope_keys=[scope_key], actor="memory-worker", at_time=_dt(19))

    learning = matrix.train_maintenance_controller(scope_key=scope_key)
    canary = matrix.run_maintenance_recommendation_canary(scope_key=scope_key)
    recommendation = matrix.recommend_maintenance_policy_promotion(scope_key=scope_key)
    mined = evolution.mine_memory_policy_candidates(
        scope_key=scope_key,
        promotion_recommendations=[recommendation],
    )

    assert learning.controller_version == "v2"
    assert canary.controller_version == "v2"
    assert recommendation.recommendation in {"promote", "hold"}
    assert mined


def test_amos_shared_backend_fallback_recommends_local_rebuild_when_shared_backend_unavailable(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(
        repository=repository,
        artifact_root=tmp_path / "artifacts",
        shared_artifact_root=tmp_path / "shared-artifacts",
    )
    scope_key = "project:shared-fallback-v7"

    candidate = matrix.create_candidate(
        task_id="task-903",
        scope_key=scope_key,
        lane="semantic",
        summary="project requires shared index resilience",
        content={
            "subject": "project",
            "predicate": "requires",
            "object": "shared_index_resilience",
            "head": "goal",
        },
        sources=["episode-shared-fallback"],
    )
    matrix.govern_candidate(candidate.candidate_id)
    matrix.consolidate_candidate(candidate.candidate_id)
    matrix.rebuild_indexes(scope_key=scope_key, reason="prime indexes")

    matrix.shared_artifact_root = None
    recommendation = matrix.recommend_memory_maintenance(scope_key=scope_key)
    run = matrix.run_background_memory_maintenance(scope_keys=[scope_key], actor="memory-worker")[0]
    analytics = matrix.list_memory_maintenance_analytics(scope_key=scope_key)

    assert "fallback_local_artifacts" in recommendation.actions
    assert "fallback_local_artifacts" in run.executed_actions
    assert analytics[-1].fallback_action_count >= 1
