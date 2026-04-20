import json
import threading
import urllib.request
from pathlib import Path

from contract_evidence_os.api.server import RemoteOperatorService
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


def test_remote_operator_service_exposes_collaboration_memory_scopes_and_strategy_state(tmp_path: Path) -> None:
    attachment = tmp_path / "notes.txt"
    attachment.write_text("Collaboration and strategy state should be visible over the versioned operator API.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    runtime = RuntimeService(storage_root=root, routing_strategy="quality")
    result = runtime.run_task(
        goal="Read the note and prepare collaboration-ready state.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not publish unreviewed summaries as trusted."],
    )
    runtime.configure_task_collaboration(
        task_id=result.task_id,
        owner="owner@example.com",
        reviewer="reviewer@example.com",
        operators=["owner@example.com"],
        watchers=["watcher@example.com"],
        approval_assignee="reviewer@example.com",
    )
    runtime.acquire_task_lease(
        task_id=result.task_id,
        actor="owner@example.com",
        lease_kind="owner",
        phase="verification",
    )
    runtime.record_scoped_memory(
        task_id=result.task_id,
        actor="owner@example.com",
        owner_user_id="owner@example.com",
        audience_scope="task_shared",
        memory_kind="decision",
        summary="Share the review-gated conclusion with the team.",
        content={"decision": "share_with_team"},
        evidence_refs=["evidence-1"],
        privacy_level="low",
        contradiction_risk=0.0,
    )
    signal = runtime.record_strategy_feedback(
        scope_key=result.task_id,
        actor="reviewer@example.com",
        strategy_kind="summarization_policy",
        signal_kind="review_accept",
        metrics={"quality": 1.0},
        evidence_refs=[],
    )
    runtime.propose_strategy_candidate(
        scope_key=result.task_id,
        actor="reviewer@example.com",
        strategy_kind="summarization_policy",
        target_component="summary.handoff",
        hypothesis="Promote trusted handoff summaries after reviewer approval.",
        supporting_signal_ids=[signal.signal_id],
    )

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        collaboration = _request("GET", f"{remote.base_url}/v1/tasks/{result.task_id}/collaboration", "secret-token")
        memory_scopes = _request("GET", f"{remote.base_url}/v1/tasks/{result.task_id}/memory/scopes", "secret-token")
        strategy = _request("GET", f"{remote.base_url}/v1/strategy/overview?scope_key={result.task_id}", "secret-token")

        assert collaboration["binding"]["owner"] == "owner@example.com"
        assert collaboration["active_leases"][0]["phase"] == "verification"
        assert memory_scopes["records"][0]["audience_scope"] == "task_shared"
        assert strategy["scope_key"] == result.task_id
        assert strategy["candidates"][0]["target_component"] == "summary.handoff"
    finally:
        remote.shutdown()


def test_remote_operator_service_executes_collaboration_memory_scope_and_strategy_actions(tmp_path: Path) -> None:
    attachment = tmp_path / "collab.txt"
    attachment.write_text("Operators should be able to coordinate, hand off, and tune strategy over the remote API.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    runtime = RuntimeService(storage_root=root, routing_strategy="quality")
    result = runtime.run_task(
        goal="Prepare a task that will be coordinated by multiple operators.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not bypass review for shared strategy changes."],
    )

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        collaboration = _request(
            "POST",
            f"{remote.base_url}/v1/tasks/{result.task_id}/collaboration",
            "secret-token",
            {
                "owner": "owner@example.com",
                "reviewer": "reviewer@example.com",
                "operators": ["owner@example.com", "operator@example.com"],
                "watchers": ["watcher@example.com"],
                "approval_assignee": "reviewer@example.com",
            },
        )
        lease = _request(
            "POST",
            f"{remote.base_url}/v1/tasks/{result.task_id}/leases",
            "secret-token",
            {"actor": "owner@example.com", "lease_kind": "owner", "phase": "delivery", "ttl_seconds": 300},
        )
        branch = _request(
            "POST",
            f"{remote.base_url}/v1/tasks/{result.task_id}/branches",
            "secret-token",
            {"actor": "operator@example.com", "branch_kind": "evidence", "title": "Collect final evidence"},
        )
        handoff = _request(
            "POST",
            f"{remote.base_url}/v1/tasks/{result.task_id}/handoff",
            "secret-token",
            {
                "from_actor": "owner@example.com",
                "to_actor": "operator@example.com",
                "summary": "Take over evidence collection and prep the delivery branch.",
                "branch_id": branch["branch_id"],
            },
        )
        scope_record = _request(
            "POST",
            f"{remote.base_url}/v1/tasks/{result.task_id}/memory/scopes",
            "secret-token",
            {
                "actor": "owner@example.com",
                "owner_user_id": "owner@example.com",
                "audience_scope": "task_shared",
                "memory_kind": "decision",
                "summary": "Delivery should stay reviewer-gated.",
                "content": {"decision": "review_before_delivery"},
                "evidence_refs": ["evidence-1"],
                "privacy_level": "low",
                "contradiction_risk": 0.0,
            },
        )
        summary = _request(
            "POST",
            f"{remote.base_url}/v1/tasks/{result.task_id}/memory/scopes/summary",
            "secret-token",
            {"actor": "owner@example.com", "summary_kind": "handoff_summary"},
        )
        signal = _request(
            "POST",
            f"{remote.base_url}/v1/strategy/feedback",
            "secret-token",
            {
                "scope_key": result.task_id,
                "actor": "reviewer@example.com",
                "strategy_kind": "summarization_policy",
                "signal_kind": "handoff_quality",
                "metrics": {"quality": 0.95},
                "evidence_refs": [],
            },
        )
        candidate = _request(
            "POST",
            f"{remote.base_url}/v1/strategy/candidates",
            "secret-token",
            {
                "scope_key": result.task_id,
                "actor": "reviewer@example.com",
                "strategy_kind": "summarization_policy",
                "target_component": "summary.handoff",
                "hypothesis": "Use reviewer-approved handoff summaries by default.",
                "supporting_signal_ids": [signal["signal_id"]],
            },
        )
        evaluated = _request(
            "POST",
            f"{remote.base_url}/v1/strategy/candidates/{candidate['candidate_id']}/evaluate",
            "secret-token",
            {"regression_failures": 0, "gain": 0.2},
        )
        canary = _request(
            "POST",
            f"{remote.base_url}/v1/strategy/candidates/{candidate['candidate_id']}/canary",
            "secret-token",
            {"actor": "reviewer@example.com", "scope": result.task_id, "success_rate": 0.9, "anomaly_count": 0},
        )
        promoted = _request(
            "POST",
            f"{remote.base_url}/v1/strategy/candidates/{candidate['candidate_id']}/promote",
            "secret-token",
            {"actor": "reviewer@example.com", "reason": "Canary and review both passed."},
        )
        state = _request("GET", f"{remote.base_url}/v1/tasks/{result.task_id}/collaboration", "secret-token")
        strategy = _request("GET", f"{remote.base_url}/v1/strategy/overview?scope_key={result.task_id}", "secret-token")

        assert collaboration["owner"] == "owner@example.com"
        assert lease["phase"] == "delivery"
        assert handoff["to_actor"] == "operator@example.com"
        assert scope_record["audience_scope"] == "task_shared"
        assert summary["summary_kind"] == "handoff_summary"
        assert evaluated["status"] in {"passed", "failed"}
        assert canary["candidate_id"] == candidate["candidate_id"]
        assert promoted["decision"] in {"promoted", "rolled_back"}
        assert state["branches"][0]["title"] == "Collect final evidence"
        assert strategy["feedback_signals"][0]["signal_kind"] == "handoff_quality"
        assert strategy["promotion_decisions"][0]["candidate_id"] == candidate["candidate_id"]
    finally:
        remote.shutdown()
