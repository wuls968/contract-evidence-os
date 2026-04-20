"""Code-based grading primitives."""

from __future__ import annotations

from typing import Any


def grade_expected_fact_coverage(expected_facts: list[str], actual_facts: list[dict[str, Any]]) -> float:
    """Grade how many expected facts are present in the delivery."""

    if not expected_facts:
        return 1.0
    statements = [str(fact.get("statement", "")).lower() for fact in actual_facts]
    matched = sum(1 for fact in expected_facts if fact.lower() in statements)
    return matched / len(expected_facts)


def grade_evidence_coverage(actual_facts: list[dict[str, Any]], minimum_refs: int) -> float:
    """Grade evidence coverage by counting evidence-bound facts."""

    if minimum_refs <= 0:
        return 1.0
    covered = sum(len(list(fact.get("evidence_refs", []))) for fact in actual_facts)
    return min(covered / minimum_refs, 1.0)


def grade_policy_violations(audit_events: list[dict[str, Any]]) -> float:
    """Grade policy violations; lower is worse."""

    violations = sum(
        1
        for event in audit_events
        if event.get("event_type") == "policy_violation" or event.get("result") == "denied"
    )
    return 0.0 if violations else 1.0


def grade_trace_integrity(
    audit_events: list[dict[str, Any]],
    execution_receipts: list[dict[str, Any]],
    routing_receipts: list[dict[str, Any]],
) -> float:
    """Grade whether the trace has the minimum expected artifacts."""

    if audit_events and execution_receipts and routing_receipts:
        return 1.0
    if audit_events and execution_receipts:
        return 0.75
    return 0.0


def grade_handoff_quality(handoff: dict[str, Any] | None, open_questions: list[dict[str, Any]], next_actions: list[dict[str, Any]]) -> float:
    """Grade whether the handoff contains sufficient structured continuity state."""

    if handoff is None:
        return 0.0
    score = 0.0
    if handoff.get("summary_sections"):
        score += 0.4
    if handoff.get("next_recommended_actions"):
        score += 0.3
    if handoff.get("open_question_ids") or open_questions:
        score += 0.15
    if handoff.get("pending_approval_ids") or next_actions:
        score += 0.15
    return min(score, 1.0)


def grade_continuity_reconstruction(working_set: dict[str, Any] | None, handoff: dict[str, Any] | None) -> float:
    """Grade whether the reconstructed working set aligns with the handoff."""

    if working_set is None or handoff is None:
        return 0.0
    score = 0.0
    if working_set.get("task_id") == handoff.get("task_id"):
        score += 0.25
    if working_set.get("plan_graph_id") == handoff.get("plan_graph_id"):
        score += 0.25
    if working_set.get("handoff_packet_id") == handoff.get("packet_id"):
        score += 0.25
    expected = set(handoff.get("blocked_nodes", []))
    actual = set(working_set.get("blocked_plan_nodes", []))
    if not expected and not actual:
        score += 0.25
    elif expected:
        score += 0.25 * (len(expected & actual) / len(expected))
    return min(score, 1.0)


def grade_open_question_resolution(before: list[dict[str, Any]], after: list[dict[str, Any]], final_status: str) -> float:
    """Grade whether unresolved questions were carried forward and then resolved or retained correctly."""

    if not before:
        return 1.0
    if final_status not in {"delivered", "completed"}:
        return 1.0 if after else 0.0
    unresolved_after = [item for item in after if item.get("status") == "open"]
    return 1.0 if not unresolved_after else max(0.0, 1.0 - (len(unresolved_after) / len(before)))


def grade_next_action_usefulness(next_actions: list[dict[str, Any]], final_status: str) -> float:
    """Grade whether next actions were present and led toward a sensible resume path."""

    if not next_actions:
        return 0.0
    if final_status in {"delivered", "completed"}:
        return 1.0
    urgent_actions = sum(1 for item in next_actions if item.get("urgency") == "high")
    return min(urgent_actions / len(next_actions), 1.0)
