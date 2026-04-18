"""Audit-layer models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from contract_evidence_os.base import SchemaModel


@dataclass
class AuditEvent(SchemaModel):
    """Append-only audit event."""

    version: str
    event_id: str
    task_id: str
    contract_id: str
    event_type: str
    actor: str
    why: str
    evidence_refs: list[str]
    tool_refs: list[str]
    approval_refs: list[str]
    result: str
    rollback_occurred: bool
    learning_candidate_generated: bool
    system_version: str
    skill_version: str
    timestamp: datetime
    risk_level: str = "low"

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ExecutionReceipt(SchemaModel):
    """Receipt emitted by important execution steps."""

    version: str
    receipt_id: str
    contract_id: str
    plan_node_id: str
    actor: str
    tool_used: str
    input_summary: str
    output_summary: str
    artifacts: list[str]
    evidence_refs: list[str]
    validation_refs: list[str]
    approval_refs: list[str]
    status: str
    timestamp: datetime

    def __post_init__(self) -> None:
        self.validate()
