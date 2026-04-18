"""Externalizable queue and storage boundaries with SQLite reference implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from contract_evidence_os.base import SchemaModel, utc_now
from contract_evidence_os.runtime.queueing import QueueItem, QueueLease


@dataclass
class QueueCapabilityDescriptor(SchemaModel):
    """Capabilities exposed by a queue backend."""

    version: str
    backend_name: str
    supports_priority: bool
    supports_leases: bool
    supports_renewal: bool
    supports_dead_letter: bool
    supports_fencing: bool

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class BackendCapabilityDescriptor(SchemaModel):
    """Generic capability and deployment assumptions for one backend."""

    version: str
    backend_name: str
    backend_kind: str
    scope: str
    durability_guarantee: str
    lease_semantics: str
    heartbeat_support: bool
    ordering_assumption: str
    reconnect_behavior: str
    operational_limit: str
    deployment_assumption: str

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class QueueBackendDescriptor(SchemaModel):
    """Descriptor for a queue backend."""

    version: str
    backend_name: str
    backend_kind: str
    supports_priority: bool
    supports_leases: bool
    supports_renewal: bool
    supports_dead_letter: bool
    supports_fencing: bool
    durability_guarantee: str

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class CoordinationBackendDescriptor(SchemaModel):
    """Descriptor for a coordination backend."""

    version: str
    backend_name: str
    backend_kind: str
    supports_host_registration: bool
    supports_heartbeats: bool
    supports_fencing: bool
    supports_work_stealing: bool
    lease_semantics: str
    durability_guarantee: str

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class BackendHealthRecord(SchemaModel):
    """Health view for one backend instance."""

    version: str
    backend_name: str
    backend_kind: str
    status: str
    latency_ms: float
    connected: bool
    last_error: str = ""
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class BackendPressureSnapshot(SchemaModel):
    """Observed pressure on one backend."""

    version: str
    snapshot_id: str
    backend_name: str
    queue_depth: int
    active_leases: int
    active_workers: int
    delayed_tasks: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class QueueOperationResult(SchemaModel):
    """Result of a queue backend mutation."""

    version: str
    operation: str
    succeeded: bool
    status: str
    reason: str = ""
    queue_item_id: str = ""
    lease_id: str = ""
    fencing_token: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


class QueueBackend(Protocol):
    """Queue boundary for externalizable lease-safe execution."""

    capability: QueueCapabilityDescriptor

    def descriptor(self) -> QueueBackendDescriptor: ...

    def health(self) -> BackendHealthRecord: ...

    def enqueue(self, item: QueueItem) -> QueueOperationResult: ...

    def list_ready(self, *, queue_name: str, now: datetime | None = None) -> list[QueueItem]: ...

    def acquire_lease(
        self,
        *,
        queue_item_id: str,
        worker_id: str,
        lease_timeout_seconds: int,
        now: datetime | None = None,
    ) -> QueueLease: ...

    def renew_lease(
        self,
        *,
        lease_id: str,
        worker_id: str,
        fencing_token: str,
        extend_seconds: int,
        now: datetime | None = None,
    ) -> QueueLease | None: ...

    def acknowledge(
        self,
        *,
        lease_id: str,
        worker_id: str,
        fencing_token: str,
        now: datetime | None = None,
    ) -> QueueOperationResult: ...

    def release(
        self,
        *,
        lease_id: str,
        worker_id: str,
        fencing_token: str,
        reason: str,
        retryable: bool,
        now: datetime | None = None,
    ) -> QueueOperationResult: ...

    def force_requeue(self, *, lease_id: str, reason: str, now: datetime | None = None) -> QueueOperationResult: ...


class TaskStateStore(Protocol):
    """Minimal task-state storage boundary."""

    def save_task(self, task_id: str, status: str, request: dict[str, Any], current_phase: str, **kwargs: Any) -> None: ...
    def get_task(self, task_id: str) -> dict[str, Any] | None: ...
    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]: ...


class AuditStateStore(Protocol):
    """Minimal audit boundary."""

    def query_audit(self, task_id: str | None = None, actor: str | None = None) -> list[Any]: ...


class SQLiteQueueBackend:
    """SQLite-backed queue backend that honors fenced lease ownership when present."""

    capability = QueueCapabilityDescriptor(
        version="1.0",
        backend_name="sqlite",
        supports_priority=True,
        supports_leases=True,
        supports_renewal=True,
        supports_dead_letter=True,
        supports_fencing=True,
    )

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def descriptor(self) -> QueueBackendDescriptor:
        return QueueBackendDescriptor(
            version="1.0",
            backend_name="sqlite",
            backend_kind="sqlite",
            supports_priority=True,
            supports_leases=True,
            supports_renewal=True,
            supports_dead_letter=True,
            supports_fencing=True,
            durability_guarantee="durable single-file sqlite database",
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

    def enqueue(self, item: QueueItem) -> QueueOperationResult:
        if item.status == "queued" and item.available_at > item.updated_at:
            item.available_at = item.updated_at
        self.repository.save_queue_item(item)
        return QueueOperationResult(
            version="1.0",
            operation="enqueue",
            succeeded=True,
            status="queued",
            queue_item_id=item.queue_item_id,
        )

    def list_ready(self, *, queue_name: str, now: datetime | None = None) -> list[QueueItem]:
        now = utc_now() if now is None else now
        return [
            item
            for item in self.repository.list_queue_items(statuses=["queued", "deferred"])
            if item.queue_name == queue_name and item.available_at <= now
        ]

    def acquire_lease(
        self,
        *,
        queue_item_id: str,
        worker_id: str,
        lease_timeout_seconds: int,
        now: datetime | None = None,
    ) -> QueueLease:
        now = utc_now() if now is None else now
        item = self.repository.get_queue_item(queue_item_id)
        if item is None:
            raise KeyError(queue_item_id)
        lease = QueueLease(
            version="1.0",
            lease_id=f"queue-lease-{uuid4().hex[:10]}",
            queue_item_id=queue_item_id,
            task_id=item.task_id,
            worker_id=worker_id,
            status="active",
            acquired_at=now,
            expires_at=now.replace(microsecond=0) + timedelta(seconds=lease_timeout_seconds),
            fencing_token=f"fence-{uuid4().hex}",
            lease_epoch=1,
            renewed_at=now,
        )
        item.status = "leased"
        item.lease_id = lease.lease_id
        item.updated_at = now
        self.repository.save_queue_item(item)
        self.repository.save_queue_lease(lease)
        return lease

    def renew_lease(
        self,
        *,
        lease_id: str,
        worker_id: str,
        fencing_token: str,
        extend_seconds: int,
        now: datetime | None = None,
    ) -> QueueLease | None:
        now = utc_now() if now is None else now
        lease = self.repository.get_queue_lease(lease_id)
        if lease is None or not self._is_current_owner(lease_id, worker_id, fencing_token):
            return None
        lease.expires_at = now + timedelta(seconds=extend_seconds)
        lease.renewed_at = now
        self.repository.save_queue_lease(lease)
        return lease

    def acknowledge(
        self,
        *,
        lease_id: str,
        worker_id: str,
        fencing_token: str,
        now: datetime | None = None,
    ) -> QueueOperationResult:
        now = utc_now() if now is None else now
        if not self._is_current_owner(lease_id, worker_id, fencing_token):
            return QueueOperationResult(
                version="1.0",
                operation="acknowledge",
                succeeded=False,
                status="rejected",
                reason="fenced",
                lease_id=lease_id,
                fencing_token=fencing_token,
            )
        lease = self.repository.get_queue_lease(lease_id)
        if lease is None:
            raise KeyError(lease_id)
        lease.status = "released"
        lease.released_at = now
        lease.release_reason = "acknowledged"
        self.repository.save_queue_lease(lease)
        item = self.repository.get_queue_item(lease.queue_item_id)
        if item is not None:
            item.status = "completed"
            item.lease_id = ""
            item.updated_at = now
            self.repository.save_queue_item(item)
        return QueueOperationResult(
            version="1.0",
            operation="acknowledge",
            succeeded=True,
            status="completed",
            queue_item_id=lease.queue_item_id,
            lease_id=lease_id,
            fencing_token=fencing_token,
        )

    def release(
        self,
        *,
        lease_id: str,
        worker_id: str,
        fencing_token: str,
        reason: str,
        retryable: bool,
        now: datetime | None = None,
    ) -> QueueOperationResult:
        now = utc_now() if now is None else now
        if not self._is_current_owner(lease_id, worker_id, fencing_token):
            return QueueOperationResult(
                version="1.0",
                operation="release",
                succeeded=False,
                status="rejected",
                reason="fenced",
                lease_id=lease_id,
                fencing_token=fencing_token,
            )
        lease = self.repository.get_queue_lease(lease_id)
        if lease is None:
            raise KeyError(lease_id)
        lease.status = "released"
        lease.released_at = now
        lease.release_reason = reason
        self.repository.save_queue_lease(lease)
        item = self.repository.get_queue_item(lease.queue_item_id)
        if item is None:
            raise KeyError(lease.queue_item_id)
        item.attempt_count += 1
        item.updated_at = now
        item.lease_id = ""
        if retryable and item.attempt_count < item.max_attempts:
            item.status = "queued"
            item.available_at = now
        else:
            item.status = "dead_letter"
            item.dead_letter_reason = reason
        self.repository.save_queue_item(item)
        return QueueOperationResult(
            version="1.0",
            operation="release",
            succeeded=True,
            status=item.status,
            reason=reason,
            queue_item_id=item.queue_item_id,
            lease_id=lease_id,
            fencing_token=fencing_token,
        )

    def force_requeue(self, *, lease_id: str, reason: str, now: datetime | None = None) -> QueueOperationResult:
        now = utc_now() if now is None else now
        lease = self.repository.get_queue_lease(lease_id)
        if lease is None:
            raise KeyError(lease_id)
        item = self.repository.get_queue_item(lease.queue_item_id)
        if item is None:
            raise KeyError(lease.queue_item_id)
        lease.status = "released"
        lease.released_at = now
        lease.release_reason = reason
        self.repository.save_queue_lease(lease)
        item.status = "queued"
        item.available_at = now
        item.lease_id = ""
        item.updated_at = now
        self.repository.save_queue_item(item)
        return QueueOperationResult(
            version="1.0",
            operation="force_requeue",
            succeeded=True,
            status="queued",
            reason=reason,
            queue_item_id=item.queue_item_id,
            lease_id=lease_id,
        )

    def _is_current_owner(self, lease_id: str, worker_id: str, fencing_token: str) -> bool:
        ownership = self.repository.latest_lease_ownership(lease_id)
        if ownership is not None:
            return ownership.status == "active" and ownership.worker_id == worker_id and ownership.fencing_token == fencing_token
        lease = self.repository.get_queue_lease(lease_id)
        if lease is None:
            return False
        return lease.status == "active" and lease.worker_id == worker_id and lease.fencing_token == fencing_token
