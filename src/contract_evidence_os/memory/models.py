"""Memory-layer models for the baseline and AMOS lanes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from contract_evidence_os.base import SchemaModel


@dataclass
class MemoryRecord(SchemaModel):
    """Stored memory item with lifecycle state."""

    version: str
    memory_id: str
    memory_type: str
    state: str
    summary: str
    content: dict[str, Any]
    sources: list[str]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryPromotionRecord(SchemaModel):
    """Record of a memory lifecycle promotion."""

    version: str
    promotion_id: str
    memory_id: str
    previous_state: str
    new_state: str
    rationale: str
    promoted_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class RawEpisodeRecord(SchemaModel):
    """L0 raw append-only episodic ledger entry."""

    version: str
    episode_id: str
    task_id: str
    episode_type: str
    actor: str
    scope_key: str
    project_id: str | None
    content: dict[str, Any]
    source: str
    consent: str
    trust: float
    dialogue_time: datetime
    event_time_start: datetime | None
    event_time_end: datetime | None
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class WorkingMemorySnapshot(SchemaModel):
    """L1 short-lived execution-critical state."""

    version: str
    snapshot_id: str
    task_id: str
    scope_key: str
    active_goal: str
    constraints: list[str]
    confirmed_facts: list[str]
    tentative_facts: list[str]
    evidence_refs: list[str]
    pending_actions: list[str]
    preferences: dict[str, str]
    scratchpad: list[str]
    captured_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryWriteCandidate(SchemaModel):
    """Candidate memory item before governance and consolidation."""

    version: str
    candidate_id: str
    task_id: str
    scope_key: str
    lane: str
    summary: str
    content: dict[str, Any]
    sources: list[str]
    importance: float
    novelty: float
    utility: float
    repetition: float
    privacy_risk: float
    poison_risk: float
    contradiction_risk: float
    governance_status: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryAdmissionPolicy(SchemaModel):
    """Policy controlling memory write admission and quarantine."""

    version: str
    policy_id: str
    scope_key: str
    policy_name: str
    quarantine_poison_threshold: float
    block_poison_threshold: float
    require_confirmation_threshold: float
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryAdmissionDecision(SchemaModel):
    """Admission result before consolidation is allowed."""

    version: str
    decision_id: str
    candidate_id: str
    scope_key: str
    action: str
    risk_score: float
    reasons: list[str]
    policy_id: str | None
    decided_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryAdmissionLearningState(SchemaModel):
    """Trace-informed learning state for admission and quarantine sensitivity."""

    version: str
    learning_id: str
    scope_key: str
    examples_seen: int
    poison_pattern_boost: float
    contradiction_boost: float
    privacy_confirmation_boost: float
    recommended_quarantine_threshold: float
    recommended_block_threshold: float
    trained_at: datetime
    recommended_confirmation_threshold: float = 0.8
    controller_version: str = "v1"
    feature_weights: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryAdmissionFeatureScore(SchemaModel):
    """Feature-scored write-controller output for one candidate."""

    version: str
    score_id: str
    candidate_id: str
    scope_key: str
    controller_version: str
    feature_values: dict[str, float]
    weighted_score: float
    recommended_action: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryGovernanceDecision(SchemaModel):
    """Governed action for a candidate memory write."""

    version: str
    decision_id: str
    candidate_id: str
    task_id: str
    scope_key: str
    action: str
    trust: float
    blocked_reasons: list[str]
    sensitivity: str
    decided_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class TemporalSemanticFact(SchemaModel):
    """L3 typed semantic memory with validity intervals and provenance."""

    version: str
    fact_id: str
    task_id: str
    scope_key: str
    subject: str
    predicate: str
    object: str
    head: str
    confidence: float
    provenance: list[str]
    observed_at: datetime
    valid_from: datetime | None
    valid_until: datetime | None
    status: str
    supersedes_fact_id: str | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class DurativeMemoryRecord(SchemaModel):
    """Durative temporal memory distilled from multiple semantic events."""

    version: str
    durative_id: str
    task_id: str
    scope_key: str
    subject: str
    predicate: str
    summary: str
    event_fact_ids: list[str]
    valid_from: datetime | None
    valid_until: datetime | None
    status: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MatrixAssociationPointer(SchemaModel):
    """L4 source-grounded associative pointer, not an authoritative fact."""

    version: str
    pointer_id: str
    task_id: str
    scope_key: str
    head: str
    key_terms: list[str]
    summary: str
    target_episode_ids: list[str]
    target_fact_ids: list[str]
    target_pattern_ids: list[str]
    strength: float
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProceduralPattern(SchemaModel):
    """L5 procedural / skill memory distilled from successful traces."""

    version: str
    pattern_id: str
    task_id: str
    scope_key: str
    summary: str
    trigger: str
    preconditions: list[str]
    steps: list[str]
    tools: list[str]
    outcome: str
    failure_modes: list[str]
    sources: list[str]
    confidence: float
    status: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemorySoftwareProcedureRecord(SchemaModel):
    """Software-centric procedural memory distilled from governed app actions."""

    version: str
    procedure_id: str
    task_id: str
    scope_key: str
    software_name: str
    command_path: list[str]
    summary: str
    steps: list[str]
    failure_modes: list[str]
    provenance: list[str]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ExplicitMemoryRecord(SchemaModel):
    """L6 editable explicit memory slot."""

    version: str
    record_id: str
    task_id: str
    scope_key: str
    memory_class: str
    summary: str
    content: dict[str, Any]
    editable: bool
    sources: list[str]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryEvidencePack(SchemaModel):
    """Structured memory retrieval bundle given to the runtime."""

    version: str
    pack_id: str
    query: str
    scope_key: str
    raw_episode_ids: list[str]
    semantic_fact_ids: list[str]
    matrix_pointer_ids: list[str]
    procedural_pattern_ids: list[str]
    discarded_conflict_fact_ids: list[str]
    temporal_notes: list[str]
    assembled_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryWriteReceipt(SchemaModel):
    """Auditable receipt for candidate admission and resulting AMOS writes."""

    version: str
    receipt_id: str
    candidate_id: str
    task_id: str
    scope_key: str
    lane: str
    summary: str
    governance_action: str
    source_ids: list[str]
    semantic_fact_ids: list[str]
    procedural_pattern_ids: list[str]
    matrix_pointer_ids: list[str]
    explicit_record_ids: list[str]
    lifecycle_trace_ids: list[str]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryDashboardItem(SchemaModel):
    """Operator-visible summary row for memory state."""

    version: str
    item_id: str
    scope_key: str
    source_kind: str
    summary: str
    status: str
    confidence: float
    provenance: list[str]
    valid_from: datetime | None
    valid_until: datetime | None
    updated_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryTombstoneRecord(SchemaModel):
    """Deletion tombstone for a memory-derived record."""

    version: str
    tombstone_id: str
    scope_key: str
    target_kind: str
    target_id: str
    actor: str
    reason: str
    deleted_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryDeletionRun(SchemaModel):
    """One governed deletion run over a memory scope."""

    version: str
    run_id: str
    scope_key: str
    actor: str
    reason: str
    deleted_record_count: int
    deleted_kinds: dict[str, int]
    started_at: datetime
    completed_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryDeletionReceipt(SchemaModel):
    """Unified deletion receipt over tombstone, selective purge, and hard purge flows."""

    version: str
    receipt_id: str
    scope_key: str
    actor: str
    mode: str
    target_kinds: list[str]
    deleted_record_count: int
    manifest_run_id: str | None
    reason: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryConsolidationRun(SchemaModel):
    """Offline or deferred consolidation run for AMOS."""

    version: str
    run_id: str
    scope_key: str
    reason: str
    created_durative_count: int
    superseded_fact_count: int
    deduplicated_pointer_count: int
    started_at: datetime
    completed_at: datetime
    synthesized_project_state_count: int = 0
    contradiction_merge_count: int = 0
    contradiction_repair_count: int = 0

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryConsolidationPolicy(SchemaModel):
    """Stable public view of consolidation policy defaults for one scope."""

    version: str
    policy_id: str
    scope_key: str
    controller_version: str
    synthesis_mode: str
    contradiction_merge_enabled: bool
    cross_scope_stitching_enabled: bool
    pointer_regeneration_enabled: bool
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryRebuildRun(SchemaModel):
    """Index rebuild and pointer regeneration run."""

    version: str
    run_id: str
    scope_key: str
    reason: str
    rebuild_status: str
    rebuilt_pointer_count: int
    rebuilt_dashboard_item_count: int
    started_at: datetime
    completed_at: datetime
    rebuilt_artifact_count: int = 0

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryHardPurgeRun(SchemaModel):
    """Physical purge of selected memory kinds in a scope."""

    version: str
    run_id: str
    scope_key: str
    actor: str
    reason: str
    target_kinds: list[str]
    purged_record_count: int
    started_at: datetime
    completed_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemorySelectivePurgeRun(SchemaModel):
    """Physical purge of selected derived memory records while preserving retained lanes."""

    version: str
    run_id: str
    scope_key: str
    actor: str
    reason: str
    target_kinds: list[str]
    purged_record_count: int
    preserved_record_count: int
    started_at: datetime
    completed_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryPurgeManifest(SchemaModel):
    """Explicit purge manifest for artifact and index cleanup runs."""

    version: str
    manifest_id: str
    run_id: str
    scope_key: str
    purge_mode: str
    target_kinds: list[str]
    purged_record_ids: dict[str, list[str]]
    cascaded_record_ids: dict[str, list[str]]
    preserved_summary: dict[str, int]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryArtifactRecord(SchemaModel):
    """Registered external artifact or generated index file for a memory scope."""

    version: str
    artifact_id: str
    scope_key: str
    artifact_kind: str
    path: str
    status: str
    source_run_id: str | None
    created_at: datetime
    updated_at: datetime
    backend_kind: str = "local_fs"
    backend_ref: str | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryTimelineSegment(SchemaModel):
    """Reconstructed timeline segment for durative state understanding."""

    version: str
    segment_id: str
    scope_key: str
    subject: str
    predicate: str
    state_object: str
    start_at: datetime | None
    end_at: datetime | None
    supporting_fact_ids: list[str]
    previous_segment_id: str | None
    next_segment_id: str | None
    transition_kind: str
    created_at: datetime
    contradicted_fact_ids: list[str] = field(default_factory=list)
    merge_reason: str = ""

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryCrossScopeTimelineSegment(SchemaModel):
    """Cross-scope reconstructed timeline segment for related state progression."""

    version: str
    segment_id: str
    scope_keys: list[str]
    subject: str
    predicate: str
    state_object: str
    start_at: datetime | None
    end_at: datetime | None
    supporting_fact_ids: list[str]
    previous_segment_id: str | None
    next_segment_id: str | None
    transition_kind: str
    created_at: datetime
    contradicted_fact_ids: list[str] = field(default_factory=list)
    merge_reason: str = ""

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryProjectStateSnapshot(SchemaModel):
    """Operator-visible reconstructed project state from timeline and active facts."""

    version: str
    snapshot_id: str
    scope_key: str
    subject: str
    summary: str
    active_states: list[str]
    contradiction_count: int
    timeline_segment_ids: list[str]
    supporting_fact_ids: list[str]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryTimelineView(SchemaModel):
    """Structured public view over timeline reconstruction output."""

    version: str
    view_id: str
    scope_key: str
    subject: str | None
    predicate: str | None
    segment_ids: list[str]
    active_segment_ids: list[str]
    contradiction_count: int
    generated_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryProjectStateView(SchemaModel):
    """Structured public view over reconstructed project state."""

    version: str
    view_id: str
    scope_key: str
    subject: str
    snapshot_id: str | None
    summary: str
    active_states: list[str]
    contradiction_count: int
    generated_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryContradictionRepairRecord(SchemaModel):
    """Recommended repair for conflicting cross-scope semantic state."""

    version: str
    repair_id: str
    scope_keys: list[str]
    subject: str
    predicate: str
    conflicting_fact_ids: list[str]
    recommended_state_object: str
    rationale: str
    repair_status: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryAdmissionCanaryRun(SchemaModel):
    """Canary comparison between baseline and learned write-admission behavior."""

    version: str
    run_id: str
    scope_key: str
    candidate_ids: list[str]
    controller_version: str
    recommendation: str
    metrics: dict[str, float]
    started_at: datetime
    completed_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemorySelectiveRebuildRun(SchemaModel):
    """Targeted rebuild or partial repair for selected AMOS layers."""

    version: str
    run_id: str
    scope_key: str
    reason: str
    target_kinds: list[str]
    rebuilt_counts: dict[str, int]
    started_at: datetime
    completed_at: datetime
    status: str = "completed"

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryRepairCanaryRun(SchemaModel):
    """Canary decision for whether a contradiction repair should be applied."""

    version: str
    run_id: str
    scope_keys: list[str]
    subject: str
    predicate: str
    repair_ids: list[str]
    recommendation: str
    metrics: dict[str, Any]
    started_at: datetime
    completed_at: datetime
    controller_version: str = "v1"

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryRepairSafetyAssessment(SchemaModel):
    """Safety assessment for whether a contradiction repair is safe to apply."""

    version: str
    assessment_id: str
    repair_id: str
    scope_keys: list[str]
    conflict_fact_count: int
    conflicting_state_count: int
    safety_score: float
    recommendation: str
    rationale: str
    created_at: datetime
    controller_version: str = "v1"
    base_safety_score: float | None = None
    effective_safety_score: float | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryRepairPolicy(SchemaModel):
    """Stable public view of repair safety and rollout defaults for one scope."""

    version: str
    policy_id: str
    scope_key: str
    controller_version: str
    safety_gate_required: bool
    canary_required: bool
    auto_apply_enabled: bool
    rollback_supported: bool
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryRepairLearningState(SchemaModel):
    """Trace-informed learning state for contradiction repair safety and rollout caution."""

    version: str
    learning_id: str
    scope_keys: list[str]
    examples_seen: int
    hold_signal_count: int
    rollback_signal_count: int
    learned_risk_penalty: float
    apply_threshold: float
    trained_at: datetime
    controller_version: str = "v2"

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryRepairActionRun(SchemaModel):
    """Apply or rollback action over a contradiction repair recommendation."""

    version: str
    run_id: str
    repair_id: str
    action: str
    actor: str
    reason: str
    previous_statuses: dict[str, str]
    updated_statuses: dict[str, str]
    started_at: datetime
    completed_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryRepairRolloutAnalyticsRecord(SchemaModel):
    """Observed repair rollout analytics after apply or rollback."""

    version: str
    analytics_id: str
    repair_id: str
    action: str
    affected_fact_ids: list[str]
    active_state_count_before: int
    active_state_count_after: int
    rollback_restored_count: int
    safety_score: float
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryOperationsLoopRun(SchemaModel):
    """Joined sleep-time memory operations loop covering synthesize, repair, and rebuild."""

    version: str
    run_id: str
    scope_key: str
    reason: str
    consolidation_run_id: str | None
    selective_rebuild_run_id: str | None
    status: str
    synthesized_project_state_count: int
    rebuilt_artifact_count: int
    contradiction_repair_count: int
    started_at: datetime
    completed_at: datetime
    interrupted_phase: str | None = None
    resumed_from_run_id: str | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryAdmissionPromotionRecommendation(SchemaModel):
    """Recommendation for promoting a learned admission policy path."""

    version: str
    recommendation_id: str
    scope_key: str
    source_canary_run_ids: list[str]
    controller_version: str
    recommendation: str
    confidence: float
    rationale: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryOperationsLoopSchedule(SchemaModel):
    """Periodic schedule for running the AMOS memory operations loop."""

    version: str
    schedule_id: str
    scope_key: str
    cadence_hours: int
    enabled: bool
    actor: str
    next_run_at: datetime
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryOperationsLoopRecoveryRecord(SchemaModel):
    """Recovery record for an interrupted memory operations loop."""

    version: str
    recovery_id: str
    loop_run_id: str
    scope_key: str
    interrupted_phase: str
    status: str
    actor: str
    created_at: datetime
    recovered_at: datetime | None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryOperationsDiagnosticRecord(SchemaModel):
    """Operator-visible diagnostic summary for memory repair fabric health."""

    version: str
    diagnostic_id: str
    scope_key: str
    missing_artifact_count: int
    repair_backlog_count: int
    interrupted_loop_count: int
    due_schedule_count: int
    recommendation_count: int
    created_at: datetime
    missing_shared_artifact_count: int = 0
    maintenance_recommendation_count: int = 0

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryArtifactBackendHealthRecord(SchemaModel):
    """Health snapshot for one artifact/index backend serving a memory scope."""

    version: str
    health_id: str
    scope_key: str
    backend_kind: str
    total_artifact_count: int
    missing_artifact_count: int
    created_at: datetime
    healthy: bool = True

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryArtifactBackendRepairRun(SchemaModel):
    """Repair run for a memory artifact backend such as a shared index mirror."""

    version: str
    run_id: str
    scope_key: str
    backend_kind: str
    actor: str
    reason: str
    repaired_artifact_count: int
    repaired_paths: list[str]
    started_at: datetime
    completed_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryArtifactDriftRecord(SchemaModel):
    """Detected drift between local and shared artifact/index representations."""

    version: str
    drift_id: str
    scope_key: str
    artifact_kind: str
    local_artifact_id: str | None
    shared_artifact_id: str | None
    local_path: str | None
    shared_path: str | None
    drift_kind: str
    summary: str
    status: str
    detected_at: datetime
    reconciled_at: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryMaintenanceIncidentRecord(SchemaModel):
    """Incident record emitted when background maintenance enters a degraded path."""

    version: str
    incident_id: str
    scope_key: str
    incident_kind: str
    severity: str
    summary: str
    mode: str
    status: str
    created_at: datetime
    related_run_id: str | None = None
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryMaintenanceRecommendation(SchemaModel):
    """Operator-visible recommendation bundle for background memory maintenance."""

    version: str
    recommendation_id: str
    scope_key: str
    actions: list[str]
    reasons: list[str]
    pending_repair_ids: list[str]
    pending_recovery_ids: list[str]
    due_schedule_ids: list[str]
    created_at: datetime
    controller_version: str = "v1"

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryMaintenanceRun(SchemaModel):
    """Auditable background maintenance run executing recommendations for one scope."""

    version: str
    run_id: str
    scope_key: str
    recommendation_id: str
    actor: str
    executed_actions: list[str]
    resumed_loop_run_ids: list[str]
    repair_canary_run_ids: list[str]
    repair_action_run_ids: list[str]
    artifact_backend_repair_run_ids: list[str]
    started_at: datetime
    completed_at: datetime
    status: str = "completed"
    interrupted_phase: str | None = None
    resumed_from_run_id: str | None = None
    schedule_id: str | None = None
    claimed_by_worker_id: str | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryMaintenanceLearningState(SchemaModel):
    """Trace-informed learning state for background maintenance recommendation scoring."""

    version: str
    learning_id: str
    scope_key: str
    examples_seen: int
    recovery_weight: float
    shared_backend_weight: float
    repair_backlog_weight: float
    fallback_weight: float
    trained_at: datetime
    controller_version: str = "v2"

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryMaintenanceCanaryRun(SchemaModel):
    """Canary comparison between baseline and learned maintenance recommendation scoring."""

    version: str
    run_id: str
    scope_key: str
    controller_version: str
    baseline_actions: list[str]
    learned_actions: list[str]
    recommendation: str
    metrics: dict[str, float]
    started_at: datetime
    completed_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryMaintenancePromotionRecommendation(SchemaModel):
    """Recommendation for promoting learned maintenance recommendation behavior."""

    version: str
    recommendation_id: str
    scope_key: str
    source_canary_run_ids: list[str]
    controller_version: str
    recommendation: str
    confidence: float
    rationale: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryMaintenanceControllerState(SchemaModel):
    """Active maintenance controller state for one memory scope."""

    version: str
    state_id: str
    scope_key: str
    active_controller_version: str
    status: str
    updated_at: datetime
    last_canary_run_id: str | None = None
    last_promotion_recommendation_id: str | None = None
    last_rollout_id: str | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryMaintenanceRolloutRecord(SchemaModel):
    """Apply or rollback record for maintenance controller rollout decisions."""

    version: str
    rollout_id: str
    scope_key: str
    recommendation_id: str | None
    action: str
    from_controller_version: str
    to_controller_version: str
    actor: str
    reason: str
    created_at: datetime
    related_rollout_id: str | None = None
    status: str = "completed"

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryMaintenanceWorkerRecord(SchemaModel):
    """Registered background maintenance worker with heartbeat and claim state."""

    version: str
    worker_id: str
    host_id: str
    actor: str
    status: str
    current_mode: str
    registered_at: datetime
    last_heartbeat_at: datetime
    claimed_schedule_ids: list[str]
    active_run_ids: list[str]

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryMaintenanceSchedule(SchemaModel):
    """Periodic schedule for background memory maintenance."""

    version: str
    schedule_id: str
    scope_key: str
    cadence_hours: int
    enabled: bool
    actor: str
    next_run_at: datetime
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
    claimed_by_worker_id: str | None = None
    lease_expires_at: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryMaintenanceRecoveryRecord(SchemaModel):
    """Recovery record for an interrupted background maintenance run."""

    version: str
    recovery_id: str
    maintenance_run_id: str
    scope_key: str
    interrupted_phase: str
    status: str
    actor: str
    created_at: datetime
    recovered_at: datetime | None
    schedule_id: str | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryMaintenanceAnalyticsRecord(SchemaModel):
    """Observed analytics for one background maintenance execution."""

    version: str
    analytics_id: str
    scope_key: str
    run_id: str
    executed_actions: list[str]
    resumed_loop_count: int
    applied_repair_count: int
    repaired_shared_artifact_count: int
    fallback_action_count: int
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MaintenanceWorkerLeaseState(SchemaModel):
    """Current lease state for one resident maintenance worker."""

    version: str
    lease_state_id: str
    worker_id: str
    host_id: str
    claimed_schedule_ids: list[str]
    lease_seconds: int
    stale: bool
    captured_at: datetime
    lease_expires_at: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MaintenanceDaemonRun(SchemaModel):
    """Resident maintenance daemon execution summary."""

    version: str
    daemon_run_id: str
    worker_id: str
    host_id: str
    actor: str
    daemon_mode: bool
    poll_interval_seconds: int
    heartbeat_seconds: int
    lease_seconds: int
    cycles_completed: int
    started_at: datetime
    completed_at: datetime
    maintenance_run_ids: list[str]
    reclaimed_worker_ids: list[str]
    status: str = "completed"
    interrupted_phase: str | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MaintenanceIncidentRecommendation(SchemaModel):
    """Action recommendation attached to a maintenance incident."""

    version: str
    recommendation_id: str
    scope_key: str
    incident_id: str
    recommended_actions: list[str]
    rationale: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MaintenanceResolutionAnalytics(SchemaModel):
    """Closure analytics for resolving maintenance incidents."""

    version: str
    resolution_id: str
    scope_key: str
    incident_id: str
    actor: str
    resolution: str
    restored_mode: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryScopeRecord(SchemaModel):
    """Scoped memory record for personal, task, workspace, or published layers."""

    version: str
    record_id: str
    task_id: str
    scope_key: str
    memory_kind: str
    summary: str
    content: dict[str, Any]
    evidence_refs: list[str]
    owner_user_id: str
    audience_scope: str
    promotion_state: str
    trust_state: str
    review_state: str
    retention_policy: str
    privacy_level: str
    contradiction_risk: float
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class MemoryPromotionDecision(SchemaModel):
    """Promotion or demotion decision for a scoped memory record."""

    version: str
    decision_id: str
    record_id: str
    task_id: str
    scope_key: str
    actor: str
    source_scope: str
    target_scope: str
    decision: str
    reason: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SummaryRecord(SchemaModel):
    """Evidence-bound summary generated for one task or workspace scope."""

    version: str
    summary_id: str
    task_id: str
    scope_key: str
    summary_kind: str
    actor: str
    audience_scope: str
    summary_text: str
    evidence_refs: list[str]
    source_record_ids: list[str]
    trust_state: str
    review_state: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class TaskCollaborationMemory(SchemaModel):
    """Shared collaboration-oriented memory for task coordination."""

    version: str
    collaboration_memory_id: str
    task_id: str
    scope_key: str
    owner_user_id: str
    summary: str
    evidence_refs: list[str]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class DecisionMemory(SchemaModel):
    """Decision memory promoted from private or task-shared work."""

    version: str
    decision_memory_id: str
    task_id: str
    scope_key: str
    owner_user_id: str
    decision_summary: str
    decision_payload: dict[str, Any]
    evidence_refs: list[str]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ReviewMemory(SchemaModel):
    """Review outcome remembered for future task coordination."""

    version: str
    review_memory_id: str
    task_id: str
    scope_key: str
    reviewer: str
    summary: str
    review_state: str
    evidence_refs: list[str]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class WorkaroundMemory(SchemaModel):
    """Known workaround or remediation captured as memory."""

    version: str
    workaround_memory_id: str
    task_id: str
    scope_key: str
    owner_user_id: str
    summary: str
    workaround_steps: list[str]
    evidence_refs: list[str]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ToolUsageMemory(SchemaModel):
    """Memory of a successful or problematic tool usage pattern."""

    version: str
    tool_usage_memory_id: str
    task_id: str
    scope_key: str
    owner_user_id: str
    tool_name: str
    summary: str
    outcome: str
    evidence_refs: list[str]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SkillCapsule(SchemaModel):
    """Promotable procedural unit distilled from execution traces."""

    version: str
    skill_id: str
    name: str
    triggering_conditions: list[str]
    preferred_plan_pattern: list[str]
    tool_sequence: list[str]
    validation_pattern: list[str]
    failure_signals: list[str]
    memory_write_policy: str
    test_cases: list[str]
    promotion_status: str
    regression_risk: str

    def __post_init__(self) -> None:
        self.validate()
