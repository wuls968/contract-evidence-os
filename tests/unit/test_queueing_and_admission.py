from datetime import UTC, datetime, timedelta
from pathlib import Path

from contract_evidence_os.runtime.provider_health import ProviderAvailabilityPolicy, ProviderHealthManager
from contract_evidence_os.runtime.queueing import (
    AdmissionPolicy,
    CapacityPolicy,
    CapacitySnapshot,
    LoadSheddingPolicy,
    QueueManager,
    QueuePolicy,
    QueuePriorityPolicy,
    RecoveryReservationPolicy,
)
from contract_evidence_os.storage.repository import SQLiteRepository


def _now() -> datetime:
    return datetime(2026, 4, 17, 0, 0, tzinfo=UTC)


def _queue_manager(tmp_path: Path) -> QueueManager:
    repo = SQLiteRepository(tmp_path / "ceos.sqlite3")
    return QueueManager(repository=repo)


def test_queue_manager_persists_leases_and_moves_exhausted_items_to_dead_letter(tmp_path: Path) -> None:
    queue = _queue_manager(tmp_path)
    queue.repository.save_queue_policy(
        QueuePolicy(
            version="1.0",
            policy_id="queue-policy-001",
            queue_name="default",
            max_attempts=2,
            lease_timeout_seconds=1,
            dead_letter_queue="dead-letter",
            created_at=_now(),
        )
    )
    queue.repository.save_admission_policy(
        AdmissionPolicy(
            version="1.0",
            policy_id="admission-policy-001",
            allow_high_risk_when_provider_degraded=False,
            max_active_tasks=2,
            max_pending_approvals=5,
            continuity_fragility_threshold=0.7,
            budget_pressure_threshold=0.2,
            created_at=_now(),
        )
    )
    queue.repository.save_queue_priority_policy(
        QueuePriorityPolicy(
            version="1.0",
            policy_id="priority-policy-001",
            class_weights={"standard": 10},
            resumed_task_bonus=5,
            stale_continuity_bonus=10,
            recovery_priority_bonus=20,
            high_risk_bonus=15,
            created_at=_now(),
        )
    )
    queue.repository.save_capacity_policy(
        CapacityPolicy(
            version="1.0",
            policy_id="capacity-policy-001",
            max_active_tasks=2,
            max_active_high_risk_tasks=1,
            max_provider_parallelism={"anthropic_live": 2},
            max_tool_parallelism={"file_retrieval": 2},
            created_at=_now(),
        )
    )
    queue.repository.save_load_shedding_policy(
        LoadSheddingPolicy(
            version="1.0",
            policy_id="load-policy-001",
            reject_low_priority_under_degraded_mode=True,
            defer_background_evals_when_recovery_reserved=True,
            created_at=_now(),
        )
    )
    queue.repository.save_recovery_reservation_policy(
        RecoveryReservationPolicy(
            version="1.0",
            policy_id="recovery-policy-001",
            reserve_active_slots=1,
            reserve_budget_fraction=0.15,
            created_at=_now(),
        )
    )

    item = queue.enqueue_task(
        task_id="task-001",
        contract_id="contract-001",
        risk_level="low",
        priority_class="standard",
        queue_name="default",
    )
    health = ProviderHealthManager(repository=queue.repository)
    health.repository.save_provider_availability_policy(
        ProviderAvailabilityPolicy(
            version="1.0",
            policy_id="provider-policy-001",
            provider_name="anthropic_live",
            failure_threshold=2,
            cooldown_seconds=1,
            rate_limit_window_seconds=60,
            max_requests_per_window=5,
            created_at=_now(),
        )
    )
    capacity = CapacitySnapshot(
        version="1.0",
        snapshot_id="capacity-001",
        active_tasks=0,
        queued_tasks=1,
        provider_capacity_usage={"anthropic_live": 0},
        tool_pressure={"file_retrieval": 0},
        approval_backlog=0,
        budget_pressure=0.0,
        recovery_reservations=0,
        eval_load=0,
        created_at=_now(),
    )

    first = queue.dispatch_next(
        worker_id="worker-1",
        capacity_snapshot=capacity,
        provider_health=health.snapshot(["anthropic_live"]),
        system_mode="normal",
    )
    assert first is not None
    queue.release_lease(first[1].lease_id, reason="worker crashed", retryable=True)

    second = queue.dispatch_next(
        worker_id="worker-1",
        capacity_snapshot=capacity,
        provider_health=health.snapshot(["anthropic_live"]),
        system_mode="normal",
    )
    assert second is not None
    queue.release_lease(second[1].lease_id, reason="worker crashed again", retryable=True)

    persisted = queue.repository.get_queue_item(item.queue_item_id)
    assert persisted is not None
    assert persisted.status == "dead_letter"


def test_admission_control_prioritizes_recovery_and_stale_continuity_before_background_work(tmp_path: Path) -> None:
    queue = _queue_manager(tmp_path)
    queue.repository.save_queue_policy(
        QueuePolicy(
            version="1.0",
            policy_id="queue-policy-001",
            queue_name="default",
            max_attempts=3,
            lease_timeout_seconds=60,
            dead_letter_queue="dead-letter",
            created_at=_now(),
        )
    )
    queue.repository.save_admission_policy(
        AdmissionPolicy(
            version="1.0",
            policy_id="admission-policy-001",
            allow_high_risk_when_provider_degraded=True,
            max_active_tasks=1,
            max_pending_approvals=3,
            continuity_fragility_threshold=0.7,
            budget_pressure_threshold=0.2,
            created_at=_now(),
        )
    )
    queue.repository.save_queue_priority_policy(
        QueuePriorityPolicy(
            version="1.0",
            policy_id="priority-policy-001",
            class_weights={"background_eval": 1, "standard": 10, "recovery": 30},
            resumed_task_bonus=5,
            stale_continuity_bonus=10,
            recovery_priority_bonus=25,
            high_risk_bonus=15,
            created_at=_now(),
        )
    )

    background = queue.enqueue_task(
        task_id="task-background",
        contract_id="contract-background",
        risk_level="low",
        priority_class="background_eval",
        queue_name="default",
    )
    queue.enqueue_task(
        task_id="task-stale",
        contract_id="contract-stale",
        risk_level="moderate",
        priority_class="standard",
        queue_name="default",
        continuity_fragility=0.95,
        resume_task=True,
    )
    queue.enqueue_task(
        task_id="task-recovery",
        contract_id="contract-recovery",
        risk_level="low",
        priority_class="recovery",
        queue_name="default",
        recovery_required=True,
    )

    health = ProviderHealthManager(repository=queue.repository)
    health.repository.save_provider_availability_policy(
        ProviderAvailabilityPolicy(
            version="1.0",
            policy_id="provider-policy-001",
            provider_name="anthropic_live",
            failure_threshold=3,
            cooldown_seconds=5,
            rate_limit_window_seconds=60,
            max_requests_per_window=5,
            created_at=_now(),
        )
    )
    capacity = CapacitySnapshot(
        version="1.0",
        snapshot_id="capacity-001",
        active_tasks=0,
        queued_tasks=3,
        provider_capacity_usage={"anthropic_live": 0},
        tool_pressure={"file_retrieval": 0},
        approval_backlog=0,
        budget_pressure=0.0,
        recovery_reservations=0,
        eval_load=0,
        created_at=_now(),
    )

    first = queue.dispatch_next(
        worker_id="worker-1",
        capacity_snapshot=capacity,
        provider_health=health.snapshot(["anthropic_live"]),
        system_mode="normal",
    )
    assert first is not None
    assert first[0].task_id == "task-recovery"
    queue.ack_lease(first[1].lease_id)

    second = queue.dispatch_next(
        worker_id="worker-1",
        capacity_snapshot=capacity,
        provider_health=health.snapshot(["anthropic_live"]),
        system_mode="normal",
    )
    assert second is not None
    assert second[0].task_id == "task-stale"

    remaining = queue.repository.get_queue_item(background.queue_item_id)
    assert remaining is not None
    assert remaining.status in {"queued", "deferred"}


def test_admission_control_defers_under_drain_mode(tmp_path: Path) -> None:
    queue = _queue_manager(tmp_path)
    queue.repository.save_admission_policy(
        AdmissionPolicy(
            version="1.0",
            policy_id="admission-policy-001",
            allow_high_risk_when_provider_degraded=False,
            max_active_tasks=1,
            max_pending_approvals=2,
            continuity_fragility_threshold=0.7,
            budget_pressure_threshold=0.2,
            created_at=_now(),
        )
    )
    item = queue.enqueue_task(
        task_id="task-001",
        contract_id="contract-001",
        risk_level="low",
        priority_class="standard",
        queue_name="default",
    )
    health = ProviderHealthManager(repository=queue.repository)
    health.repository.save_provider_availability_policy(
        ProviderAvailabilityPolicy(
            version="1.0",
            policy_id="provider-policy-001",
            provider_name="anthropic_live",
            failure_threshold=3,
            cooldown_seconds=5,
            rate_limit_window_seconds=60,
            max_requests_per_window=5,
            created_at=_now(),
        )
    )
    decision = queue.evaluate_admission(
        item=item,
        capacity_snapshot=CapacitySnapshot(
            version="1.0",
            snapshot_id="capacity-001",
            active_tasks=0,
            queued_tasks=1,
            provider_capacity_usage={"anthropic_live": 0},
            tool_pressure={"file_retrieval": 0},
            approval_backlog=0,
            budget_pressure=0.0,
            recovery_reservations=0,
            eval_load=0,
            created_at=_now(),
        ),
        provider_health=health.snapshot(["anthropic_live"]),
        system_mode="drain",
    )
    assert decision.status == "deferred"
    assert "drain" in decision.reason
