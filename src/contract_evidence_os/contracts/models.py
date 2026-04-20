"""Contract-layer models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from contract_evidence_os.base import SchemaModel


@dataclass
class TaskContract(SchemaModel):
    """Primary execution contract for a task."""

    version: str
    contract_id: str
    user_goal: str
    normalized_goal: str
    deliverables: list[str]
    hard_constraints: list[str]
    soft_preferences: list[str]
    forbidden_actions: list[str]
    success_criteria: list[str]
    failure_conditions: list[str]
    evidence_requirements: list[str]
    risk_level: str
    approval_required: list[str]
    budget_limits: dict[str, int | float]
    time_limits: dict[str, int | float]
    tool_limits: list[str]
    uncertainty_tolerance: str
    memory_policy: str
    checkpoint_policy: str
    evolution_allowed_scope: list[str]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        super().validate()
        if not self.contract_id:
            raise ValueError("TaskContract requires a contract_id")
        if not self.user_goal:
            raise ValueError("TaskContract requires a user_goal")


@dataclass
class ContractDelta(SchemaModel):
    """Version-to-version contract change record."""

    version: str
    delta_id: str
    contract_id: str
    previous_version: str
    new_version: str
    changed_fields: list[str]
    reason: str
    author: str
    timestamp: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ContractLattice(SchemaModel):
    """Relationship map across root and derived contracts."""

    version: str
    root_contract_id: str
    contract_ids: list[str] = field(default_factory=list)
    inheritance: dict[str, list[str]] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.validate()
