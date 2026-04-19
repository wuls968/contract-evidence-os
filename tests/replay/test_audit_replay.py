from datetime import UTC, datetime

from contract_evidence_os.audit.ledger import AuditLedger
from contract_evidence_os.audit.models import AuditEvent


def _event(event_id: str, event_type: str, actor: str, tool_ref: str | None = None) -> AuditEvent:
    return AuditEvent(
        version="1.0",
        event_id=event_id,
        task_id="task-001",
        contract_id="contract-001",
        event_type=event_type,
        actor=actor,
        why=event_type,
        evidence_refs=[],
        tool_refs=[tool_ref] if tool_ref else [],
        approval_refs=[],
        result="success",
        rollback_occurred=False,
        learning_candidate_generated=False,
        system_version="0.1.0",
        skill_version="initial",
        timestamp=datetime(2026, 4, 17, 0, 0, tzinfo=UTC),
        risk_level="low",
    )


def test_audit_ledger_replays_and_filters_events(tmp_path) -> None:
    ledger = AuditLedger(tmp_path)
    first = _event("audit-001", "contract_compiled", "Strategist")
    second = _event("audit-002", "tool_invocation", "Researcher", "file-retrieval")

    ledger.record(first)
    ledger.record(second)

    replayed = ledger.replay_task("task-001")
    filtered = ledger.query(task_id="task-001", actor="Researcher", tool_ref="file-retrieval")

    assert [event.event_id for event in replayed] == ["audit-001", "audit-002"]
    assert [event.event_id for event in filtered] == ["audit-002"]
