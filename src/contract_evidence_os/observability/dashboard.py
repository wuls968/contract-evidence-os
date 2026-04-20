"""Simple report-oriented observability helpers."""

from __future__ import annotations

from typing import Any


def build_task_dashboard(
    task: dict[str, Any],
    handoff_packet: dict[str, Any] | None,
    open_questions: list[dict[str, Any]],
    next_actions: list[dict[str, Any]],
    approval_queue: list[dict[str, Any]],
    recent_failures: list[dict[str, Any]],
    continuity_state: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a compact operator dashboard payload."""

    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "current_phase": task["current_phase"],
        "latest_checkpoint_id": task["latest_checkpoint_id"],
        "handoff_packet": handoff_packet,
        "open_questions": open_questions,
        "next_actions": next_actions,
        "approval_queue": approval_queue,
        "recent_failures": recent_failures,
        "continuity_state": continuity_state,
        "recovery_suggestion": "resume from latest checkpoint" if task["latest_checkpoint_id"] else "inspect replay bundle",
    }


def build_system_metrics_report(
    *,
    summary: dict[str, Any],
    memory: dict[str, Any],
    software_control: dict[str, Any],
    maintenance_mode_counts: dict[str, int],
    maintenance_incident_count: int,
    repair_backlog_count: int,
    purge_history: dict[str, int],
    rebuild_history: dict[str, int],
) -> dict[str, Any]:
    """Return a compact operator metrics report spanning runtime, AMOS, and software control."""

    return {
        "summary": summary,
        "amos": {
            "write_receipt_count": memory["write_receipt_count"],
            "evidence_pack_count": memory["evidence_pack_count"],
            "deletion_receipt_count": memory["deletion_receipt_count"],
            "controller_versions": memory["controller_versions"],
        },
        "maintenance": {
            "mode_counts": maintenance_mode_counts,
            "incident_count": maintenance_incident_count,
            "repair_backlog_count": repair_backlog_count,
            "purge_history": purge_history,
            "rebuild_history": rebuild_history,
        },
        "software_control": {
            "harness_count": software_control["harness_count"],
            "action_receipt_count": software_control["action_receipt_count"],
            "failure_pattern_count": software_control["failure_pattern_count"],
            "risk_distribution": software_control["risk_distribution"],
        },
    }


def build_software_control_report(
    *,
    summary: dict[str, Any],
    manifests: list[dict[str, Any]],
    action_receipts: list[dict[str, Any]],
    replay_records: list[dict[str, Any]],
    failure_patterns: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return a governed software-control report suitable for operator-facing surfaces."""

    return {
        "summary": summary,
        "manifests": manifests,
        "action_receipts": action_receipts,
        "replay_records": replay_records,
        "failure_patterns": failure_patterns,
    }
