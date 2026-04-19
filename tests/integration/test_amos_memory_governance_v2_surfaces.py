import json
import threading
import urllib.request
from pathlib import Path

from contract_evidence_os.api.operator import OperatorAPI
from contract_evidence_os.api.server import RemoteOperatorService
from contract_evidence_os.evals.models import StrategyEvaluationReport
from contract_evidence_os.runtime.service import RuntimeService


def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, method=method, data=data)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Request-Id", f"req-{method.lower()}-{abs(hash(url)) % 100000}")
    request.add_header("X-Request-Nonce", f"nonce-{abs(hash(url)) % 100000}")
    request.add_header("X-Idempotency-Key", f"idem-{abs(hash(url)) % 100000}")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_operator_and_remote_service_expose_project_state_purge_manifests_and_policy_analytics(tmp_path: Path) -> None:
    attachment = tmp_path / "notes.txt"
    attachment.write_text("AMOS should stay auditable, recoverable, and contradiction-aware.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    result = service.run_task(
        goal="Read the attachment and summarize the memory governance requirements.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not erase audit lineage."],
    )

    api = OperatorAPI(storage_root=root)
    for when, state_object in (
        ("2026-04-10T12:00:00+00:00", "AMOS design"),
        ("2026-04-12T12:00:00+00:00", "policy tuning"),
        ("2026-04-15T12:00:00+00:00", "AMOS design"),
    ):
        candidate = api.memory.create_candidate(
            task_id=result.task_id,
            scope_key=result.task_id,
            lane="semantic",
            summary=f"user working on {state_object}",
            content={
                "subject": "user",
                "predicate": "working_on",
                "object": state_object,
                "valid_from": when,
                "head": "goal",
            },
            sources=["episode-project-state"],
        )
        api.memory.govern_candidate(candidate.candidate_id)
        api.memory.consolidate_candidate(candidate.candidate_id)

    trace = api.evolution.record_memory_lifecycle_trace(
        scope_key=result.task_id,
        events=["candidate_quarantined", "selective_purge_completed", "cross_scope_timeline_rebuilt"],
        metrics={
            "quarantine_precision_rate": 1.0,
            "selective_purge_precision_rate": 1.0,
            "cross_scope_timeline_reconstruction_rate": 1.0,
        },
    )
    candidate = api.evolution.propose_memory_policy_candidate(
        lifecycle_trace=trace,
        target_component="memory.policy.admission",
        hypothesis="Tighten feature-scored memory admission.",
    )
    api.evolution.evaluate_candidate(
        candidate.candidate_id,
        report=StrategyEvaluationReport(
            strategy_name="memory-governance-v2",
            metrics={
                "quarantine_precision_rate": 1.0,
                "hard_purge_compliance_rate": 1.0,
                "timeline_reconstruction_rate": 1.0,
                "selective_purge_precision_rate": 1.0,
                "learned_admission_gain_rate": 1.0,
                "cross_scope_timeline_reconstruction_rate": 1.0,
                "policy_violation_rate": 0.0,
            },
        ),
    )
    api.evolution.run_canary(candidate.candidate_id, success_rate=0.5, anomaly_count=2)
    api.evolution.promote_candidate(candidate.candidate_id)

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        project_state = _request(
            "GET",
            f"{remote.base_url}/tasks/{result.task_id}/memory/project-state?subject=user",
            "secret-token",
        )
        assert project_state["snapshot"]["contradiction_count"] >= 1

        hard_purge = _request(
            "POST",
            f"{remote.base_url}/tasks/{result.task_id}/memory/hard-purge",
            "secret-token",
            {
                "actor": "runtime-admin",
                "reason": "remove AMOS memory artifacts and indexes",
            },
        )
        assert hard_purge["purged_record_count"] >= 1
        assert hard_purge["manifest"]["purged_record_ids"]

        policy = _request(
            "GET",
            f"{remote.base_url}/tasks/{result.task_id}/memory/policy",
            "secret-token",
        )
        assert policy["analytics"]
        assert policy["analytics"][0]["recommendation"] == "rollback"
    finally:
        remote.shutdown()

