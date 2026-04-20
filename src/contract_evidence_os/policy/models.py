"""Policy and approval models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from contract_evidence_os.base import SchemaModel, utc_now


@dataclass
class ApprovalRequest(SchemaModel):
    """Approval request for a gated action."""

    version: str
    request_id: str
    contract_id: str
    action: str
    reason: str
    requested_scope: list[str]
    risk_level: str
    status: str
    task_id: str = ""
    plan_node_id: str | None = None
    action_summary: str = ""
    risk_classification: str = ""
    relevant_contract_clause: str = ""
    relevant_evidence: list[str] = field(default_factory=list)
    alternatives_considered: list[str] = field(default_factory=list)
    if_denied: str = ""
    expiry_at: datetime | None = None
    audit_refs: list[str] = field(default_factory=list)
    receipt_refs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ApprovalDecision(SchemaModel):
    """Decision for a previously requested approval."""

    version: str
    request_id: str
    decision_id: str
    approver: str
    status: str
    approved_scope: list[str]
    rationale: str
    decided_at: datetime
    intervention_action: str = "approve"
    task_id: str = ""
    plan_node_id: str | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class HumanIntervention(SchemaModel):
    """Recorded operator intervention against a running task."""

    version: str
    intervention_id: str
    task_id: str
    action: str
    operator: str
    reason: str
    created_at: datetime
    payload: dict[str, str]

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class RemoteApprovalOperation(SchemaModel):
    """Remote approval action performed through the operator service."""

    version: str
    operation_id: str
    request_id: str
    task_id: str
    contract_id: str
    plan_node_id: str | None
    operator: str
    action: str
    status: str
    rationale: str
    audit_event_id: str = ""
    decision_id: str = ""
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()
