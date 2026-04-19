"""Models for the trusted runtime, collaboration plane, and MCP surface."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from contract_evidence_os.base import SchemaModel, utc_now


@dataclass
class StructuredSchemaRecord(SchemaModel):
    """Structured schema published by the trusted runtime."""

    version: str
    schema_id: str
    schema_kind: str
    title: str
    json_schema: dict[str, Any]
    compatibility_notes: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class AuditLogEntry(SchemaModel):
    """Human-facing audit ledger entry."""

    version: str
    entry_id: str
    task_id: str
    event_type: str
    actor: str
    status: str
    summary: str
    evidence_refs: list[str]
    evidence_span_refs: list[str]
    related_refs: list[str]
    created_at: datetime = field(default_factory=utc_now)
    risk_level: str = "low"

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class AuditEventBundle(SchemaModel):
    """Grouped audit events for export or replay."""

    version: str
    bundle_id: str
    task_id: str
    entries: list[AuditLogEntry]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class PlaybookStep(SchemaModel):
    """Single executable step in a task playbook."""

    version: str
    step_id: str
    playbook_id: str
    title: str
    description: str
    status: str
    evidence_required: bool
    checkpoint_required: bool
    human_review_required: bool
    related_plan_node_id: str = ""
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class PlaybookRecord(SchemaModel):
    """Trusted task playbook synthesized from the contract and plan."""

    version: str
    playbook_id: str
    task_id: str
    title: str
    status: str
    rationale: str
    steps: list[PlaybookStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class HumanReviewDecision(SchemaModel):
    """Decision taken in a human review loop."""

    version: str
    decision_id: str
    case_id: str
    actor: str
    decision: str
    rationale: str
    evidence_refs: list[str]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class HumanReviewCase(SchemaModel):
    """Review case surfaced to operators or reviewers."""

    version: str
    case_id: str
    task_id: str
    review_kind: str
    status: str
    summary: str
    assignee: str
    evidence_refs: list[str]
    decisions: list[HumanReviewDecision] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class BenchmarkArtifact(SchemaModel):
    """Artifact emitted by a benchmark or repro-eval run."""

    version: str
    artifact_id: str
    run_id: str
    task_id: str
    artifact_kind: str
    locator: str
    status: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class BenchmarkRun(SchemaModel):
    """Human-facing benchmark run summary."""

    version: str
    run_id: str
    suite_id: str
    case_id: str
    task_id: str
    status: str
    score: float
    summary: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class BenchmarkCase(SchemaModel):
    """Benchmark case descriptor."""

    version: str
    case_id: str
    suite_id: str
    title: str
    description: str
    success_criteria: list[str]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class BenchmarkSuite(SchemaModel):
    """Benchmark suite grouping related benchmark cases."""

    version: str
    suite_id: str
    title: str
    description: str
    benchmark_kind: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ReproEvalRun(SchemaModel):
    """Reproducibility evaluation summary."""

    version: str
    repro_run_id: str
    task_id: str
    status: str
    summary: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ReproBundle(SchemaModel):
    """Bundle of artifacts and metadata needed to reproduce a run."""

    version: str
    bundle_id: str
    task_id: str
    artifact_ids: list[str]
    status: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class TaskCollaborationBinding(SchemaModel):
    """Task-level collaboration ownership and watch state."""

    version: str
    binding_id: str
    task_id: str
    owner: str
    reviewer: str
    watchers: list[str]
    approval_assignee: str
    blocked_by: str
    waiting_for: str
    recent_activity: list[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class TaskReviewerAssignment(SchemaModel):
    """Explicit reviewer assignment."""

    version: str
    assignment_id: str
    task_id: str
    reviewer: str
    review_kind: str
    status: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class WorkspaceInvitation(SchemaModel):
    """Invitation for small-team shared usage."""

    version: str
    invitation_id: str
    email: str
    role_name: str
    invited_by: str
    status: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SessionAuditRecord(SchemaModel):
    """Audit record for session lifecycle and auth-visible changes."""

    version: str
    session_audit_id: str
    session_id: str
    user_id: str
    action: str
    actor: str
    details: dict[str, Any]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MCPServerRecord(SchemaModel):
    """Registered MCP server or surface."""

    version: str
    server_id: str
    display_name: str
    transport: str
    endpoint: str
    direction: str
    enabled: bool
    status: str
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MCPToolRecord(SchemaModel):
    """Exposed or discovered MCP tool."""

    version: str
    tool_id: str
    server_id: str
    tool_name: str
    display_name: str
    description: str
    permission_mode: str
    schema_ref: str = ""
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MCPResourceRecord(SchemaModel):
    """Exposed or discovered MCP resource."""

    version: str
    resource_id: str
    server_id: str
    resource_name: str
    uri: str
    description: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MCPInvocationRecord(SchemaModel):
    """Invocation receipt for an MCP tool call."""

    version: str
    invocation_id: str
    server_id: str
    task_id: str
    tool_name: str
    actor: str
    status: str
    arguments: dict[str, Any]
    result_summary: str
    approval_required: bool
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MCPPermissionDecision(SchemaModel):
    """Permission decision for a governed MCP invocation."""

    version: str
    decision_id: str
    invocation_id: str
    actor: str
    decision: str
    rationale: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class TaskTimelineView(SchemaModel):
    """Timeline view for a task cockpit."""

    version: str
    task_id: str
    events: list[dict[str, Any]]
    summary: dict[str, Any]
    generated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class EvidenceTraceView(SchemaModel):
    """Traceable source-to-claim graph for the console."""

    version: str
    task_id: str
    sources: list[dict[str, Any]]
    spans: list[dict[str, Any]]
    claims: list[dict[str, Any]]
    validations: list[dict[str, Any]]
    trace_edges: list[dict[str, Any]]
    generated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class AuditTrendReport(SchemaModel):
    """Trend report for audit events over time."""

    version: str
    report_id: str
    points: list[dict[str, Any]]
    summary: dict[str, Any]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class BenchmarkSummaryView(SchemaModel):
    """Dashboard read model for benchmarks and repro-evals."""

    version: str
    summary_id: str
    suites: list[dict[str, Any]]
    latest_runs: list[dict[str, Any]]
    repro_runs: list[dict[str, Any]]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class CollaborationSummaryView(SchemaModel):
    """Dashboard read model for people, roles, sessions, and task ownership."""

    version: str
    summary_id: str
    users: list[dict[str, Any]]
    role_bindings: list[dict[str, Any]]
    sessions: list[dict[str, Any]]
    task_bindings: list[dict[str, Any]]
    invitations: list[dict[str, Any]]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()
