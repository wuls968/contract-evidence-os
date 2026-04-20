from __future__ import annotations

from pathlib import Path

from contract_evidence_os.api.operator import OperatorAPI
from contract_evidence_os.console.service import ConsoleService
from contract_evidence_os.runtime.service import RuntimeService


def _build_runtime(tmp_path: Path) -> tuple[RuntimeService, str]:
    attachment = tmp_path / "brief.txt"
    attachment.write_text(
        "Share trustworthy summaries with the team, keep private notes scoped, and require human review before publication.\n",
        encoding="utf-8",
    )
    root = tmp_path / "runtime"
    runtime = RuntimeService(storage_root=root, routing_strategy="quality")
    result = runtime.run_task(
        goal="Read the attachment and summarize the trusted collaboration requirements.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not publish unreviewed summaries as trusted facts."],
    )
    return runtime, result.task_id


def test_runtime_supports_scoped_memory_strategy_and_task_collaboration(tmp_path: Path) -> None:
    runtime, task_id = _build_runtime(tmp_path)

    binding = runtime.configure_task_collaboration(
        task_id=task_id,
        owner="alice@example.com",
        reviewer="reviewer@example.com",
        operators=["alice@example.com", "bob@example.com"],
        watchers=["watcher@example.com"],
        approval_assignee="reviewer@example.com",
    )
    lease = runtime.acquire_task_lease(
        task_id=task_id,
        actor="alice@example.com",
        lease_kind="owner",
        phase="verification",
    )
    branch = runtime.create_task_branch(
        task_id=task_id,
        actor="alice@example.com",
        branch_kind="evidence",
        title="Collect policy evidence",
    )
    handoff = runtime.open_handoff_window(
        task_id=task_id,
        from_actor="alice@example.com",
        to_actor="bob@example.com",
        summary="Continue the evidence pass and request reviewer sign-off.",
        branch_id=branch.branch_id,
    )
    scoped = runtime.record_scoped_memory(
        task_id=task_id,
        actor="alice@example.com",
        owner_user_id="alice@example.com",
        audience_scope="personal_private",
        memory_kind="decision",
        summary="Need reviewer sign-off before publishing.",
        content={"decision": "wait_for_review"},
        evidence_refs=["evidence-1"],
        privacy_level="low",
        contradiction_risk=0.1,
    )
    promotion = runtime.promote_scoped_memory(
        record_id=scoped.record_id,
        actor="alice@example.com",
        target_scope="task_shared",
        reason="Share the decision with collaborators on the task.",
    )
    summary = runtime.generate_scope_summary(
        task_id=task_id,
        actor="alice@example.com",
        summary_kind="handoff_summary",
    )
    feedback = runtime.record_strategy_feedback(
        scope_key=task_id,
        actor="reviewer@example.com",
        strategy_kind="summarization_policy",
        signal_kind="review_accept",
        metrics={"quality": 1.0, "handoff_clarity": 1.0},
        evidence_refs=[summary.summary_id],
    )
    candidate = runtime.propose_strategy_candidate(
        scope_key=task_id,
        actor="reviewer@example.com",
        strategy_kind="summarization_policy",
        target_component="summary.handoff",
        hypothesis="Promote evidence-backed handoff summaries to task_shared after reviewer acceptance.",
        supporting_signal_ids=[feedback.signal_id],
    )
    evaluation = runtime.evaluate_strategy_candidate(candidate.candidate_id, regression_failures=0, gain=0.4)
    canary = runtime.run_strategy_canary(
        candidate.candidate_id,
        actor="reviewer@example.com",
        success_rate=0.98,
        anomaly_count=0,
        scope=task_id,
    )
    decision = runtime.promote_strategy_candidate(
        candidate.candidate_id,
        actor="reviewer@example.com",
        reason="Quality and handoff clarity signals remained healthy in canary.",
    )

    memory_state = runtime.memory_scope_state(scope_key=task_id)
    collaboration_state = runtime.task_collaboration_state(task_id=task_id)
    strategy_state = runtime.strategy_state(scope_key=task_id)

    assert binding.owner == "alice@example.com"
    assert lease.status == "active"
    assert branch.status == "active"
    assert handoff.status == "open"
    assert promotion.target_scope == "task_shared"
    assert summary.summary_kind == "handoff_summary"
    assert evaluation.status == "passed"
    assert canary.status == "promoted"
    assert decision.decision == "promoted"
    assert memory_state["records"][0]["audience_scope"] == "task_shared"
    assert collaboration_state["binding"]["owner"] == "alice@example.com"
    assert collaboration_state["active_leases"][0]["actor"] == "alice@example.com"
    assert collaboration_state["branches"][0]["branch_kind"] == "evidence"
    assert strategy_state["promotion_decisions"][0]["decision"] == "promoted"


def test_operator_and_console_expose_memory_scopes_strategies_and_collaboration(tmp_path: Path) -> None:
    runtime, task_id = _build_runtime(tmp_path)
    runtime.configure_task_collaboration(
        task_id=task_id,
        owner="owner@example.com",
        reviewer="reviewer@example.com",
        operators=["owner@example.com"],
        watchers=["watcher@example.com"],
        approval_assignee="reviewer@example.com",
    )
    runtime.acquire_task_lease(
        task_id=task_id,
        actor="owner@example.com",
        lease_kind="owner",
        phase="delivery",
    )
    runtime.create_task_branch(
        task_id=task_id,
        actor="owner@example.com",
        branch_kind="tool-run",
        title="Generate governed delivery preview",
    )
    runtime.record_scoped_memory(
        task_id=task_id,
        actor="owner@example.com",
        owner_user_id="owner@example.com",
        audience_scope="task_shared",
        memory_kind="tool_usage",
        summary="The governed provider build path was stable.",
        content={"tool": "provider_build"},
        evidence_refs=["evidence-2"],
        privacy_level="low",
        contradiction_risk=0.0,
    )
    runtime.generate_scope_summary(
        task_id=task_id,
        actor="owner@example.com",
        summary_kind="task_completion_summary",
    )
    signal = runtime.record_strategy_feedback(
        scope_key=task_id,
        actor="reviewer@example.com",
        strategy_kind="tool_selection_policy",
        signal_kind="replay_success",
        metrics={"success_rate": 1.0},
        evidence_refs=[],
    )
    runtime.propose_strategy_candidate(
        scope_key=task_id,
        actor="reviewer@example.com",
        strategy_kind="tool_selection_policy",
        target_component="tool.provider_build",
        hypothesis="Prefer the governed build path when replay success remains perfect.",
        supporting_signal_ids=[signal.signal_id],
    )

    root = tmp_path / "runtime"
    api = OperatorAPI(storage_root=root)
    config_path = root / "config.local.json"
    env_path = root / ".env.local"
    config_path.write_text("{}", encoding="utf-8")
    env_path.write_text("", encoding="utf-8")
    console = ConsoleService(api=api, config_path=config_path, env_path=env_path)

    memory_state = api.memory_scope_state(task_id)
    collaboration = api.task_collaboration(task_id)
    strategy = api.strategy_state(task_id)
    cockpit = console.task_cockpit(task_id)
    summary = console.collaboration_summary()

    assert memory_state["task_id"] == task_id
    assert memory_state["records"]
    assert memory_state["summaries"][0]["summary_kind"] == "task_completion_summary"
    assert collaboration["binding"]["owner"] == "owner@example.com"
    assert collaboration["active_leases"][0]["phase"] == "delivery"
    assert collaboration["branches"][0]["branch_kind"] == "tool-run"
    assert strategy["candidates"][0]["target_component"] == "tool.provider_build"
    assert cockpit["collaboration"]["active_leases"][0]["phase"] == "delivery"
    assert cockpit["memory_scopes"]["summaries"][0]["summary_kind"] == "task_completion_summary"
    assert summary.task_bindings
