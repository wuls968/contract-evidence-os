from pathlib import Path

from contract_evidence_os.memory.matrix import MemoryMatrix
from contract_evidence_os.storage.repository import SQLiteRepository


def test_amos_artifact_drift_detection_and_reconciliation(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(
        repository=repository,
        artifact_root=tmp_path / "artifacts",
        shared_artifact_root=tmp_path / "shared-artifacts",
    )
    scope_key = "project:drift-v8"

    candidate = matrix.create_candidate(
        task_id="task-951",
        scope_key=scope_key,
        lane="semantic",
        summary="project requires drift-safe memory indexes",
        content={
            "subject": "project",
            "predicate": "requires",
            "object": "drift_safe_memory_indexes",
            "head": "goal",
        },
        sources=["episode-drift-v8"],
    )
    matrix.govern_candidate(candidate.candidate_id)
    matrix.consolidate_candidate(candidate.candidate_id)
    matrix.rebuild_indexes(scope_key=scope_key, reason="prime mirrored indexes")

    shared_artifact = next(
        item for item in matrix.list_memory_artifacts(scope_key=scope_key) if item.backend_kind == "shared_fs" and item.artifact_kind == "memory_index"
    )
    Path(shared_artifact.path).write_text('{"corrupted": true}\n', encoding="utf-8")

    drift = matrix.scan_artifact_drift(scope_key=scope_key)
    recommendation = matrix.recommend_memory_maintenance(scope_key=scope_key)
    run = matrix.run_background_memory_maintenance(scope_keys=[scope_key], actor="memory-worker")[0]

    assert drift
    assert "reconcile_shared_artifacts" in recommendation.actions
    assert "reconcile_shared_artifacts" in run.executed_actions


def test_amos_maintenance_incident_and_degraded_mode_visibility(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(
        repository=repository,
        artifact_root=tmp_path / "artifacts",
        shared_artifact_root=tmp_path / "shared-artifacts",
    )
    scope_key = "project:incident-v8"

    candidate = matrix.create_candidate(
        task_id="task-952",
        scope_key=scope_key,
        lane="semantic",
        summary="project requires resilient maintenance incidents",
        content={
            "subject": "project",
            "predicate": "requires",
            "object": "maintenance_incident_tracking",
            "head": "goal",
        },
        sources=["episode-incident-v8"],
    )
    matrix.govern_candidate(candidate.candidate_id)
    matrix.consolidate_candidate(candidate.candidate_id)
    matrix.rebuild_indexes(scope_key=scope_key, reason="prime incident indexes")

    matrix.shared_artifact_root = None
    matrix.run_background_memory_maintenance(scope_keys=[scope_key], actor="memory-worker")
    incidents = matrix.list_memory_maintenance_incidents(scope_key=scope_key)
    mode = matrix.maintenance_mode(scope_key=scope_key)

    assert incidents
    assert mode["mode"] == "degraded"
