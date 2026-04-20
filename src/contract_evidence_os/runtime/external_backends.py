"""External backend implementations for shared runtime coordination."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.runtime.backends import (
    BackendHealthRecord,
    QueueBackendDescriptor,
    QueueCapabilityDescriptor,
    QueueOperationResult,
)
from contract_evidence_os.runtime.queueing import QueueItem, QueueLease

try:  # pragma: no cover - exercised indirectly in tests
    import redis
except Exception:  # pragma: no cover - optional dependency path
    redis = None  # type: ignore[assignment]


def _require_redis() -> Any:
    if redis is None:
        raise RuntimeError("redis package is required for the redis backend")
    return redis


def build_redis_client(*, url: str | None = None, client: Any | None = None) -> Any:
    """Build or reuse a redis client."""

    if client is not None:
        return client
    module = _require_redis()
    return module.Redis.from_url(url or "redis://127.0.0.1:6379/0", decode_responses=True)


class RedisQueueBackend:
    """Redis-backed queue backend with repository mirroring for audit and replay."""

    capability = QueueCapabilityDescriptor(
        version="1.0",
        backend_name="redis",
        supports_priority=True,
        supports_leases=True,
        supports_renewal=True,
        supports_dead_letter=True,
        supports_fencing=True,
    )

    def __init__(
        self,
        repository: Any,
        *,
        client: Any | None = None,
        url: str | None = None,
        namespace: str = "ceos",
    ) -> None:
        self.repository = repository
        self.client = build_redis_client(url=url, client=client)
        self.namespace = namespace

    def descriptor(self) -> QueueBackendDescriptor:
        return QueueBackendDescriptor(
            version="1.0",
            backend_name="redis",
            backend_kind="redis",
            supports_priority=True,
            supports_leases=True,
            supports_renewal=True,
            supports_dead_letter=True,
            supports_fencing=True,
            durability_guarantee="in-memory with backend-dependent persistence and append-only durability",
        )

    def health(self) -> BackendHealthRecord:
        started = time.perf_counter()
        try:
            self.client.ping()
            latency_ms = (time.perf_counter() - started) * 1000.0
            return BackendHealthRecord(
                version="1.0",
                backend_name="redis",
                backend_kind="redis",
                status="available",
                latency_ms=latency_ms,
                connected=True,
            )
        except Exception as exc:  # pragma: no cover - exercised in outage tests later
            return BackendHealthRecord(
                version="1.0",
                backend_name="redis",
                backend_kind="redis",
                status="degraded",
                latency_ms=0.0,
                connected=False,
                last_error=str(exc),
            )

    def enqueue(self, item: QueueItem) -> QueueOperationResult:
        if item.status == "queued" and item.available_at > item.updated_at:
            item.available_at = item.updated_at
        self.repository.save_queue_item(item)
        self.client.set(self._item_key(item.queue_item_id), self._dumps(item))
        self.client.zadd(self._ready_key(item.queue_name), {item.queue_item_id: item.available_at.timestamp()})
        return QueueOperationResult(
            version="1.0",
            operation="enqueue",
            succeeded=True,
            status="queued",
            queue_item_id=item.queue_item_id,
        )

    def list_ready(self, *, queue_name: str, now: datetime | None = None) -> list[QueueItem]:
        now = utc_now() if now is None else now
        item_ids = list(self.client.zrangebyscore(self._ready_key(queue_name), min="-inf", max=now.timestamp()))
        items = [item for item_id in item_ids if (item := self._load_item(item_id)) is not None]
        priority = {"recovery": 0, "high": 1, "standard": 2, "background": 3}
        return sorted(items, key=lambda item: (priority.get(item.priority_class, 9), item.available_at))

    def acquire_lease(
        self,
        *,
        queue_item_id: str,
        worker_id: str,
        lease_timeout_seconds: int,
        now: datetime | None = None,
    ) -> QueueLease:
        now = utc_now() if now is None else now
        item = self._lock_and_load_item(queue_item_id)
        try:
            if item is None:
                raise KeyError(queue_item_id)
            if item.status not in {"queued", "deferred"}:
                raise RuntimeError(f"queue item {queue_item_id} is not leasable")
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
            self.client.set(self._item_key(queue_item_id), self._dumps(item))
            self.client.set(self._lease_key(lease.lease_id), self._dumps(lease))
            self.client.zrem(self._ready_key(item.queue_name), queue_item_id)
            return lease
        finally:
            self._unlock_item(queue_item_id)

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
        lease = self._load_lease(lease_id)
        if lease is None or lease.worker_id != worker_id or lease.fencing_token != fencing_token or lease.status != "active":
            return None
        lease.expires_at = now + timedelta(seconds=extend_seconds)
        lease.renewed_at = now
        self.repository.save_queue_lease(lease)
        self.client.set(self._lease_key(lease_id), self._dumps(lease))
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
        lease = self._load_lease(lease_id)
        if lease is None:
            raise KeyError(lease_id)
        if lease.worker_id != worker_id or lease.fencing_token != fencing_token or lease.status != "active":
            return QueueOperationResult(
                version="1.0",
                operation="acknowledge",
                succeeded=False,
                status="rejected",
                reason="fenced",
                lease_id=lease_id,
                fencing_token=fencing_token,
            )
        item = self._lock_and_load_item(lease.queue_item_id)
        try:
            if item is None:
                raise KeyError(lease.queue_item_id)
            lease.status = "released"
            lease.released_at = now
            lease.release_reason = "acknowledged"
            item.status = "completed"
            item.updated_at = now
            item.lease_id = ""
            self.repository.save_queue_lease(lease)
            self.repository.save_queue_item(item)
            self.client.set(self._lease_key(lease_id), self._dumps(lease))
            self.client.set(self._item_key(item.queue_item_id), self._dumps(item))
            self.client.zrem(self._ready_key(item.queue_name), item.queue_item_id)
            return QueueOperationResult(
                version="1.0",
                operation="acknowledge",
                succeeded=True,
                status="completed",
                queue_item_id=item.queue_item_id,
                lease_id=lease_id,
                fencing_token=fencing_token,
            )
        finally:
            self._unlock_item(lease.queue_item_id)

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
        lease = self._load_lease(lease_id)
        if lease is None:
            raise KeyError(lease_id)
        if lease.worker_id != worker_id or lease.fencing_token != fencing_token or lease.status != "active":
            return QueueOperationResult(
                version="1.0",
                operation="release",
                succeeded=False,
                status="rejected",
                reason="fenced",
                lease_id=lease_id,
                fencing_token=fencing_token,
            )
        item = self._lock_and_load_item(lease.queue_item_id)
        try:
            if item is None:
                raise KeyError(lease.queue_item_id)
            lease.status = "released"
            lease.released_at = now
            lease.release_reason = reason
            item.attempt_count += 1
            item.updated_at = now
            item.lease_id = ""
            if retryable and item.attempt_count < item.max_attempts:
                item.status = "queued"
                item.available_at = now
                self.client.zadd(self._ready_key(item.queue_name), {item.queue_item_id: item.available_at.timestamp()})
            else:
                item.status = "dead_letter"
                item.dead_letter_reason = reason
                self.client.zrem(self._ready_key(item.queue_name), item.queue_item_id)
            self.repository.save_queue_lease(lease)
            self.repository.save_queue_item(item)
            self.client.set(self._lease_key(lease_id), self._dumps(lease))
            self.client.set(self._item_key(item.queue_item_id), self._dumps(item))
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
        finally:
            self._unlock_item(lease.queue_item_id)

    def force_requeue(self, *, lease_id: str, reason: str, now: datetime | None = None) -> QueueOperationResult:
        now = utc_now() if now is None else now
        lease = self._load_lease(lease_id)
        if lease is None:
            raise KeyError(lease_id)
        item = self._lock_and_load_item(lease.queue_item_id)
        try:
            if item is None:
                raise KeyError(lease.queue_item_id)
            lease.status = "released"
            lease.released_at = now
            lease.release_reason = reason
            item.status = "queued"
            item.available_at = now
            item.lease_id = ""
            item.updated_at = now
            self.repository.save_queue_lease(lease)
            self.repository.save_queue_item(item)
            self.client.set(self._lease_key(lease_id), self._dumps(lease))
            self.client.set(self._item_key(item.queue_item_id), self._dumps(item))
            self.client.zadd(self._ready_key(item.queue_name), {item.queue_item_id: item.available_at.timestamp()})
            return QueueOperationResult(
                version="1.0",
                operation="force_requeue",
                succeeded=True,
                status="queued",
                reason=reason,
                queue_item_id=item.queue_item_id,
                lease_id=lease_id,
            )
        finally:
            self._unlock_item(lease.queue_item_id)

    def _dumps(self, value: Any) -> str:
        return json.dumps(value.to_dict(), ensure_ascii=True)

    def _load_item(self, queue_item_id: str) -> QueueItem | None:
        raw = self.client.get(self._item_key(queue_item_id))
        if raw is None:
            item = self.repository.get_queue_item(queue_item_id)
            if item is not None:
                self.client.set(self._item_key(queue_item_id), self._dumps(item))
            return item
        return QueueItem.from_dict(json.loads(raw))

    def _load_lease(self, lease_id: str) -> QueueLease | None:
        raw = self.client.get(self._lease_key(lease_id))
        if raw is None:
            lease = self.repository.get_queue_lease(lease_id)
            if lease is not None:
                self.client.set(self._lease_key(lease_id), self._dumps(lease))
            return lease
        return QueueLease.from_dict(json.loads(raw))

    def _lock_and_load_item(self, queue_item_id: str) -> QueueItem | None:
        lock_key = self._lock_key(queue_item_id)
        if not self.client.set(lock_key, "1", nx=True, ex=5):
            raise RuntimeError(f"queue item {queue_item_id} is locked by another owner")
        return self._load_item(queue_item_id)

    def _unlock_item(self, queue_item_id: str) -> None:
        self.client.delete(self._lock_key(queue_item_id))

    def _item_key(self, queue_item_id: str) -> str:
        return f"{self.namespace}:queue:item:{queue_item_id}"

    def _lease_key(self, lease_id: str) -> str:
        return f"{self.namespace}:queue:lease:{lease_id}"

    def _ready_key(self, queue_name: str) -> str:
        return f"{self.namespace}:queue:ready:{queue_name}"

    def _lock_key(self, queue_item_id: str) -> str:
        return f"{self.namespace}:queue:lock:{queue_item_id}"
