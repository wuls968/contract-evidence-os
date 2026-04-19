"""Persistent queueing, admission control, and system-scale capacity models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from contract_evidence_os.base import SchemaModel, utc_now


@dataclass
class QueueItem(SchemaModel):
    """Persisted unit of queued task work."""

    version: str
    queue_item_id: str
    task_id: str
    contract_id: str
    queue_name: str
    priority_class: str
    risk_level: str
    status: str
    attempt_count: int
    max_attempts: int
    recovery_required: bool = False
    resume_task: bool = False
    continuity_fragility: float = 0.0
    operator_priority: int = 0
    lease_id: str = ""
    available_at: datetime = field(default_factory=utc_now)
    dead_letter_reason: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class QueueLease(SchemaModel):
    """Lease representing temporary ownership of a queued task."""

    version: str
    lease_id: str
    queue_item_id: str
    task_id: str
    worker_id: str
    status: str
    acquired_at: datetime
    expires_at: datetime
    fencing_token: str = ""
    lease_epoch: int = 0
    owner_session_id: str = ""
    renewed_at: datetime | None = None
    released_at: datetime | None = None
    release_reason: str = ""

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class AdmissionDecision(SchemaModel):
    """Decision about whether a queued task may enter active execution."""

    version: str
    decision_id: str
    queue_item_id: str
    task_id: str
    status: str
    reason: str
    active_policy_id: str
    active_mode: str
    factors: dict[str, Any]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class DispatchRecord(SchemaModel):
    """Record that a queued task was dispatched to a worker."""

    version: str
    dispatch_id: str
    queue_item_id: str
    task_id: str
    lease_id: str
    worker_id: str
    status: str
    admission_decision_id: str
    created_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class QueuePolicy(SchemaModel):
    """Queue policy for lease length, retries, and dead-letter handling."""

    version: str
    policy_id: str
    queue_name: str
    max_attempts: int
    lease_timeout_seconds: int
    dead_letter_queue: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class CapacitySnapshot(SchemaModel):
    """System-scale capacity view used during admission control."""

    version: str
    snapshot_id: str
    active_tasks: int
    queued_tasks: int
    provider_capacity_usage: dict[str, int]
    tool_pressure: dict[str, int]
    approval_backlog: int
    budget_pressure: float
    recovery_reservations: int
    eval_load: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class LoadSheddingEvent(SchemaModel):
    """Record that work was deferred or rejected under system pressure."""

    version: str
    event_id: str
    queue_item_id: str
    task_id: str
    reason: str
    action: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class AdmissionPolicy(SchemaModel):
    """Admission policy for queued or resumed tasks."""

    version: str
    policy_id: str
    allow_high_risk_when_provider_degraded: bool
    max_active_tasks: int
    max_pending_approvals: int
    continuity_fragility_threshold: float
    budget_pressure_threshold: float
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class QueuePriorityPolicy(SchemaModel):
    """Priority weights for queue ordering."""

    version: str
    policy_id: str
    class_weights: dict[str, int]
    resumed_task_bonus: int
    stale_continuity_bonus: int
    recovery_priority_bonus: int
    high_risk_bonus: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class CapacityPolicy(SchemaModel):
    """Capacity caps used for admission decisions."""

    version: str
    policy_id: str
    max_active_tasks: int
    max_active_high_risk_tasks: int
    max_provider_parallelism: dict[str, int]
    max_tool_parallelism: dict[str, int]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class LoadSheddingPolicy(SchemaModel):
    """Policy controlling how non-critical work is deferred or rejected."""

    version: str
    policy_id: str
    reject_low_priority_under_degraded_mode: bool
    defer_background_evals_when_recovery_reserved: bool
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class RecoveryReservationPolicy(SchemaModel):
    """Reserve slots and budget for recovery-critical work."""

    version: str
    policy_id: str
    reserve_active_slots: int
    reserve_budget_fraction: float
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class GlobalExecutionModeState(SchemaModel):
    """Persisted system-wide execution mode."""

    version: str
    mode_id: str
    mode_name: str
    reason: str
    active_constraints: list[str]
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class OperatorOverrideRecord(SchemaModel):
    """Typed operator override with optional idempotency key."""

    version: str
    override_id: str
    action: str
    scope: str
    value: str
    operator: str
    status: str
    idempotency_key: str = ""
    reason: str = ""
    created_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()


class QueueManager:
    """Persistent task queue manager with admission and lease handling."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def enqueue_task(
        self,
        *,
        task_id: str,
        contract_id: str,
        risk_level: str,
        priority_class: str,
        queue_name: str = "default",
        continuity_fragility: float = 0.0,
        recovery_required: bool = False,
        resume_task: bool = False,
        operator_priority: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> QueueItem:
        policy = self.repository.load_queue_policy(queue_name) or QueuePolicy(
            version="1.0",
            policy_id=f"queue-policy-{queue_name}",
            queue_name=queue_name,
            max_attempts=3,
            lease_timeout_seconds=60,
            dead_letter_queue="dead-letter",
        )
        item = QueueItem(
            version="1.0",
            queue_item_id=f"queue-item-{uuid4().hex[:10]}",
            task_id=task_id,
            contract_id=contract_id,
            queue_name=queue_name,
            priority_class=priority_class,
            risk_level=risk_level,
            status="queued",
            attempt_count=0,
            max_attempts=policy.max_attempts,
            continuity_fragility=continuity_fragility,
            recovery_required=recovery_required,
            resume_task=resume_task,
            operator_priority=operator_priority,
            payload={} if payload is None else payload,
        )
        self.repository.save_queue_item(item)
        return item

    def dispatch_next(
        self,
        *,
        worker_id: str,
        capacity_snapshot: CapacitySnapshot,
        provider_health: Any,
        system_mode: str,
        now: datetime | None = None,
    ) -> tuple[QueueItem, QueueLease, AdmissionDecision, DispatchRecord] | None:
        now = utc_now() if now is None else now
        items = self.repository.list_queue_items(statuses=["queued", "deferred", "leased"])
        items = [item for item in items if item.status != "leased" and item.available_at <= now]
        if not items:
            return None
        for item in sorted(items, key=lambda candidate: self._priority_score(candidate), reverse=True):
            decision = self.evaluate_admission(
                item=item,
                capacity_snapshot=capacity_snapshot,
                provider_health=provider_health,
                system_mode=system_mode,
            )
            self.repository.save_admission_decision(decision)
            if decision.status != "admitted":
                item.status = "deferred" if decision.status == "deferred" else "rejected"
                item.updated_at = now
                self.repository.save_queue_item(item)
                self.repository.save_load_shedding_event(
                    LoadSheddingEvent(
                        version="1.0",
                        event_id=f"load-shed-{uuid4().hex[:10]}",
                        queue_item_id=item.queue_item_id,
                        task_id=item.task_id,
                        reason=decision.reason,
                        action=item.status,
                        created_at=now,
                    )
                )
                continue
            policy = self.repository.load_queue_policy(item.queue_name) or QueuePolicy(
                version="1.0",
                policy_id=f"queue-policy-{item.queue_name}",
                queue_name=item.queue_name,
                max_attempts=item.max_attempts,
                lease_timeout_seconds=60,
                dead_letter_queue="dead-letter",
            )
            lease = QueueLease(
                version="1.0",
                lease_id=f"queue-lease-{uuid4().hex[:10]}",
                queue_item_id=item.queue_item_id,
                task_id=item.task_id,
                worker_id=worker_id,
                status="active",
                acquired_at=now,
                expires_at=now + timedelta(seconds=policy.lease_timeout_seconds),
            )
            item.status = "leased"
            item.lease_id = lease.lease_id
            item.updated_at = now
            self.repository.save_queue_item(item)
            self.repository.save_queue_lease(lease)
            dispatch = DispatchRecord(
                version="1.0",
                dispatch_id=f"dispatch-{uuid4().hex[:10]}",
                queue_item_id=item.queue_item_id,
                task_id=item.task_id,
                lease_id=lease.lease_id,
                worker_id=worker_id,
                status="dispatched",
                admission_decision_id=decision.decision_id,
                created_at=now,
            )
            self.repository.save_dispatch_record(dispatch)
            return item, lease, decision, dispatch
        return None

    def evaluate_admission(
        self,
        *,
        item: QueueItem,
        capacity_snapshot: CapacitySnapshot,
        provider_health: Any,
        system_mode: str,
    ) -> AdmissionDecision:
        policy = self.repository.latest_admission_policy() or AdmissionPolicy(
            version="1.0",
            policy_id="admission-default",
            allow_high_risk_when_provider_degraded=False,
            max_active_tasks=1,
            max_pending_approvals=5,
            continuity_fragility_threshold=0.75,
            budget_pressure_threshold=0.4,
        )
        provider_available = bool(getattr(provider_health, "records", []))
        degraded = any(getattr(record, "availability_state", "available") != "available" for record in getattr(provider_health, "records", []))
        status = "admitted"
        reason = "capacity and provider health allow dispatch"
        if system_mode in {"drain", "maintenance"}:
            status = "deferred"
            reason = f"system mode {system_mode} is deferring queue dispatch"
        elif capacity_snapshot.active_tasks >= policy.max_active_tasks:
            status = "deferred"
            reason = "active task capacity is saturated"
        elif capacity_snapshot.approval_backlog > policy.max_pending_approvals and item.priority_class == "background_eval":
            status = "deferred"
            reason = "approval backlog is too high for background work"
        elif capacity_snapshot.budget_pressure >= policy.budget_pressure_threshold and item.priority_class == "background_eval":
            status = "deferred"
            reason = "budget pressure is reserving capacity for higher-value work"
        elif not provider_available:
            status = "deferred"
            reason = "no compatible providers are currently available"
        elif degraded and item.risk_level == "high" and not policy.allow_high_risk_when_provider_degraded:
            status = "deferred"
            reason = "provider degradation blocks high-risk admission"
        return AdmissionDecision(
            version="1.0",
            decision_id=f"admission-{uuid4().hex[:10]}",
            queue_item_id=item.queue_item_id,
            task_id=item.task_id,
            status=status,
            reason=reason,
            active_policy_id=policy.policy_id,
            active_mode=system_mode,
            factors={
                "active_tasks": capacity_snapshot.active_tasks,
                "queued_tasks": capacity_snapshot.queued_tasks,
                "approval_backlog": capacity_snapshot.approval_backlog,
                "budget_pressure": capacity_snapshot.budget_pressure,
                "continuity_fragility": item.continuity_fragility,
                "provider_degraded": degraded,
            },
        )

    def ack_lease(self, lease_id: str) -> None:
        lease = self.repository.get_queue_lease(lease_id)
        if lease is None:
            raise KeyError(lease_id)
        lease.status = "released"
        lease.released_at = utc_now()
        lease.release_reason = "acknowledged"
        self.repository.save_queue_lease(lease)
        item = self.repository.get_queue_item(lease.queue_item_id)
        if item is not None:
            item.status = "completed"
            item.lease_id = ""
            item.updated_at = utc_now()
            self.repository.save_queue_item(item)
        dispatch = self.repository.latest_dispatch_record(lease.task_id)
        if dispatch is not None and dispatch.lease_id == lease_id:
            dispatch.status = "completed"
            dispatch.completed_at = utc_now()
            self.repository.save_dispatch_record(dispatch)

    def release_lease(self, lease_id: str, *, reason: str, retryable: bool) -> None:
        lease = self.repository.get_queue_lease(lease_id)
        if lease is None:
            raise KeyError(lease_id)
        lease.status = "released"
        lease.released_at = utc_now()
        lease.release_reason = reason
        self.repository.save_queue_lease(lease)
        item = self.repository.get_queue_item(lease.queue_item_id)
        if item is None:
            return
        item.attempt_count += 1
        item.updated_at = utc_now()
        item.lease_id = ""
        if retryable and item.attempt_count < item.max_attempts:
            item.status = "queued"
            item.available_at = utc_now()
        else:
            item.status = "dead_letter"
            item.dead_letter_reason = reason
        self.repository.save_queue_item(item)
        dispatch = self.repository.latest_dispatch_record(lease.task_id)
        if dispatch is not None and dispatch.lease_id == lease_id:
            dispatch.status = item.status
            dispatch.completed_at = utc_now()
            self.repository.save_dispatch_record(dispatch)

    def recover_stale_leases(self, *, now: datetime | None = None, force_expire: bool = False) -> int:
        now = utc_now() if now is None else now
        recovered = 0
        for lease in self.repository.list_queue_leases(status="active"):
            if force_expire or lease.expires_at <= now:
                self.release_lease(lease.lease_id, reason="stale lease recovered", retryable=True)
                recovered += 1
        return recovered

    def _priority_score(self, item: QueueItem) -> int:
        policy = self.repository.latest_queue_priority_policy() or QueuePriorityPolicy(
            version="1.0",
            policy_id="priority-default",
            class_weights={"background_eval": 1, "standard": 10, "recovery": 30},
            resumed_task_bonus=5,
            stale_continuity_bonus=10,
            recovery_priority_bonus=20,
            high_risk_bonus=15,
        )
        score = int(policy.class_weights.get(item.priority_class, 5))
        score += item.operator_priority
        if item.resume_task:
            score += policy.resumed_task_bonus
        if item.continuity_fragility >= 0.7:
            score += policy.stale_continuity_bonus
        if item.recovery_required:
            score += policy.recovery_priority_bonus
        if item.risk_level == "high":
            score += policy.high_risk_bonus
        score -= item.attempt_count
        return score
