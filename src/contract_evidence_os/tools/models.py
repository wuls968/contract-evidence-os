"""Tool-layer models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from contract_evidence_os.base import SchemaModel


@dataclass
class ToolSpec(SchemaModel):
    """Structured specification for a tool adapter."""

    version: str
    tool_id: str
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_level: str
    permission_requirements: list[str]
    retry_policy: dict[str, Any]
    timeout_policy: dict[str, Any]
    audit_hooks: list[str]
    evidence_hooks: list[str]
    validation_hooks: list[str]
    mock_provider: str
    simulator_provider: str
    supports_replay: bool = True
    supports_idempotency: bool = True

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ToolInvocation(SchemaModel):
    """Record of a specific tool request."""

    version: str
    invocation_id: str
    tool_id: str
    actor: str
    input_payload: dict[str, Any]
    requested_at: datetime
    task_id: str = ""
    plan_node_id: str = ""
    correlation_id: str = ""
    idempotency_key: str = ""
    attempt: int = 1
    simulator_used: bool = False
    mock_used: bool = False

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ToolResult(SchemaModel):
    """Outcome of a tool invocation."""

    version: str
    invocation_id: str
    tool_id: str
    status: str
    output_payload: dict[str, Any]
    error: str | None
    started_at: datetime
    completed_at: datetime
    correlation_id: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None
    provider_mode: str = "live"
    deterministic: bool = False
    failure_classification: str | None = None
    suggested_follow_up_action: str | None = None
    artifact_refs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.validate()
