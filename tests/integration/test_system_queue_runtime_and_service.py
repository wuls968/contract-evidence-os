import json
import threading
import urllib.request
from pathlib import Path

from contract_evidence_os.api.server import RemoteOperatorService
from contract_evidence_os.runtime.service import RuntimeInterrupted, RuntimeService


def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, method=method, data=data)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_runtime_can_queue_interrupt_recover_and_resume_tasks(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text(
        "Audit history must never be deleted.\nEvery important summary must cite evidence.\n",
        encoding="utf-8",
    )
    service = RuntimeService(storage_root=tmp_path / "runtime", routing_strategy="quality")
    queued = service.submit_task(
        goal="Read the attachment, build a structured delivery, and verify it.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
        priority_class="standard",
    )

    first = service.dispatch_next_queued_task(worker_id="worker-1", interrupt_after="planned")
    assert first["status"] == "interrupted"
    queue_item = service.repository.get_queue_item(queued.queue_item_id)
    assert queue_item is not None
    assert queue_item.status == "queued"

    service.recover_stale_queue_leases(force_expire=True)
    second = service.dispatch_next_queued_task(worker_id="worker-1")
    assert second["status"] in {"completed", "awaiting_approval", "blocked"}
    replay = service.replay_task(queued.task_id)
    assert replay["handoff"] is not None


def test_remote_operator_service_exposes_queue_provider_and_policy_surfaces(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text("Audit history must never be deleted.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    queued = service.submit_task(
        goal="Read the attachment and verify it.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
        priority_class="standard",
    )

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = remote.base_url
        queue_status = _request("GET", f"{base_url}/queue/status", "secret-token")
        assert queue_status["queued_tasks"] >= 1

        provider_health = _request("GET", f"{base_url}/providers/health", "secret-token")
        assert "records" in provider_health
        assert "rate_limit_states" in provider_health

        policies = _request("GET", f"{base_url}/policies", "secret-token")
        assert "active_versions" in policies

        report = _request("GET", f"{base_url}/reports/system", "secret-token")
        assert "bottlenecks" in report

        startup = _request("GET", f"{base_url}/service/startup-validation", "secret-token")
        assert startup["ok"] is True

        override = _request(
            "POST",
            f"{base_url}/system/governance",
            "secret-token",
            {
                "action": "set_drain_mode",
                "operator": "remote-operator",
                "reason": "draining for restart",
                "payload": {"idempotency_key": "drain-001"},
            },
        )
        assert override["status"] == "accepted"
        repeated_override = _request(
            "POST",
            f"{base_url}/system/governance",
            "secret-token",
            {
                "action": "set_drain_mode",
                "operator": "remote-operator",
                "reason": "draining for restart",
                "payload": {"idempotency_key": "drain-001"},
            },
        )
        assert repeated_override["override_id"] == override["override_id"]

        candidate = _request(
            "POST",
            f"{base_url}/policies/candidates",
            "secret-token",
            {
                "name": "routing-pressure-candidate",
                "hypothesis": "Prefer the more stable provider under pressure.",
                "policy_payload": {"prefer_reliability": True},
            },
        )
        evaluated = _request(
            "POST",
            f"{base_url}/policies/evaluate",
            "secret-token",
            {
                "candidate_id": candidate["candidate_id"],
                "metrics": {
                    "provider_pressure_survival_rate": 1.0,
                    "verified_completion_rate_under_load": 1.0,
                    "policy_violation_rate": 0.0,
                },
            },
        )
        assert evaluated["status"] == "passed"

        promoted = _request(
            "POST",
            f"{base_url}/policies/promote",
            "secret-token",
            {"candidate_id": candidate["candidate_id"]},
        )
        assert promoted["status"] == "promoted"

        drained = _request(
            "POST",
            f"{base_url}/service/shutdown",
            "secret-token",
            {"reason": "prepare for restart"},
        )
        assert drained["status"] == "draining"

        restarted = _request("POST", f"{base_url}/service/restart-recovery", "secret-token", {})
        assert restarted["status"] == "ready"

        replay = _request("POST", f"{base_url}/queue/dispatch", "secret-token", {"worker_id": "worker-1"})
        assert replay["status"] in {"completed", "interrupted", "awaiting_approval", "blocked", "deferred", "idle"}
    finally:
        remote.shutdown()
