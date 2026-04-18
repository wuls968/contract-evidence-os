"""Plan graph models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from contract_evidence_os.base import SchemaModel


@dataclass
class PlanNode(SchemaModel):
    """Executable node in the plan graph."""

    version: str
    node_id: str
    objective: str
    role_owner: str
    dependencies: list[str]
    preconditions: list[str]
    expected_outputs: list[str]
    validation_gate: str
    fallback_paths: list[str]
    budget_cost: float
    status: str
    checkpoint_required: bool
    approval_gate: str | None
    node_category: str = "research"
    priority: int = 50
    branch_id: str = "branch-main"
    attachment_ref: str | None = None
    handler_name: str = ""

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class PlanEdge(SchemaModel):
    """Typed edge between plan nodes."""

    version: str
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class PlanGraph(SchemaModel):
    """Graph representation of task execution."""

    version: str
    graph_id: str
    active_branch_id: str = "branch-main"
    nodes: list[PlanNode] = field(default_factory=list)
    edges: list[PlanEdge] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class PlanRevision(SchemaModel):
    """Structured revision to part of a plan graph."""

    version: str
    revision_id: str
    task_id: str
    plan_graph_id: str
    cause: str
    affected_nodes: list[str]
    inserted_nodes: list[str]
    superseded_nodes: list[str]
    contract_id: str
    evidence_refs: list[str]
    approval_refs: list[str]
    branch_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ExecutionBranch(SchemaModel):
    """Persisted execution branch for recovery and comparison."""

    version: str
    branch_id: str
    task_id: str
    plan_graph_id: str
    parent_branch_id: str | None
    label: str
    status: str
    selected: bool
    cause: str
    node_ids: list[str]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SchedulerState(SchemaModel):
    """Durable scheduler state for ready/running/blocked node tracking."""

    version: str
    scheduler_id: str
    task_id: str
    plan_graph_id: str
    active_branch_id: str
    ready_queue: list[str]
    running_nodes: list[str]
    blocked_nodes: list[str]
    completed_nodes: list[str]
    failed_nodes: list[str]
    deferred_nodes: list[str]
    status: str
    updated_at: datetime

    def __post_init__(self) -> None:
        self.validate()
