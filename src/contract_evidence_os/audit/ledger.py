"""Append-only audit ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from contract_evidence_os.audit.models import AuditEvent
from contract_evidence_os.storage.repository import SQLiteRepository


@dataclass
class AuditLedger:
    """Persist and query audit events."""

    storage_root: Path | None = None
    repository: SQLiteRepository | None = None
    events: list[AuditEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.repository is None:
            if self.storage_root is None:
                raise ValueError("AuditLedger requires a storage_root or repository")
            self.storage_root.mkdir(parents=True, exist_ok=True)
            self.repository = SQLiteRepository(self.storage_root / "contract_evidence_os.sqlite3")

    def record(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        self.repository.save_audit_event(event)
        return event

    def query(
        self,
        task_id: str | None = None,
        event_type: str | None = None,
        actor: str | None = None,
        tool_ref: str | None = None,
        risk_level: str | None = None,
    ) -> list[AuditEvent]:
        return self.repository.query_audit(
            task_id=task_id,
            event_type=event_type,
            actor=actor,
            tool_ref=tool_ref,
            risk_level=risk_level,
        )

    def replay_task(self, task_id: str) -> list[AuditEvent]:
        """Return task events in ledger order for replay."""

        return self.repository.query_audit(task_id=task_id)
