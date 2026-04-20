"""Externalizable worker coordination and lease ownership models."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from contract_evidence_os.base import SchemaModel, utc_now
from contract_evidence_os.runtime.backends import BackendHealthRecord, CoordinationBackendDescriptor
from contract_evidence_os.runtime.external_backends import build_redis_client


@dataclass
class WorkerCapabilityRecord(SchemaModel):
    """Capabilities advertised by a worker process."""

    version: str
    worker_id: str
    provider_access: list[str]
    tool_access: list[str]
    role_specialization: list[str]
    supports_degraded_mode: bool
    supports_high_risk: bool
    max_parallel_tasks: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class HostRecord(SchemaModel):
    """Host-level execution identity and maintenance state."""

    version: str
    host_id: str
    hostname: str
    network_identity: str
    status: str
    drain_state: str
    capabilities: list[str]
    lease_pressure: float = 0.0
    created_at: datetime = field(default_factory=utc_now)
    last_seen_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class WorkerHostBinding(SchemaModel):
    """Binding between a worker and its host/endpoint."""

    version: str
    binding_id: str
    worker_id: str
    host_id: str
    endpoint_id: str
    status: str
    bound_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class WorkerEndpointRecord(SchemaModel):
    """Reachability record for a worker endpoint."""

    version: str
    endpoint_id: str
    worker_id: str
    host_id: str
    address: str
    protocol: str
    status: str
    last_seen_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class WorkerLifecycleRecord(SchemaModel):
    """Worker identity, status, and current lease ownership summary."""

    version: str
    worker_id: str
    worker_role: str
    process_identity: str
    heartbeat_state: str
    claimed_capacity: int
    active_leases: list[str]
    startup_time: datetime
    host_id: str = "local-host"
    service_identity: str = ""
    startup_epoch: str = ""
    current_drain_state: str = "running"
    endpoint_address: str = ""
    lease_pressure: float = 0.0
    last_checkpoint_activity: datetime | None = None
    shutdown_state: str = "running"
    local_execution_mode: str = "normal"
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class WorkerHeartbeatRecord(SchemaModel):
    """Periodic worker heartbeat with active load and expiry."""

    version: str
    heartbeat_id: str
    worker_id: str
    host_id: str
    service_identity: str
    heartbeat_state: str
    active_leases: list[str]
    capacity_in_use: int
    queue_pressure: float
    lease_pressure: float = 0.0
    last_checkpoint_activity: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)
    expires_at: datetime = field(default_factory=lambda: utc_now() + timedelta(seconds=30))

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class LeaseOwnershipRecord(SchemaModel):
    """Authoritative lease ownership with fencing token."""

    version: str
    ownership_id: str
    lease_id: str
    queue_item_id: str
    task_id: str
    worker_id: str
    lease_epoch: int
    fencing_token: str
    status: str
    acquired_at: datetime
    expires_at: datetime
    host_id: str = "local-host"
    renewed_at: datetime | None = None
    released_at: datetime | None = None
    reclaim_reason: str = ""

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class DispatchOwnershipRecord(SchemaModel):
    """Ownership record connecting a dispatch attempt to a worker and lease fence."""

    version: str
    ownership_id: str
    dispatch_id: str
    task_id: str
    queue_item_id: str
    lease_id: str
    worker_id: str
    fencing_token: str
    status: str
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class WorkerPressureSnapshot(SchemaModel):
    """Aggregated worker-pool pressure and utilization summary."""

    version: str
    snapshot_id: str
    active_workers: int
    draining_workers: int
    stale_workers: int
    total_claimed_capacity: int
    active_leases: int
    capability_distribution: dict[str, int]
    host_distribution: dict[str, int] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class LeaseRenewalPolicy(SchemaModel):
    """Policy controlling renewal timing and steal eligibility."""

    version: str
    policy_id: str
    renew_before_seconds: int
    max_jitter_seconds: int
    slow_worker_grace_seconds: int
    contention_backoff_seconds: int
    steal_min_age_seconds: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class RenewalAttemptRecord(SchemaModel):
    """Recorded lease renewal attempt."""

    version: str
    attempt_id: str
    lease_id: str
    worker_id: str
    host_id: str
    outcome: str
    latency_ms: float
    previous_expires_at: datetime
    new_expires_at: datetime
    created_at: datetime = field(default_factory=utc_now)
    note: str = ""

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class LeaseExpiryForecast(SchemaModel):
    """Forecast of lease expiry risk used for reclaim and steal decisions."""

    version: str
    forecast_id: str
    lease_id: str
    seconds_remaining: float
    risk_level: str
    recommended_action: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class LeaseContentionRecord(SchemaModel):
    """Record of a challenger attempting to take ownership."""

    version: str
    contention_id: str
    lease_id: str
    current_worker_id: str
    challenger_worker_id: str
    decision: str
    reason: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class WorkStealPolicy(SchemaModel):
    """Policy for conservative, auditable work stealing."""

    version: str
    policy_id: str
    allow_steal_from_draining: bool
    allow_steal_from_stale: bool
    min_lease_age_seconds: int
    max_pressure_to_keep_owner: float
    protect_verification_capacity: bool
    protect_recovery_capacity: bool
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class WorkStealDecision(SchemaModel):
    """Explainable lease steal decision."""

    version: str
    decision_id: str
    lease_id: str
    from_worker_id: str
    to_worker_id: str
    status: str
    reason: str
    safety_checks: dict[str, bool]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class LeaseTransferRecord(SchemaModel):
    """Ownership transfer after reclaim or work steal."""

    version: str
    transfer_id: str
    lease_id: str
    from_worker_id: str
    to_worker_id: str
    previous_epoch: int
    new_epoch: int
    reason: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class OwnershipConflictEvent(SchemaModel):
    """Ownership conflict or stale-owner rejection event."""

    version: str
    event_id: str
    lease_id: str
    stale_worker_id: str
    active_worker_id: str
    rejected_action: str
    summary: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


class CoordinationBackend(Protocol):
    """Coordination boundary for workers, heartbeats, and fenced lease ownership."""

    def descriptor(self) -> CoordinationBackendDescriptor: ...

    def health(self) -> BackendHealthRecord: ...

    def register_worker(
        self,
        *,
        worker_id: str,
        worker_role: str,
        process_identity: str,
        capabilities: WorkerCapabilityRecord,
        claimed_capacity: int,
        started_at: datetime | None = None,
        host_id: str = "local-host",
        service_identity: str = "",
        endpoint_address: str = "",
    ) -> WorkerLifecycleRecord: ...

    def heartbeat(
        self,
        worker_id: str,
        *,
        active_leases: list[str],
        capacity_in_use: int,
        now: datetime | None = None,
        heartbeat_latency_ms: float = 0.0,
    ) -> WorkerHeartbeatRecord: ...

    def claim_lease(
        self,
        *,
        lease_id: str,
        queue_item_id: str,
        task_id: str,
        worker_id: str,
        expires_at: datetime,
        now: datetime | None = None,
        host_id: str | None = None,
    ) -> LeaseOwnershipRecord: ...

    def renew_lease(
        self,
        *,
        lease_id: str,
        worker_id: str,
        fencing_token: str,
        expires_at: datetime,
        now: datetime | None = None,
        policy: LeaseRenewalPolicy | None = None,
        host_id: str | None = None,
    ) -> LeaseOwnershipRecord | None: ...

    def release_lease(
        self,
        *,
        lease_id: str,
        worker_id: str,
        fencing_token: str,
        reason: str,
        now: datetime | None = None,
    ) -> LeaseOwnershipRecord | None: ...

    def validate_fencing(self, *, lease_id: str, worker_id: str, fencing_token: str) -> bool: ...

    def reclaim_stale_workers(
        self,
        *,
        now: datetime | None = None,
        heartbeat_expiry_seconds: int = 30,
    ) -> list[LeaseOwnershipRecord]: ...

    def steal_lease(
        self,
        *,
        lease_id: str,
        queue_item_id: str,
        task_id: str,
        new_worker_id: str,
        now: datetime,
        policy: WorkStealPolicy,
    ) -> WorkStealDecision | None: ...


class SQLiteCoordinationBackend:
    """SQLite reference coordination backend for multi-worker-safe execution."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def descriptor(self) -> CoordinationBackendDescriptor:
        return CoordinationBackendDescriptor(
            version="1.0",
            backend_name="sqlite",
            backend_kind="sqlite",
            supports_host_registration=True,
            supports_heartbeats=True,
            supports_fencing=True,
            supports_work_stealing=True,
            lease_semantics="durable repository-backed fenced ownership",
            durability_guarantee="durable sqlite persistence",
        )

    def health(self) -> BackendHealthRecord:
        return BackendHealthRecord(
            version="1.0",
            backend_name="sqlite",
            backend_kind="sqlite",
            status="available",
            latency_ms=0.0,
            connected=True,
        )

    def register_worker(
        self,
        *,
        worker_id: str,
        worker_role: str,
        process_identity: str,
        capabilities: WorkerCapabilityRecord,
        claimed_capacity: int,
        started_at: datetime | None = None,
        host_id: str = "local-host",
        service_identity: str = "",
        endpoint_address: str = "",
    ) -> WorkerLifecycleRecord:
        started_at = utc_now() if started_at is None else started_at
        self.repository.save_worker_capability(capabilities)
        self.repository.save_host_record(
            HostRecord(
                version="1.0",
                host_id=host_id,
                hostname=host_id,
                network_identity=endpoint_address or host_id,
                status="active",
                drain_state="running",
                capabilities=sorted(set(capabilities.role_specialization)),
                created_at=started_at,
                last_seen_at=started_at,
            )
        )
        record = self.repository.load_worker(worker_id) or WorkerLifecycleRecord(
            version="1.0",
            worker_id=worker_id,
            worker_role=worker_role,
            process_identity=process_identity,
            heartbeat_state="active",
            claimed_capacity=claimed_capacity,
            active_leases=[],
            startup_time=started_at,
            host_id=host_id,
            service_identity=service_identity,
            startup_epoch=f"epoch-{started_at.timestamp():.0f}",
            endpoint_address=endpoint_address,
            updated_at=started_at,
        )
        record.worker_role = worker_role
        record.process_identity = process_identity
        record.claimed_capacity = claimed_capacity
        record.host_id = host_id
        record.service_identity = service_identity
        record.endpoint_address = endpoint_address
        record.heartbeat_state = "active"
        record.shutdown_state = "running"
        record.current_drain_state = "running"
        record.updated_at = started_at
        self.repository.save_worker(record)
        endpoint_id = f"endpoint-{worker_id}"
        self.repository.save_worker_endpoint(
            WorkerEndpointRecord(
                version="1.0",
                endpoint_id=endpoint_id,
                worker_id=worker_id,
                host_id=host_id,
                address=endpoint_address or host_id,
                protocol="internal",
                status="active",
                last_seen_at=started_at,
            )
        )
        self.repository.save_worker_host_binding(
            WorkerHostBinding(
                version="1.0",
                binding_id=f"binding-{worker_id}",
                worker_id=worker_id,
                host_id=host_id,
                endpoint_id=endpoint_id,
                status="active",
                bound_at=started_at,
            )
        )
        self.repository.save_worker_pressure_snapshot(self.worker_pool_snapshot(now=started_at))
        return record

    def heartbeat(
        self,
        worker_id: str,
        *,
        active_leases: list[str],
        capacity_in_use: int,
        now: datetime | None = None,
        heartbeat_latency_ms: float = 0.0,
    ) -> WorkerHeartbeatRecord:
        now = utc_now() if now is None else now
        worker = self.repository.load_worker(worker_id)
        heartbeat = WorkerHeartbeatRecord(
            version="1.0",
            heartbeat_id=f"worker-heartbeat-{uuid4().hex[:10]}",
            worker_id=worker_id,
            host_id="local-host" if worker is None else worker.host_id,
            service_identity="" if worker is None else worker.service_identity,
            heartbeat_state="active",
            active_leases=active_leases,
            capacity_in_use=capacity_in_use,
            queue_pressure=float(len(active_leases)),
            lease_pressure=max(float(len(active_leases)), heartbeat_latency_ms / 1000.0),
            created_at=now,
            expires_at=now + timedelta(seconds=30),
        )
        self.repository.save_worker_heartbeat(heartbeat)
        if worker is not None:
            worker.active_leases = active_leases
            worker.heartbeat_state = "active"
            worker.updated_at = now
            worker.last_checkpoint_activity = now
            worker.lease_pressure = heartbeat.lease_pressure
            self.repository.save_worker(worker)
            host = self.repository.load_host_record(worker.host_id)
            if host is not None:
                host.last_seen_at = now
                host.status = "active"
                host.lease_pressure = heartbeat.lease_pressure
                self.repository.save_host_record(host)
            endpoint = self.repository.load_worker_endpoint(worker_id)
            if endpoint is not None:
                endpoint.last_seen_at = now
                endpoint.status = "active"
                self.repository.save_worker_endpoint(endpoint)
        self.repository.save_worker_pressure_snapshot(self.worker_pool_snapshot(now=now))
        return heartbeat

    def set_worker_mode(self, worker_id: str, *, mode_name: str, shutdown_state: str | None = None) -> WorkerLifecycleRecord | None:
        worker = self.repository.load_worker(worker_id)
        if worker is None:
            return None
        worker.local_execution_mode = mode_name
        worker.current_drain_state = mode_name
        if shutdown_state is not None:
            worker.shutdown_state = shutdown_state
        worker.updated_at = utc_now()
        self.repository.save_worker(worker)
        host = self.repository.load_host_record(worker.host_id)
        if host is not None and shutdown_state is not None:
            host.drain_state = shutdown_state
            host.last_seen_at = worker.updated_at
            self.repository.save_host_record(host)
        return worker

    def claim_lease(
        self,
        *,
        lease_id: str,
        queue_item_id: str,
        task_id: str,
        worker_id: str,
        expires_at: datetime,
        now: datetime | None = None,
        host_id: str | None = None,
    ) -> LeaseOwnershipRecord:
        now = utc_now() if now is None else now
        current = self.repository.latest_lease_ownership(lease_id)
        epoch = 1 if current is None else current.lease_epoch + 1
        if current is not None and current.status == "active":
            current.status = "fenced"
            current.released_at = now
            current.reclaim_reason = "superseded_by_new_owner"
            self.repository.save_lease_ownership(current)
        record = LeaseOwnershipRecord(
            version="1.0",
            ownership_id=f"lease-owner-{uuid4().hex[:10]}",
            lease_id=lease_id,
            queue_item_id=queue_item_id,
            task_id=task_id,
            worker_id=worker_id,
            host_id=host_id or ("local-host" if self.repository.load_worker(worker_id) is None else self.repository.load_worker(worker_id).host_id),
            lease_epoch=epoch,
            fencing_token=f"fence-{uuid4().hex}",
            status="active",
            acquired_at=now,
            expires_at=expires_at,
        )
        self.repository.save_lease_ownership(record)
        worker = self.repository.load_worker(worker_id)
        if worker is not None:
            leases = [lease for lease in worker.active_leases if lease != lease_id]
            worker.active_leases = [*leases, lease_id]
            worker.lease_pressure = float(len(worker.active_leases))
            worker.updated_at = now
            self.repository.save_worker(worker)
        return record

    def renew_lease(
        self,
        *,
        lease_id: str,
        worker_id: str,
        fencing_token: str,
        expires_at: datetime,
        now: datetime | None = None,
        policy: LeaseRenewalPolicy | None = None,
        host_id: str | None = None,
    ) -> LeaseOwnershipRecord | None:
        now = utc_now() if now is None else now
        started = time.perf_counter()
        current = self.repository.latest_lease_ownership(lease_id)
        if current is None or current.worker_id != worker_id or current.fencing_token != fencing_token or current.status != "active":
            if current is not None:
                self.repository.save_ownership_conflict_event(
                    OwnershipConflictEvent(
                        version="1.0",
                        event_id=f"ownership-conflict-{uuid4().hex[:10]}",
                        lease_id=lease_id,
                        stale_worker_id=worker_id,
                        active_worker_id=current.worker_id,
                        rejected_action="renew_lease",
                        summary="stale or fenced owner attempted lease renewal",
                        created_at=now,
                    )
                )
            return None
        previous_expires_at = current.expires_at
        current.renewed_at = now
        current.expires_at = expires_at
        self.repository.save_lease_ownership(current)
        self.repository.save_renewal_attempt(
            RenewalAttemptRecord(
                version="1.0",
                attempt_id=f"renewal-attempt-{uuid4().hex[:10]}",
                lease_id=lease_id,
                worker_id=worker_id,
                host_id=host_id or current.host_id,
                outcome="renewed",
                latency_ms=(time.perf_counter() - started) * 1000.0,
                previous_expires_at=previous_expires_at,
                new_expires_at=expires_at,
                created_at=now,
                note="" if policy is None else policy.policy_id,
            )
        )
        self.repository.save_lease_expiry_forecast(
            LeaseExpiryForecast(
                version="1.0",
                forecast_id=f"lease-forecast-{uuid4().hex[:10]}",
                lease_id=lease_id,
                seconds_remaining=max((expires_at - now).total_seconds(), 0.0),
                risk_level="low",
                recommended_action="continue",
                created_at=now,
            )
        )
        return current

    def release_lease(
        self,
        *,
        lease_id: str,
        worker_id: str,
        fencing_token: str,
        reason: str,
        now: datetime | None = None,
    ) -> LeaseOwnershipRecord | None:
        now = utc_now() if now is None else now
        current = self.repository.latest_lease_ownership(lease_id)
        if current is None or current.worker_id != worker_id or current.fencing_token != fencing_token:
            if current is not None:
                self.repository.save_ownership_conflict_event(
                    OwnershipConflictEvent(
                        version="1.0",
                        event_id=f"ownership-conflict-{uuid4().hex[:10]}",
                        lease_id=lease_id,
                        stale_worker_id=worker_id,
                        active_worker_id=current.worker_id,
                        rejected_action="release_lease",
                        summary="stale or fenced owner attempted lease release",
                        created_at=now,
                    )
                )
            return None
        current.status = "released"
        current.released_at = now
        current.reclaim_reason = reason
        self.repository.save_lease_ownership(current)
        worker = self.repository.load_worker(worker_id)
        if worker is not None:
            worker.active_leases = [lease for lease in worker.active_leases if lease != lease_id]
            worker.updated_at = now
            self.repository.save_worker(worker)
        return current

    def validate_fencing(self, *, lease_id: str, worker_id: str, fencing_token: str) -> bool:
        current = self.repository.latest_lease_ownership(lease_id)
        if current is None:
            return False
        return current.status == "active" and current.worker_id == worker_id and current.fencing_token == fencing_token

    def steal_lease(
        self,
        *,
        lease_id: str,
        queue_item_id: str,
        task_id: str,
        new_worker_id: str,
        now: datetime,
        policy: WorkStealPolicy,
    ) -> WorkStealDecision | None:
        current = self.repository.latest_lease_ownership(lease_id)
        if current is None or current.status != "active":
            return None
        current_worker = self.repository.load_worker(current.worker_id)
        age_seconds = max((now - current.acquired_at).total_seconds(), 0.0)
        safety_checks = {
            "lease_old_enough": age_seconds >= policy.min_lease_age_seconds,
            "owner_draining": current_worker is not None and current_worker.shutdown_state == "draining",
            "owner_stale": current_worker is not None and current_worker.heartbeat_state == "stale",
            "owner_pressure_low": current_worker is None or current_worker.lease_pressure <= policy.max_pressure_to_keep_owner,
        }
        allowed = safety_checks["lease_old_enough"] and (
            (policy.allow_steal_from_draining and safety_checks["owner_draining"])
            or (policy.allow_steal_from_stale and safety_checks["owner_stale"])
        )
        reason = "work_steal_not_allowed"
        if not allowed:
            self.repository.save_lease_contention_record(
                LeaseContentionRecord(
                    version="1.0",
                    contention_id=f"lease-contention-{uuid4().hex[:10]}",
                    lease_id=lease_id,
                    current_worker_id=current.worker_id,
                    challenger_worker_id=new_worker_id,
                    decision="rejected",
                    reason=reason,
                    created_at=now,
                )
            )
            return None
        replacement = self.claim_lease(
            lease_id=lease_id,
            queue_item_id=queue_item_id,
            task_id=task_id,
            worker_id=new_worker_id,
            expires_at=now + timedelta(seconds=30),
            now=now,
        )
        self.repository.save_work_steal_decision(
            WorkStealDecision(
                version="1.0",
                decision_id=f"work-steal-{uuid4().hex[:10]}",
                lease_id=lease_id,
                from_worker_id=current.worker_id,
                to_worker_id=new_worker_id,
                status="stolen",
                reason="owner_draining_or_stale",
                safety_checks=safety_checks,
                created_at=now,
            )
        )
        self.repository.save_lease_transfer_record(
            LeaseTransferRecord(
                version="1.0",
                transfer_id=f"lease-transfer-{uuid4().hex[:10]}",
                lease_id=lease_id,
                from_worker_id=current.worker_id,
                to_worker_id=new_worker_id,
                previous_epoch=current.lease_epoch,
                new_epoch=replacement.lease_epoch,
                reason="controlled_work_steal",
                created_at=now,
            )
        )
        self.repository.save_lease_contention_record(
            LeaseContentionRecord(
                version="1.0",
                contention_id=f"lease-contention-{uuid4().hex[:10]}",
                lease_id=lease_id,
                current_worker_id=current.worker_id,
                challenger_worker_id=new_worker_id,
                decision="accepted",
                reason="policy_allowed",
                created_at=now,
            )
        )
        return self.repository.list_work_steal_decisions()[-1]

    def claim_dispatch(
        self,
        *,
        dispatch_id: str,
        task_id: str,
        queue_item_id: str,
        lease_id: str,
        worker_id: str,
        fencing_token: str,
    ) -> DispatchOwnershipRecord:
        current = self.repository.latest_dispatch_ownership(dispatch_id)
        if current is not None and current.status == "active":
            current.status = "superseded"
            current.updated_at = utc_now()
            self.repository.save_dispatch_ownership(current)
        record = DispatchOwnershipRecord(
            version="1.0",
            ownership_id=f"dispatch-owner-{uuid4().hex[:10]}",
            dispatch_id=dispatch_id,
            task_id=task_id,
            queue_item_id=queue_item_id,
            lease_id=lease_id,
            worker_id=worker_id,
            fencing_token=fencing_token,
            status="active",
        )
        self.repository.save_dispatch_ownership(record)
        return record

    def reclaim_stale_workers(
        self,
        *,
        now: datetime | None = None,
        heartbeat_expiry_seconds: int = 30,
    ) -> list[LeaseOwnershipRecord]:
        now = utc_now() if now is None else now
        reclaimed: list[LeaseOwnershipRecord] = []
        cutoff = now - timedelta(seconds=heartbeat_expiry_seconds)
        for worker in self.repository.list_workers():
            heartbeat = self.repository.latest_worker_heartbeat(worker.worker_id)
            last_seen = heartbeat.created_at if heartbeat is not None else worker.updated_at
            if last_seen > cutoff:
                continue
            worker.heartbeat_state = "stale"
            worker.shutdown_state = "stale"
            worker.updated_at = now
            self.repository.save_worker(worker)
            host = self.repository.load_host_record(worker.host_id)
            if host is not None:
                host.status = "stale"
                host.last_seen_at = now
                self.repository.save_host_record(host)
            for ownership in self.repository.list_lease_ownerships(worker_id=worker.worker_id, statuses=["active"]):
                ownership.status = "reclaimed"
                ownership.released_at = now
                ownership.reclaim_reason = "worker_stale"
                self.repository.save_lease_ownership(ownership)
                reclaimed.append(ownership)
        self.repository.save_worker_pressure_snapshot(self.worker_pool_snapshot(now=now))
        return reclaimed

    def worker_pool_snapshot(self, *, now: datetime | None = None) -> WorkerPressureSnapshot:
        now = utc_now() if now is None else now
        workers = self.repository.list_workers()
        return WorkerPressureSnapshot(
            version="1.0",
            snapshot_id=f"worker-pool-{uuid4().hex[:10]}",
            active_workers=len([worker for worker in workers if worker.shutdown_state == "running"]),
            draining_workers=len([worker for worker in workers if worker.shutdown_state == "draining"]),
            stale_workers=len([worker for worker in workers if worker.heartbeat_state == "stale"]),
            total_claimed_capacity=sum(worker.claimed_capacity for worker in workers),
            active_leases=len([ownership for ownership in self.repository.list_lease_ownerships(statuses=["active"])]),
            capability_distribution={
                role: len([cap for cap in self.repository.list_worker_capabilities() if role in cap.role_specialization])
                for role in {"Researcher", "Builder", "Verifier", "Strategist", "Archivist"}
            },
            host_distribution={
                host.host_id: len([worker for worker in workers if worker.host_id == host.host_id])
                for host in self.repository.list_host_records()
            },
            created_at=now,
        )


class RedisCoordinationBackend(SQLiteCoordinationBackend):
    """Redis-backed coordination backend with repository mirroring for replay and audit."""

    def __init__(
        self,
        repository: Any,
        *,
        client: Any | None = None,
        url: str | None = None,
        namespace: str = "ceos",
    ) -> None:
        super().__init__(repository)
        self.client = build_redis_client(url=url, client=client)
        self.namespace = namespace

    def descriptor(self) -> CoordinationBackendDescriptor:
        return CoordinationBackendDescriptor(
            version="1.0",
            backend_name="redis",
            backend_kind="redis",
            supports_host_registration=True,
            supports_heartbeats=True,
            supports_fencing=True,
            supports_work_stealing=True,
            lease_semantics="redis current-owner fencing with sqlite mirror history",
            durability_guarantee="redis live state plus sqlite mirrored audit/replay records",
        )

    def health(self) -> BackendHealthRecord:
        started = time.perf_counter()
        try:
            self.client.ping()
            return BackendHealthRecord(
                version="1.0",
                backend_name="redis",
                backend_kind="redis",
                status="available",
                latency_ms=(time.perf_counter() - started) * 1000.0,
                connected=True,
            )
        except Exception as exc:  # pragma: no cover - outage tests cover this
            return BackendHealthRecord(
                version="1.0",
                backend_name="redis",
                backend_kind="redis",
                status="degraded",
                latency_ms=0.0,
                connected=False,
                last_error=str(exc),
            )

    def register_worker(
        self,
        *,
        worker_id: str,
        worker_role: str,
        process_identity: str,
        capabilities: WorkerCapabilityRecord,
        claimed_capacity: int,
        started_at: datetime | None = None,
        host_id: str = "local-host",
        service_identity: str = "",
        endpoint_address: str = "",
    ) -> WorkerLifecycleRecord:
        record = super().register_worker(
            worker_id=worker_id,
            worker_role=worker_role,
            process_identity=process_identity,
            capabilities=capabilities,
            claimed_capacity=claimed_capacity,
            started_at=started_at,
            host_id=host_id,
            service_identity=service_identity,
            endpoint_address=endpoint_address,
        )
        self.client.set(self._worker_key(worker_id), self._dumps(record))
        self.client.set(self._host_key(host_id), self._dumps(self.repository.load_host_record(host_id)))
        self.client.set(self._worker_capability_key(worker_id), self._dumps(capabilities))
        return record

    def heartbeat(
        self,
        worker_id: str,
        *,
        active_leases: list[str],
        capacity_in_use: int,
        now: datetime | None = None,
        heartbeat_latency_ms: float = 0.0,
    ) -> WorkerHeartbeatRecord:
        heartbeat = super().heartbeat(
            worker_id,
            active_leases=active_leases,
            capacity_in_use=capacity_in_use,
            now=now,
            heartbeat_latency_ms=heartbeat_latency_ms,
        )
        self.client.set(self._heartbeat_key(worker_id), self._dumps(heartbeat))
        self.client.expire(self._heartbeat_key(worker_id), 60)
        worker = self.repository.load_worker(worker_id)
        if worker is not None:
            self.client.set(self._worker_key(worker_id), self._dumps(worker))
            host = self.repository.load_host_record(worker.host_id)
            if host is not None:
                self.client.set(self._host_key(worker.host_id), self._dumps(host))
        return heartbeat

    def claim_lease(
        self,
        *,
        lease_id: str,
        queue_item_id: str,
        task_id: str,
        worker_id: str,
        expires_at: datetime,
        now: datetime | None = None,
        host_id: str | None = None,
    ) -> LeaseOwnershipRecord:
        record = super().claim_lease(
            lease_id=lease_id,
            queue_item_id=queue_item_id,
            task_id=task_id,
            worker_id=worker_id,
            expires_at=expires_at,
            now=now,
            host_id=host_id,
        )
        self.client.set(self._lease_key(lease_id), self._dumps(record))
        return record

    def renew_lease(
        self,
        *,
        lease_id: str,
        worker_id: str,
        fencing_token: str,
        expires_at: datetime,
        now: datetime | None = None,
        policy: LeaseRenewalPolicy | None = None,
        host_id: str | None = None,
    ) -> LeaseOwnershipRecord | None:
        record = super().renew_lease(
            lease_id=lease_id,
            worker_id=worker_id,
            fencing_token=fencing_token,
            expires_at=expires_at,
            now=now,
            policy=policy,
            host_id=host_id,
        )
        if record is not None:
            self.client.set(self._lease_key(lease_id), self._dumps(record))
        return record

    def release_lease(
        self,
        *,
        lease_id: str,
        worker_id: str,
        fencing_token: str,
        reason: str,
        now: datetime | None = None,
    ) -> LeaseOwnershipRecord | None:
        record = super().release_lease(
            lease_id=lease_id,
            worker_id=worker_id,
            fencing_token=fencing_token,
            reason=reason,
            now=now,
        )
        if record is not None:
            self.client.set(self._lease_key(lease_id), self._dumps(record))
        return record

    def validate_fencing(self, *, lease_id: str, worker_id: str, fencing_token: str) -> bool:
        raw = self.client.get(self._lease_key(lease_id))
        if raw is None:
            return super().validate_fencing(lease_id=lease_id, worker_id=worker_id, fencing_token=fencing_token)
        record = LeaseOwnershipRecord.from_dict(json.loads(raw))
        return record.status == "active" and record.worker_id == worker_id and record.fencing_token == fencing_token

    def reclaim_stale_workers(
        self,
        *,
        now: datetime | None = None,
        heartbeat_expiry_seconds: int = 30,
    ) -> list[LeaseOwnershipRecord]:
        reclaimed = super().reclaim_stale_workers(now=now, heartbeat_expiry_seconds=heartbeat_expiry_seconds)
        for ownership in reclaimed:
            self.client.set(self._lease_key(ownership.lease_id), self._dumps(ownership))
        for worker in self.repository.list_workers():
            self.client.set(self._worker_key(worker.worker_id), self._dumps(worker))
        return reclaimed

    def steal_lease(
        self,
        *,
        lease_id: str,
        queue_item_id: str,
        task_id: str,
        new_worker_id: str,
        now: datetime,
        policy: WorkStealPolicy,
    ) -> WorkStealDecision | None:
        decision = super().steal_lease(
            lease_id=lease_id,
            queue_item_id=queue_item_id,
            task_id=task_id,
            new_worker_id=new_worker_id,
            now=now,
            policy=policy,
        )
        latest = self.repository.latest_lease_ownership(lease_id)
        if latest is not None:
            self.client.set(self._lease_key(lease_id), self._dumps(latest))
        return decision

    def _dumps(self, value: Any) -> str:
        return json.dumps(value.to_dict(), ensure_ascii=True)

    def _worker_key(self, worker_id: str) -> str:
        return f"{self.namespace}:coord:worker:{worker_id}"

    def _worker_capability_key(self, worker_id: str) -> str:
        return f"{self.namespace}:coord:capability:{worker_id}"

    def _heartbeat_key(self, worker_id: str) -> str:
        return f"{self.namespace}:coord:heartbeat:{worker_id}"

    def _lease_key(self, lease_id: str) -> str:
        return f"{self.namespace}:coord:lease:{lease_id}"

    def _host_key(self, host_id: str) -> str:
        return f"{self.namespace}:coord:host:{host_id}"
