"""Evolution-layer models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from contract_evidence_os.base import SchemaModel


@dataclass
class EvolutionCandidate(SchemaModel):
    """Candidate self-improvement proposal."""

    version: str
    candidate_id: str
    candidate_type: str
    source_traces: list[str]
    target_component: str
    hypothesis: str
    expected_benefit: str
    evaluation_suite: list[str]
    canary_scope: str
    rollback_plan: str
    promotion_result: str

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class EvaluationRun(SchemaModel):
    """Offline evaluation run for an evolution candidate."""

    version: str
    run_id: str
    candidate_id: str
    suite_name: str
    status: str
    metrics: dict[str, Any]
    started_at: datetime
    completed_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class CanaryRun(SchemaModel):
    """Canary deployment record for an evolution candidate."""

    version: str
    run_id: str
    candidate_id: str
    scope: str
    status: str
    metrics: dict[str, Any]
    started_at: datetime
    completed_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryLifecycleTrace(SchemaModel):
    """Lifecycle trace mined from memory admission, consolidation, purge, and rebuild events."""

    version: str
    trace_id: str
    scope_key: str
    events: list[str]
    metrics: dict[str, Any]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryPolicyMiningRun(SchemaModel):
    """Trace-mining run that proposed memory-policy candidates from lifecycle evidence."""

    version: str
    run_id: str
    scope_key: str
    trace_ids: list[str]
    proposed_candidate_ids: list[str]
    rationale: str
    created_at: datetime
    source_canary_run_ids: list[str] = field(default_factory=list)
    source_recommendation_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryPolicyAnalyticsRecord(SchemaModel):
    """Recommendation and rollback analytics for memory-policy candidates."""

    version: str
    analytics_id: str
    scope_key: str
    candidate_id: str
    recommendation: str
    supporting_trace_ids: list[str]
    evaluation_status: str | None
    canary_status: str | None
    promotion_state: str
    rollback_risk: float
    rationale: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()
