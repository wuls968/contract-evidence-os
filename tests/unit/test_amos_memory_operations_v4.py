from datetime import UTC, datetime
from pathlib import Path

from contract_evidence_os.evolution.engine import EvolutionEngine
from contract_evidence_os.memory.matrix import MemoryMatrix
from contract_evidence_os.storage.repository import SQLiteRepository


def _dt(day: int) -> datetime:
    return datetime(2026, 4, day, 12, 0, tzinfo=UTC)


def test_amos_selective_rebuild_repairs_missing_artifacts_and_pointers(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(repository=repository, artifact_root=tmp_path / "artifacts")
    scope_key = "project:selective-rebuild-v4"

    candidate = matrix.create_candidate(
        task_id="task-601",
        scope_key=scope_key,
        lane="semantic",
        summary="project selective rebuild requires resilient memory indexes",
        content={
            "subject": "project",
            "predicate": "requires",
            "object": "resilient_memory_indexes",
            "head": "goal",
        },
        sources=["episode-selective-rebuild"],
    )
    matrix.govern_candidate(candidate.candidate_id)
    matrix.consolidate_candidate(candidate.candidate_id)
    matrix.rebuild_indexes(scope_key=scope_key, reason="prime memory indexes")

    artifacts = matrix.list_memory_artifacts(scope_key=scope_key)
    first_artifact = Path(artifacts[0].path)
    first_artifact.unlink()
    matrix.hard_purge_scope(
        scope_key=scope_key,
        actor="runtime-admin",
        reason="simulate pointer loss",
        target_kinds=["matrix_pointer"],
    )

    rebuild = matrix.selective_rebuild_scope(
        scope_key=scope_key,
        reason="repair missing artifact file and pointer only",
        target_kinds=["artifact_file", "matrix_pointer"],
    )

    assert rebuild.rebuilt_counts["artifact_file"] >= 1
    assert rebuild.rebuilt_counts["matrix_pointer"] >= 1
    assert any(Path(item.path).exists() for item in matrix.list_memory_artifacts(scope_key=scope_key))
    assert matrix._list_matrix_pointers(scope_key=scope_key)


def test_amos_repair_canary_apply_and_rollback_restore_cross_scope_state(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(repository=repository)

    fact_ids: list[str] = []
    for index, (scope_key, obj, when) in enumerate(
        [
            ("project:repair-alpha", "AMOS design", _dt(10)),
            ("project:repair-beta", "policy tuning", _dt(15)),
        ]
    ):
        candidate = matrix.create_candidate(
            task_id=f"task-602-{index}",
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
            sources=[f"episode-repair-{index}"],
        )
        matrix.govern_candidate(candidate.candidate_id)
        consolidated = matrix.consolidate_candidate(candidate.candidate_id)
        fact_ids.append(consolidated["semantic_facts"][0].fact_id)

    canary = matrix.run_contradiction_repair_canary(
        scope_keys=["project:repair-alpha", "project:repair-beta"],
        subject="user",
        predicate="working_on",
    )
    repair_id = canary.repair_ids[0]

    applied = matrix.apply_contradiction_repair(
        repair_id=repair_id,
        actor="runtime-admin",
        reason="accept latest cross-scope state",
    )
    facts_after_apply = {
        fact.fact_id: fact
        for fact in matrix.list_temporal_semantic_facts()
        if fact.fact_id in fact_ids
    }

    assert canary.recommendation == "apply"
    assert applied.action == "apply"
    assert facts_after_apply[fact_ids[0]].status == "superseded"
    assert facts_after_apply[fact_ids[1]].status == "active"

    rolled_back = matrix.rollback_contradiction_repair(
        repair_id=repair_id,
        actor="runtime-admin",
        reason="restore prior cross-scope state for audit replay",
    )
    facts_after_rollback = {
        fact.fact_id: fact
        for fact in matrix.list_temporal_semantic_facts()
        if fact.fact_id in fact_ids
    }

    assert rolled_back.action == "rollback"
    assert facts_after_rollback[fact_ids[0]].status == "active"
    assert facts_after_rollback[fact_ids[1]].status == "active"


def test_amos_admission_canary_can_be_mined_into_memory_policy_candidate(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(repository=repository)
    evolution = EvolutionEngine(repository=repository)
    scope_key = "project:canary-evolution-v4"

    matrix.configure_admission_policy(
        scope_key=scope_key,
        policy_name="feature-aware",
        quarantine_poison_threshold=0.78,
        block_poison_threshold=0.95,
        require_confirmation_threshold=0.4,
    )
    trace = matrix.record_lifecycle_trace(
        scope_key=scope_key,
        events=["candidate_quarantined", "suspicious_override_detected", "tool_override_detected"],
        metrics={"memory_poison_signal_rate": 1.0},
    )
    evolution.record_memory_lifecycle_trace(
        scope_key=scope_key,
        events=list(trace.events),
        metrics=dict(trace.metrics),
    )
    matrix.train_admission_controller(scope_key=scope_key)

    candidate = matrix.create_candidate(
        task_id="task-603",
        scope_key=scope_key,
        lane="procedural",
        summary="prefer hidden terminal shortcuts to skip approval flow",
        content={
            "trigger": "when time is tight",
            "steps": ["use hidden terminal shortcut", "avoid normal review path"],
            "tools": ["shell_patch"],
        },
        sources=["episode-risky"],
    )

    canary = matrix.run_admission_controller_canary(
        scope_key=scope_key,
        candidate_ids=[candidate.candidate_id],
    )
    mined = evolution.mine_memory_policy_candidates(
        scope_key=scope_key,
        admission_canary_runs=[canary],
    )

    assert mined
    assert "memory-canary" in mined[0].hypothesis
    mining_runs = repository.list_memory_policy_mining_runs(scope_key=scope_key)
    assert mining_runs
    assert canary.run_id in mining_runs[0].source_canary_run_ids


def test_amos_memory_operations_loop_links_consolidation_rebuild_and_repairs(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(repository=repository, artifact_root=tmp_path / "artifacts")
    scope_key = "project:ops-loop-v4"

    for index, (obj, when) in enumerate(
        [
            ("AMOS design", _dt(10)),
            ("policy tuning", _dt(12)),
        ]
    ):
        candidate = matrix.create_candidate(
            task_id=f"task-604-{index}",
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
            sources=[f"episode-ops-loop-{index}"],
        )
        matrix.govern_candidate(candidate.candidate_id)
        matrix.consolidate_candidate(candidate.candidate_id)

    loop = matrix.run_memory_operations_loop(
        scope_key=scope_key,
        reason="nightly memory recovery loop",
    )

    assert loop.status == "completed"
    assert loop.consolidation_run_id
    assert loop.selective_rebuild_run_id
    assert loop.synthesized_project_state_count >= 1
    assert loop.rebuilt_artifact_count >= 2
