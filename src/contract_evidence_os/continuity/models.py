"""Long-horizon continuity models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from contract_evidence_os.base import SchemaModel, utc_now


@dataclass
class HandoffSummarySection(SchemaModel):
    """One structured section within a handoff packet."""

    version: str
    section_id: str
    title: str
    content: str
    priority: int

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class HandoffPacketVersion(SchemaModel):
    """Version marker for a persisted handoff packet."""

    version: str
    packet_version_id: str
    packet_id: str
    task_id: str
    contract_version: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class EvidenceDeltaSummary(SchemaModel):
    """Compact evidence delta generated at checkpoints or session boundaries."""

    version: str
    delta_id: str
    task_id: str
    checkpoint_id: str
    new_facts_established: list[str]
    claims_strengthened: list[str]
    claims_weakened: list[str]
    contradictions_discovered: list[str]
    tests_passed: list[str]
    tests_failed: list[str]
    important_artifacts: list[str]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class OpenQuestion(SchemaModel):
    """Persisted unresolved question that matters to task progress."""

    version: str
    question_id: str
    contract_id: str
    related_plan_node: str | None
    why_it_matters: str
    current_known_evidence: list[str]
    missing_evidence: list[str]
    blocking_severity: str
    owner_role: str
    status: str
    resolution_notes: str

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class NextAction(SchemaModel):
    """Persistent next-action recommendation."""

    version: str
    action_id: str
    contract_id: str
    related_plan_node: str | None
    action_summary: str
    prerequisites: list[str]
    suggested_role: str
    suggested_toolchain: list[str]
    confidence: float
    urgency: str
    status: str

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class WorkspaceSnapshot(SchemaModel):
    """Structured snapshot of relevant workspace state."""

    version: str
    snapshot_id: str
    task_id: str
    active_artifacts: list[str]
    key_generated_files: list[str]
    recent_tool_outputs: list[str]
    environment_metadata: dict[str, str]
    audit_refs: list[str]
    evidence_refs: list[str]
    memory_refs: list[str]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ContextTier(SchemaModel):
    """One tier of continuity context."""

    version: str
    tier_name: str
    summary: str
    record_refs: list[str]
    token_estimate: int

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ContextCompaction(SchemaModel):
    """Compacted continuity state across hot, warm, and cold tiers."""

    version: str
    context_id: str
    task_id: str
    recent_execution_summary: str
    evidence_summary: str
    unresolved_issues_summary: str
    decision_rationale_summary: str
    pending_risks: list[str]
    memory_candidates: list[str]
    hot_context: ContextTier
    warm_context: ContextTier
    cold_context: ContextTier
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class PromptBudgetAllocation(SchemaModel):
    """Role-specific prompt/context budget allocation."""

    version: str
    allocation_id: str
    task_id: str
    role_name: str
    total_budget: int
    contract_budget: int
    active_plan_budget: int
    contradictions_budget: int
    evidence_budget: int
    approvals_budget: int
    memory_budget: int
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ContinuityWorkingSet(SchemaModel):
    """Execution-ready continuity slice reconstructed for a new session."""

    version: str
    working_set_id: str
    task_id: str
    contract_id: str
    plan_graph_id: str
    handoff_packet_id: str
    active_plan_nodes: list[str]
    blocked_plan_nodes: list[str]
    evidence_frontier_ids: list[str]
    open_question_ids: list[str]
    next_action_ids: list[str]
    pending_approval_ids: list[str]
    pending_risks: list[str]
    recommended_strategy: str
    hot_context: ContextTier
    warm_context: ContextTier
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class HandoffPacket(SchemaModel):
    """Formal handoff object for cross-session continuity."""

    version: str
    packet_id: str
    task_id: str
    contract_id: str
    contract_version: str
    plan_graph_id: str
    completed_nodes: list[str]
    blocked_nodes: list[str]
    next_recommended_actions: list[str]
    open_question_ids: list[str]
    unresolved_contradictions: list[str]
    key_evidence_delta_id: str
    current_risk_state: str
    pending_approval_ids: list[str]
    pending_memory_ids: list[str]
    recommended_strategy: str
    summary_sections: list[HandoffSummarySection] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()
