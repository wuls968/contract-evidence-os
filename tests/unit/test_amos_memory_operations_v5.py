from datetime import UTC, datetime
from pathlib import Path

from contract_evidence_os.evolution.engine import EvolutionEngine
from contract_evidence_os.memory.matrix import MemoryMatrix
from contract_evidence_os.storage.repository import SQLiteRepository


def _dt(day: int) -> datetime:
    return datetime(2026, 4, day, 12, 0, tzinfo=UTC)


def test_amos_repair_canary_records_safety_assessment_and_blocks_unsafe_apply(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(repository=repository)

    for index, (scope_key, obj, when) in enumerate(
        [
            ("project:risk-alpha", "AMOS design", _dt(10)),
            ("project:risk-beta", "policy tuning", _dt(11)),
            ("project:risk-gamma", "repair fabric", _dt(12)),
        ]
    ):
        candidate = matrix.create_candidate(
            task_id=f"task-701-{index}",
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
            sources=[f"episode-risk-{index}"],
        )
        matrix.govern_candidate(candidate.candidate_id)
        matrix.consolidate_candidate(candidate.candidate_id)

    canary = matrix.run_contradiction_repair_canary(
        scope_keys=["project:risk-alpha", "project:risk-beta", "project:risk-gamma"],
        subject="user",
        predicate="working_on",
    )
    assessments = matrix.list_repair_safety_assessments(scope_keys=["project:risk-alpha", "project:risk-beta", "project:risk-gamma"])

    assert canary.recommendation == "hold"
    assert assessments
    assert assessments[0].safety_score < 0.75


def test_amos_repair_apply_and_rollback_persist_rollout_analytics(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(repository=repository)

    for index, (scope_key, obj, when) in enumerate(
        [
            ("project:rollout-alpha", "AMOS design", _dt(10)),
            ("project:rollout-beta", "policy tuning", _dt(15)),
        ]
    ):
        candidate = matrix.create_candidate(
            task_id=f"task-702-{index}",
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
            sources=[f"episode-rollout-{index}"],
        )
        matrix.govern_candidate(candidate.candidate_id)
        matrix.consolidate_candidate(candidate.candidate_id)

    canary = matrix.run_contradiction_repair_canary(
        scope_keys=["project:rollout-alpha", "project:rollout-beta"],
        subject="user",
        predicate="working_on",
    )
    matrix.apply_contradiction_repair(
        repair_id=canary.repair_ids[0],
        actor="runtime-admin",
        reason="apply latest state",
    )
    matrix.rollback_contradiction_repair(
        repair_id=canary.repair_ids[0],
        actor="runtime-admin",
        reason="restore prior state",
    )

    analytics = matrix.list_repair_rollout_analytics(repair_id=canary.repair_ids[0])
    actions = [item.action for item in analytics]

    assert "apply" in actions
    assert "rollback" in actions


def test_amos_admission_canary_creates_promotion_recommendation_and_evolution_uses_it(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(repository=repository)
    evolution = EvolutionEngine(repository=repository)
    scope_key = "project:promotion-v5"

    matrix.configure_admission_policy(
        scope_key=scope_key,
        policy_name="feature-aware",
        quarantine_poison_threshold=0.78,
        block_poison_threshold=0.95,
        require_confirmation_threshold=0.4,
    )
    matrix.record_lifecycle_trace(
        scope_key=scope_key,
        events=["candidate_quarantined", "suspicious_override_detected", "tool_override_detected"],
        metrics={"memory_poison_signal_rate": 1.0},
    )
    matrix.train_admission_controller(scope_key=scope_key)
    risky = matrix.create_candidate(
        task_id="task-703",
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
    canary = matrix.run_admission_controller_canary(scope_key=scope_key, candidate_ids=[risky.candidate_id])
    recommendation = matrix.recommend_admission_policy_promotion(scope_key=scope_key)

    mined = evolution.mine_memory_policy_candidates(
        scope_key=scope_key,
        admission_canary_runs=[canary],
        promotion_recommendations=[recommendation],
    )

    assert recommendation.recommendation == "promote"
    assert mined
    assert recommendation.recommendation_id in repository.list_memory_policy_mining_runs(scope_key=scope_key)[0].source_recommendation_ids


def test_amos_memory_ops_schedule_interrupt_resume_and_diagnostics(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    matrix = MemoryMatrix(repository=repository, artifact_root=tmp_path / "artifacts")
    scope_key = "project:ops-schedule-v5"

    candidate = matrix.create_candidate(
        task_id="task-704",
        scope_key=scope_key,
        lane="semantic",
        summary="project needs a scheduled memory repair loop",
        content={
            "subject": "project",
            "predicate": "requires",
            "object": "scheduled_memory_repair_loop",
            "head": "goal",
        },
        sources=["episode-ops-schedule"],
    )
    matrix.govern_candidate(candidate.candidate_id)
    matrix.consolidate_candidate(candidate.candidate_id)
    matrix.schedule_memory_operations_loop(scope_key=scope_key, cadence_hours=24, actor="runtime-admin", start_at=_dt(18))

    runs = matrix.run_due_memory_operations(at_time=_dt(18), interrupt_after_phase="consolidation")
    diagnostics_before = matrix.memory_operations_diagnostics(scope_key=scope_key)

    resumed = matrix.resume_memory_operations_loop(
        loop_run_id=runs[0].run_id,
        actor="runtime-admin",
        reason="resume interrupted loop",
    )
    diagnostics_after = matrix.memory_operations_diagnostics(scope_key=scope_key)

    assert runs[0].status == "interrupted"
    assert diagnostics_before.interrupted_loop_count >= 1
    assert resumed.status == "completed"
    assert diagnostics_after.interrupted_loop_count == 0
