from datetime import UTC, datetime, timedelta
from pathlib import Path

from contract_evidence_os.runtime.backends import SQLiteQueueBackend
from contract_evidence_os.runtime.coordination import SQLiteCoordinationBackend, WorkerCapabilityRecord
from contract_evidence_os.runtime.queueing import QueueItem
from contract_evidence_os.storage.repository import SQLiteRepository


def _now() -> datetime:
    return datetime(2026, 4, 17, 0, 0, tzinfo=UTC)


def test_sqlite_queue_backend_contract_supports_enqueue_lease_release_and_ack(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    backend = SQLiteQueueBackend(repository)

    item = QueueItem(
        version="1.0",
        queue_item_id="queue-item-001",
        task_id="task-001",
        contract_id="contract-001",
        queue_name="default",
        priority_class="standard",
        risk_level="low",
        status="queued",
        attempt_count=0,
        max_attempts=3,
        created_at=_now(),
        updated_at=_now(),
    )
    enqueue = backend.enqueue(item)
    assert enqueue.succeeded is True

    ready = backend.list_ready(queue_name="default", now=_now())
    assert [candidate.queue_item_id for candidate in ready] == ["queue-item-001"]

    lease = backend.acquire_lease(queue_item_id=item.queue_item_id, worker_id="worker-1", lease_timeout_seconds=30, now=_now())
    assert lease.worker_id == "worker-1"

    released = backend.release(
        lease_id=lease.lease_id,
        worker_id="worker-1",
        fencing_token=lease.fencing_token,
        reason="retry",
        retryable=True,
        now=_now() + timedelta(seconds=5),
    )
    assert released.succeeded is True

    leased_again = backend.acquire_lease(queue_item_id=item.queue_item_id, worker_id="worker-1", lease_timeout_seconds=30, now=_now() + timedelta(seconds=6))
    acknowledged = backend.acknowledge(
        lease_id=leased_again.lease_id,
        worker_id="worker-1",
        fencing_token=leased_again.fencing_token,
        now=_now() + timedelta(seconds=7),
    )
    assert acknowledged.succeeded is True


def test_coordination_backend_reclaims_stale_worker_leases_and_fences_old_owner(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    queue_backend = SQLiteQueueBackend(repository)
    coordination = SQLiteCoordinationBackend(repository)

    coordination.register_worker(
        worker_id="worker-1",
        worker_role="worker",
        process_identity="pid-100",
        capabilities=WorkerCapabilityRecord(
            version="1.0",
            worker_id="worker-1",
            provider_access=["openai_live", "anthropic_live"],
            tool_access=["file_retrieval"],
            role_specialization=["Researcher", "Verifier"],
            supports_degraded_mode=True,
            supports_high_risk=False,
            max_parallel_tasks=1,
            created_at=_now(),
        ),
        claimed_capacity=1,
        started_at=_now(),
    )
    coordination.register_worker(
        worker_id="worker-2",
        worker_role="worker",
        process_identity="pid-200",
        capabilities=WorkerCapabilityRecord(
            version="1.0",
            worker_id="worker-2",
            provider_access=["openai_live", "anthropic_live"],
            tool_access=["file_retrieval"],
            role_specialization=["Researcher", "Verifier"],
            supports_degraded_mode=True,
            supports_high_risk=True,
            max_parallel_tasks=1,
            created_at=_now(),
        ),
        claimed_capacity=1,
        started_at=_now(),
    )
    queue_backend.enqueue(
        QueueItem(
            version="1.0",
            queue_item_id="queue-item-001",
            task_id="task-001",
            contract_id="contract-001",
            queue_name="default",
            priority_class="standard",
            risk_level="low",
            status="queued",
            attempt_count=0,
            max_attempts=3,
            created_at=_now(),
            updated_at=_now(),
        )
    )

    lease = queue_backend.acquire_lease(queue_item_id="queue-item-001", worker_id="worker-1", lease_timeout_seconds=10, now=_now())
    ownership = coordination.claim_lease(
        lease_id=lease.lease_id,
        queue_item_id="queue-item-001",
        task_id="task-001",
        worker_id="worker-1",
        expires_at=_now() + timedelta(seconds=10),
        now=_now(),
    )
    coordination.heartbeat("worker-1", active_leases=[lease.lease_id], capacity_in_use=1, now=_now())

    reclaimed = coordination.reclaim_stale_workers(
        now=_now() + timedelta(seconds=90),
        heartbeat_expiry_seconds=30,
    )
    assert reclaimed

    replacement = coordination.claim_lease(
        lease_id=lease.lease_id,
        queue_item_id="queue-item-001",
        task_id="task-001",
        worker_id="worker-2",
        expires_at=_now() + timedelta(seconds=120),
        now=_now() + timedelta(seconds=91),
    )
    assert replacement.lease_epoch > ownership.lease_epoch

    stale_ack = queue_backend.acknowledge(
        lease_id=lease.lease_id,
        worker_id="worker-1",
        fencing_token=ownership.fencing_token,
        now=_now() + timedelta(seconds=92),
    )
    assert stale_ack.succeeded is False
    assert stale_ack.reason == "fenced"
