from pathlib import Path

import fakeredis

from contract_evidence_os.runtime.coordination import WorkerCapabilityRecord
from contract_evidence_os.runtime.service import RuntimeService


def test_cross_host_runtime_recovers_via_external_backend_and_host_turnover(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text("Audit history must never be deleted.\n", encoding="utf-8")

    redis_client = fakeredis.FakeRedis(decode_responses=True)
    runtime_a = RuntimeService(
        storage_root=tmp_path / "runtime",
        routing_strategy="quality",
        coordination_backend_kind="redis",
        queue_backend_kind="redis",
        external_backend_client=redis_client,
    )
    runtime_b = RuntimeService(
        storage_root=tmp_path / "runtime",
        routing_strategy="quality",
        coordination_backend_kind="redis",
        queue_backend_kind="redis",
        external_backend_client=redis_client,
    )

    queued = runtime_a.submit_task(
        goal="Read the attachment, build a structured delivery, and verify it.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
        priority_class="standard",
    )

    runtime_a.register_worker(
        worker_id="worker-a",
        worker_role="worker",
        process_identity="pid-a",
        capabilities=WorkerCapabilityRecord(
            version="1.0",
            worker_id="worker-a",
            provider_access=["openai_live", "anthropic_live"],
            tool_access=["file_retrieval"],
            role_specialization=["Researcher", "Verifier"],
            supports_degraded_mode=True,
            supports_high_risk=False,
            max_parallel_tasks=1,
        ),
        host_id="host-a",
        service_identity="worker-service",
        endpoint_address="tcp://host-a:9101",
    )
    runtime_b.register_worker(
        worker_id="worker-b",
        worker_role="worker",
        process_identity="pid-b",
        capabilities=WorkerCapabilityRecord(
            version="1.0",
            worker_id="worker-b",
            provider_access=["openai_live", "anthropic_live"],
            tool_access=["file_retrieval"],
            role_specialization=["Researcher", "Verifier"],
            supports_degraded_mode=True,
            supports_high_risk=True,
            max_parallel_tasks=1,
        ),
        host_id="host-b",
        service_identity="worker-service",
        endpoint_address="tcp://host-b:9102",
    )

    first = runtime_a.dispatch_next_queued_task(worker_id="worker-a", interrupt_after="planned")
    assert first["status"] == "interrupted"

    reclaimed = runtime_b.reclaim_stale_workers(force_expire=True)
    assert reclaimed["reclaimed_leases"] >= 1

    resumed = runtime_b.dispatch_next_queued_task(worker_id="worker-b")
    assert resumed["status"] in {"completed", "blocked", "awaiting_approval"}

    replay = runtime_b.replay_task(queued.task_id)
    assert replay["lease_ownerships"]
    assert replay["worker_registry"]
    assert replay["host_records"]

    report = runtime_b.system_governance_state()
    assert report["backend_state"]["coordination_backend"]["backend_name"] == "redis"
    assert report["backend_state"]["queue_backend"]["backend_name"] == "redis"
