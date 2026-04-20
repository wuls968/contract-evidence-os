"""Provider-pool balancing and reservation management."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from contract_evidence_os.base import SchemaModel, utc_now


@dataclass
class ProviderCapacityRecord(SchemaModel):
    """Declared provider-pool capacity and reservation slots."""

    version: str
    provider_name: str
    max_parallel: int
    reservation_slots: dict[str, int]
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderPoolState(SchemaModel):
    """Current pool-wide summary across providers."""

    version: str
    pool_id: str
    active_reservations: int
    total_available_parallelism: int
    degraded_providers: list[str]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderPressureSnapshot(SchemaModel):
    """Observed sustained-load pressure across the provider pool."""

    version: str
    snapshot_id: str
    active_worker_demand: int
    projected_demand: int
    provider_pressures: dict[str, float]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderReservation(SchemaModel):
    """Reservation for recovery, verification, or other critical provider usage."""

    version: str
    reservation_id: str
    provider_name: str
    reservation_type: str
    task_id: str
    worker_id: str
    status: str
    created_at: datetime
    expires_at: datetime
    host_id: str = ""

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderBalanceDecision(SchemaModel):
    """Explainable provider-pool balancing decision."""

    version: str
    decision_id: str
    task_id: str
    worker_id: str
    workload: str
    risk_level: str
    chosen_provider: str
    candidate_providers: list[str]
    reservation_applied: bool
    delayed: bool
    rationale: str
    signals: dict[str, float]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderPoolEvent(SchemaModel):
    """Persisted provider-pool governance event."""

    version: str
    event_id: str
    provider_name: str
    event_type: str
    summary: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderFairnessRecord(SchemaModel):
    """Cross-host fairness view for one provider."""

    version: str
    record_id: str
    provider_name: str
    worker_allocations: dict[str, int]
    host_allocations: dict[str, int]
    fairness_score: float
    reservation_pressure: float
    delayed_tasks: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderPoolBalancePolicy(SchemaModel):
    """Policy tuning for provider balancing under sustained load."""

    version: str
    policy_id: str
    fairness_weight: float
    degradation_penalty: float
    rate_pressure_weight: float
    reservation_pressure_weight: float
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ReservationPolicy(SchemaModel):
    """Reservation policy for critical workloads."""

    version: str
    policy_id: str
    protected_workloads: list[str]
    reserve_verification_slots: int
    reserve_recovery_slots: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderFairnessPolicy(SchemaModel):
    """Fairness policy across workers and hosts."""

    version: str
    policy_id: str
    max_host_share: float
    max_worker_share: float
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SustainedPressurePolicy(SchemaModel):
    """Delay/defer policy when provider pressure is sustained."""

    version: str
    policy_id: str
    pressure_delay_threshold: float
    protect_critical_workloads: list[str]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


class ProviderPoolManager:
    """Balance providers using sustained-load pressure, reservations, and fairness hints."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def register_capacity(self, provider_name: str, *, max_parallel: int, reservation_slots: dict[str, int]) -> ProviderCapacityRecord:
        record = ProviderCapacityRecord(
            version="1.0",
            provider_name=provider_name,
            max_parallel=max_parallel,
            reservation_slots=reservation_slots,
        )
        self.repository.save_provider_capacity_record(record)
        self.repository.save_provider_pool_state(self.pool_state())
        return record

    def reserve(
        self,
        *,
        provider_name: str,
        reservation_type: str,
        task_id: str,
        worker_id: str,
        expires_at: datetime,
        host_id: str | None = None,
    ) -> ProviderReservation:
        worker = self.repository.load_worker(worker_id) if hasattr(self.repository, "load_worker") else None
        reservation = ProviderReservation(
            version="1.0",
            reservation_id=f"provider-reservation-{uuid4().hex[:10]}",
            provider_name=provider_name,
            reservation_type=reservation_type,
            task_id=task_id,
            worker_id=worker_id,
            host_id=host_id or ("" if worker is None else worker.host_id),
            status="active",
            created_at=utc_now(),
            expires_at=expires_at,
        )
        self.repository.save_provider_reservation(reservation)
        self.repository.save_provider_pool_state(self.pool_state())
        return reservation

    def release_reservation(self, reservation_id: str) -> ProviderReservation | None:
        reservation = self.repository.load_provider_reservation(reservation_id)
        if reservation is None:
            return None
        reservation.status = "released"
        self.repository.save_provider_reservation(reservation)
        self.repository.save_provider_pool_state(self.pool_state())
        return reservation

    def pressure_snapshot(self, *, now: datetime | None = None) -> ProviderPressureSnapshot:
        now = utc_now() if now is None else now
        health = {record.provider_name: record for record in self.repository.list_provider_health_records()}
        reservations = [item for item in self.repository.list_provider_reservations() if item.status == "active" and item.expires_at > now]
        snapshot = ProviderPressureSnapshot(
            version="1.0",
            snapshot_id=f"provider-pressure-{uuid4().hex[:10]}",
            active_worker_demand=len({item.worker_id for item in reservations}),
            projected_demand=len(reservations),
            provider_pressures={
                provider_name: float(record.rate_limit_pressure + (0.5 if record.availability_state != "available" else 0.0))
                for provider_name, record in health.items()
            },
            created_at=now,
        )
        self.repository.save_provider_pressure_snapshot(snapshot)
        return snapshot

    def fairness_snapshot(self, *, now: datetime | None = None) -> list[ProviderFairnessRecord]:
        now = utc_now() if now is None else now
        reservations = [item for item in self.repository.list_provider_reservations() if item.status == "active" and item.expires_at > now]
        decisions = self.repository.list_provider_balance_decisions()
        records: list[ProviderFairnessRecord] = []
        for provider_name in {item.provider_name for item in reservations} | {item.provider_name for item in self.repository.list_provider_capacity_records()}:
            provider_reservations = [item for item in reservations if item.provider_name == provider_name]
            worker_allocations: dict[str, int] = {}
            host_allocations: dict[str, int] = {}
            for item in provider_reservations:
                worker_allocations[item.worker_id] = worker_allocations.get(item.worker_id, 0) + 1
                host = item.host_id or "unknown"
                host_allocations[host] = host_allocations.get(host, 0) + 1
            total = max(sum(worker_allocations.values()), 1)
            largest_host_share = max(host_allocations.values(), default=0) / total
            fairness = max(0.0, 1.0 - largest_host_share)
            delayed_tasks = len([item for item in decisions if item.chosen_provider == "" and provider_name in item.candidate_providers])
            record = ProviderFairnessRecord(
                version="1.0",
                record_id=f"provider-fairness-{uuid4().hex[:10]}",
                provider_name=provider_name,
                worker_allocations=worker_allocations,
                host_allocations=host_allocations,
                fairness_score=fairness,
                reservation_pressure=len(provider_reservations) / max(total, 1),
                delayed_tasks=delayed_tasks,
                created_at=now,
            )
            self.repository.save_provider_fairness_record(record)
            records.append(record)
        return records

    def pool_state(self, *, now: datetime | None = None) -> ProviderPoolState:
        now = utc_now() if now is None else now
        capacities = self.repository.list_provider_capacity_records()
        reservations = [item for item in self.repository.list_provider_reservations() if item.status == "active" and item.expires_at > now]
        degraded = [
            item.provider_name
            for item in self.repository.list_provider_health_records()
            if item.availability_state != "available"
        ]
        state = ProviderPoolState(
            version="1.0",
            pool_id=f"provider-pool-{uuid4().hex[:10]}",
            active_reservations=len(reservations),
            total_available_parallelism=sum(item.max_parallel for item in capacities),
            degraded_providers=sorted(set(degraded)),
            created_at=now,
        )
        return state

    def balance(
        self,
        *,
        candidate_providers: list[str],
        task_id: str,
        worker_id: str,
        workload: str,
        risk_level: str,
        now: datetime | None = None,
    ) -> ProviderBalanceDecision:
        now = utc_now() if now is None else now
        health = {record.provider_name: record for record in self.repository.list_provider_health_records()}
        capacities = {record.provider_name: record for record in self.repository.list_provider_capacity_records()}
        reservations = [
            item
            for item in self.repository.list_provider_reservations()
            if item.status == "active" and item.expires_at > now
        ]
        worker = self.repository.load_worker(worker_id) if hasattr(self.repository, "load_worker") else None
        host_id = "" if worker is None else worker.host_id
        per_worker = {
            provider_name: len([item for item in reservations if item.provider_name == provider_name and item.worker_id == worker_id])
            for provider_name in candidate_providers
        }
        per_host = {
            provider_name: len([item for item in reservations if item.provider_name == provider_name and item.host_id == host_id and host_id])
            for provider_name in candidate_providers
        }
        scores: dict[str, float] = {}
        reservation_applied = False
        for provider_name in candidate_providers:
            record = health.get(provider_name)
            capacity = capacities.get(provider_name)
            active_reservations = [item for item in reservations if item.provider_name == provider_name]
            reserved_slots = 0 if capacity is None else int(capacity.reservation_slots.get(workload, 0))
            worker_pressure = per_worker.get(provider_name, 0)
            score = 100.0
            if record is not None:
                score -= record.rate_limit_pressure * 40.0
                score -= 30.0 if record.availability_state not in {"available", "degraded"} else 0.0
                score -= 10.0 if record.circuit_state == "open" else 0.0
            if capacity is not None:
                score -= max(0, len(active_reservations) - reserved_slots) * 15.0
            score -= worker_pressure * 5.0
            score -= per_host.get(provider_name, 0) * 4.0
            if any(item.task_id == task_id and item.reservation_type == workload for item in active_reservations):
                score += 20.0
                reservation_applied = True
            elif workload in {"verification", "recovery"} and reserved_slots > len(active_reservations):
                score += 15.0
                reservation_applied = True
            if risk_level == "high" and provider_name.startswith("openai"):
                score += 5.0
            scores[provider_name] = score
        chosen_provider = max(candidate_providers, key=lambda name: scores.get(name, float("-inf")), default="")
        delayed = chosen_provider == "" or scores.get(chosen_provider, -1.0) < 0.0
        decision = ProviderBalanceDecision(
            version="1.0",
            decision_id=f"provider-balance-{uuid4().hex[:10]}",
            task_id=task_id,
            worker_id=worker_id,
            workload=workload,
            risk_level=risk_level,
            chosen_provider="" if delayed else chosen_provider,
            candidate_providers=candidate_providers,
            reservation_applied=reservation_applied,
            delayed=delayed,
            rationale="provider pool balancing using pressure, reservations, and fairness",
            signals=scores,
            created_at=now,
        )
        self.repository.save_provider_balance_decision(decision)
        self.repository.save_provider_pool_event(
            ProviderPoolEvent(
                version="1.0",
                event_id=f"provider-pool-event-{uuid4().hex[:10]}",
                provider_name=chosen_provider or "pool",
                event_type="provider_delayed" if delayed else "provider_selected",
                summary=f"{workload} selected {chosen_provider or 'none'} under sustained-load balancing.",
                created_at=now,
            )
        )
        self.repository.save_provider_pool_state(self.pool_state(now=now))
        self.fairness_snapshot(now=now)
        return decision
