from datetime import UTC, datetime, timedelta
from pathlib import Path

import fakeredis

from contract_evidence_os.runtime.coordination import (
    LeaseRenewalPolicy,
    RedisCoordinationBackend,
    WorkStealPolicy,
    WorkerCapabilityRecord,
)
from contract_evidence_os.runtime.external_backends import RedisQueueBackend
from contract_evidence_os.runtime.queueing import QueueItem
from contract_evidence_os.storage.repository import SQLiteRepository


def _now() -> datetime:
    return datetime(2026, 4, 17, 0, 0, tzinfo=UTC)


def test_redis_queue_backend_contract_supports_enqueue_lease_renew_release_and_ack(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    backend = RedisQueueBackend(repository=repository, client=redis_client, namespace="test-ceos")

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
    assert backend.capability.backend_name == "redis"

    ready = backend.list_ready(queue_name="default", now=_now())
    assert [candidate.queue_item_id for candidate in ready] == ["queue-item-001"]

    lease = backend.acquire_lease(queue_item_id=item.queue_item_id, worker_id="worker-1", lease_timeout_seconds=30, now=_now())
    renewed = backend.renew_lease(
        lease_id=lease.lease_id,
        worker_id="worker-1",
        fencing_token=lease.fencing_token,
        extend_seconds=30,
        now=_now() + timedelta(seconds=5),
    )
    assert renewed is not None
    assert renewed.expires_at > lease.expires_at

    released = backend.release(
        lease_id=lease.lease_id,
        worker_id="worker-1",
        fencing_token=lease.fencing_token,
        reason="retry",
        retryable=True,
        now=_now() + timedelta(seconds=10),
    )
    assert released.succeeded is True

    leased_again = backend.acquire_lease(queue_item_id=item.queue_item_id, worker_id="worker-1", lease_timeout_seconds=30, now=_now() + timedelta(seconds=11))
    acknowledged = backend.acknowledge(
        lease_id=leased_again.lease_id,
        worker_id="worker-1",
        fencing_token=leased_again.fencing_token,
        now=_now() + timedelta(seconds=12),
    )
    assert acknowledged.succeeded is True


def test_redis_coordination_backend_supports_cross_host_renewal_and_safe_work_steal(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    coordination = RedisCoordinationBackend(repository=repository, client=redis_client, namespace="test-ceos")

    capability_a = WorkerCapabilityRecord(
        version="1.0",
        worker_id="worker-a",
        provider_access=["openai_live", "anthropic_live"],
        tool_access=["file_retrieval"],
        role_specialization=["Researcher", "Verifier"],
        supports_degraded_mode=True,
        supports_high_risk=False,
        max_parallel_tasks=1,
        created_at=_now(),
    )
    capability_b = WorkerCapabilityRecord(
        version="1.0",
        worker_id="worker-b",
        provider_access=["openai_live", "anthropic_live"],
        tool_access=["file_retrieval"],
        role_specialization=["Researcher", "Verifier"],
        supports_degraded_mode=True,
        supports_high_risk=True,
        max_parallel_tasks=1,
        created_at=_now(),
    )

    coordination.register_worker(
        worker_id="worker-a",
        worker_role="worker",
        process_identity="pid-a",
        capabilities=capability_a,
        claimed_capacity=1,
        started_at=_now(),
        host_id="host-a",
        service_identity="worker-service",
        endpoint_address="tcp://host-a:9101",
    )
    coordination.register_worker(
        worker_id="worker-b",
        worker_role="worker",
        process_identity="pid-b",
        capabilities=capability_b,
        claimed_capacity=1,
        started_at=_now(),
        host_id="host-b",
        service_identity="worker-service",
        endpoint_address="tcp://host-b:9102",
    )

    ownership = coordination.claim_lease(
        lease_id="lease-001",
        queue_item_id="queue-item-001",
        task_id="task-001",
        worker_id="worker-a",
        expires_at=_now() + timedelta(seconds=30),
        now=_now(),
    )
    renewed = coordination.renew_lease(
        lease_id="lease-001",
        worker_id="worker-a",
        fencing_token=ownership.fencing_token,
        expires_at=_now() + timedelta(seconds=45),
        now=_now() + timedelta(seconds=10),
        policy=LeaseRenewalPolicy(
            version="1.0",
            policy_id="renewal-default",
            renew_before_seconds=10,
            max_jitter_seconds=2,
            slow_worker_grace_seconds=5,
            contention_backoff_seconds=3,
            steal_min_age_seconds=20,
            created_at=_now(),
        ),
        host_id="host-a",
    )
    assert renewed is not None

    coordination.set_worker_mode("worker-a", mode_name="drain", shutdown_state="draining")
    stolen = coordination.steal_lease(
        lease_id="lease-001",
        queue_item_id="queue-item-001",
        task_id="task-001",
        new_worker_id="worker-b",
        now=_now() + timedelta(seconds=25),
        policy=WorkStealPolicy(
            version="1.0",
            policy_id="work-steal-default",
            allow_steal_from_draining=True,
            allow_steal_from_stale=True,
            min_lease_age_seconds=20,
            max_pressure_to_keep_owner=0.8,
            protect_verification_capacity=True,
            protect_recovery_capacity=True,
            created_at=_now(),
        ),
    )
    assert stolen is not None
    assert stolen.to_worker_id == "worker-b"
    assert coordination.validate_fencing(lease_id="lease-001", worker_id="worker-a", fencing_token=ownership.fencing_token) is False

    latest = repository.latest_lease_ownership("lease-001")
    assert latest is not None
    assert coordination.validate_fencing(lease_id="lease-001", worker_id="worker-b", fencing_token=latest.fencing_token) is True
    assert repository.list_work_steal_decisions()
    assert repository.list_lease_transfer_records()
