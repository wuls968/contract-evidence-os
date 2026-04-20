"""AMOS memory facade with source-grounded associative recall."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from pathlib import Path
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.evolution.models import MemoryLifecycleTrace
from contract_evidence_os.memory.common import safe_memory_text, tokenize_memory_text, truncate_memory_text
from contract_evidence_os.memory.maintenance_service import MemoryMaintenanceService
from contract_evidence_os.memory.models import (
    MemoryAdmissionCanaryRun,
    MemoryAdmissionPromotionRecommendation,
    MemoryAdmissionLearningState,
    MemoryAdmissionFeatureScore,
    MemoryArtifactDriftRecord,
    MemoryArtifactBackendHealthRecord,
    MemoryArtifactBackendRepairRun,
    MemoryArtifactRecord,
    MemoryMaintenanceRecommendation,
    MemoryMaintenanceRun,
    MemoryMaintenanceAnalyticsRecord,
    MemoryMaintenanceCanaryRun,
    MemoryMaintenanceControllerState,
    MemoryMaintenanceIncidentRecord,
    MemoryMaintenanceLearningState,
    MemoryMaintenancePromotionRecommendation,
    MemoryMaintenanceRecoveryRecord,
    MemoryMaintenanceRolloutRecord,
    MemoryMaintenanceSchedule,
    MemoryMaintenanceWorkerRecord,
    MemorySelectiveRebuildRun,
    MemoryRepairCanaryRun,
    MemoryRepairActionRun,
    MemoryRepairLearningState,
    MemoryRepairPolicy,
    MemoryRepairSafetyAssessment,
    MemoryRepairRolloutAnalyticsRecord,
    MemoryOperationsLoopRun,
    MemoryOperationsLoopSchedule,
    MemoryOperationsLoopRecoveryRecord,
    MemoryOperationsDiagnosticRecord,
    MemoryCrossScopeTimelineSegment,
    DurativeMemoryRecord,
    ExplicitMemoryRecord,
    MemoryAdmissionDecision,
    MemoryAdmissionPolicy,
    MatrixAssociationPointer,
    MemoryConsolidationPolicy,
    MemoryConsolidationRun,
    MemoryContradictionRepairRecord,
    MemoryDashboardItem,
    MemoryDeletionReceipt,
    MemoryDeletionRun,
    MemoryEvidencePack,
    MemoryGovernanceDecision,
    MemoryHardPurgeRun,
    MemoryProjectStateSnapshot,
    MemoryProjectStateView,
    MemoryPromotionRecord,
    MemoryPurgeManifest,
    MemoryRecord,
    MemoryRebuildRun,
    MemorySelectivePurgeRun,
    MemorySoftwareProcedureRecord,
    MemoryTimelineSegment,
    MemoryTimelineView,
    MemoryTombstoneRecord,
    MemoryWriteCandidate,
    MemoryWriteReceipt,
    ProceduralPattern,
    RawEpisodeRecord,
    TemporalSemanticFact,
    WorkingMemorySnapshot,
)
from contract_evidence_os.memory.query_service import MemoryQueryService
from contract_evidence_os.storage.repository import SQLiteRepository

_tokenize = tokenize_memory_text
_safe_text = safe_memory_text
_truncate = truncate_memory_text


@dataclass
class MemoryMatrix:
    """Manage the baseline memory lifecycle and the AMOS layered memory lanes."""

    repository: SQLiteRepository | None = None
    artifact_root: Path | None = None
    shared_artifact_root: Path | None = None
    records: dict[str, MemoryRecord] = field(default_factory=dict)
    promotions: list[MemoryPromotionRecord] = field(default_factory=list)
    raw_episodes: dict[str, RawEpisodeRecord] = field(default_factory=dict)
    working_snapshots: dict[str, WorkingMemorySnapshot] = field(default_factory=dict)
    candidates: dict[str, MemoryWriteCandidate] = field(default_factory=dict)
    admission_policies: dict[str, MemoryAdmissionPolicy] = field(default_factory=dict)
    admission_decisions: dict[str, MemoryAdmissionDecision] = field(default_factory=dict)
    admission_learning_states: dict[str, MemoryAdmissionLearningState] = field(default_factory=dict)
    admission_feature_scores: dict[str, MemoryAdmissionFeatureScore] = field(default_factory=dict)
    governance_decisions: dict[str, MemoryGovernanceDecision] = field(default_factory=dict)
    semantic_facts: dict[str, TemporalSemanticFact] = field(default_factory=dict)
    durative_records: dict[str, DurativeMemoryRecord] = field(default_factory=dict)
    matrix_pointers: dict[str, MatrixAssociationPointer] = field(default_factory=dict)
    procedural_patterns: dict[str, ProceduralPattern] = field(default_factory=dict)
    explicit_records: dict[str, ExplicitMemoryRecord] = field(default_factory=dict)
    evidence_packs: dict[str, MemoryEvidencePack] = field(default_factory=dict)
    write_receipts: dict[str, MemoryWriteReceipt] = field(default_factory=dict)
    tombstones: dict[str, MemoryTombstoneRecord] = field(default_factory=dict)
    consolidation_runs: dict[str, MemoryConsolidationRun] = field(default_factory=dict)
    deletion_runs: dict[str, MemoryDeletionRun] = field(default_factory=dict)
    deletion_receipts: dict[str, MemoryDeletionReceipt] = field(default_factory=dict)
    rebuild_runs: dict[str, MemoryRebuildRun] = field(default_factory=dict)
    hard_purge_runs: dict[str, MemoryHardPurgeRun] = field(default_factory=dict)
    selective_purge_runs: dict[str, MemorySelectivePurgeRun] = field(default_factory=dict)
    purge_manifests: dict[str, MemoryPurgeManifest] = field(default_factory=dict)
    artifact_records: dict[str, MemoryArtifactRecord] = field(default_factory=dict)
    timeline_segments: dict[str, MemoryTimelineSegment] = field(default_factory=dict)
    cross_scope_timeline_segments: dict[str, MemoryCrossScopeTimelineSegment] = field(default_factory=dict)
    project_state_snapshots: dict[str, MemoryProjectStateSnapshot] = field(default_factory=dict)
    software_procedures: dict[str, MemorySoftwareProcedureRecord] = field(default_factory=dict)
    contradiction_repairs: dict[str, MemoryContradictionRepairRecord] = field(default_factory=dict)
    admission_canary_runs: dict[str, MemoryAdmissionCanaryRun] = field(default_factory=dict)
    selective_rebuild_runs: dict[str, MemorySelectiveRebuildRun] = field(default_factory=dict)
    repair_canary_runs: dict[str, MemoryRepairCanaryRun] = field(default_factory=dict)
    repair_action_runs: dict[str, MemoryRepairActionRun] = field(default_factory=dict)
    repair_learning_states: dict[str, MemoryRepairLearningState] = field(default_factory=dict)
    repair_safety_assessments: dict[str, MemoryRepairSafetyAssessment] = field(default_factory=dict)
    repair_rollout_analytics: dict[str, MemoryRepairRolloutAnalyticsRecord] = field(default_factory=dict)
    operations_loop_runs: dict[str, MemoryOperationsLoopRun] = field(default_factory=dict)
    admission_promotion_recommendations: dict[str, MemoryAdmissionPromotionRecommendation] = field(default_factory=dict)
    operations_loop_schedules: dict[str, MemoryOperationsLoopSchedule] = field(default_factory=dict)
    operations_loop_recoveries: dict[str, MemoryOperationsLoopRecoveryRecord] = field(default_factory=dict)
    operations_diagnostics: dict[str, MemoryOperationsDiagnosticRecord] = field(default_factory=dict)
    artifact_backend_health_records: dict[str, MemoryArtifactBackendHealthRecord] = field(default_factory=dict)
    artifact_backend_repair_runs: dict[str, MemoryArtifactBackendRepairRun] = field(default_factory=dict)
    artifact_drift_records: dict[str, MemoryArtifactDriftRecord] = field(default_factory=dict)
    maintenance_recommendations: dict[str, MemoryMaintenanceRecommendation] = field(default_factory=dict)
    maintenance_runs: dict[str, MemoryMaintenanceRun] = field(default_factory=dict)
    maintenance_learning_states: dict[str, MemoryMaintenanceLearningState] = field(default_factory=dict)
    maintenance_canary_runs: dict[str, MemoryMaintenanceCanaryRun] = field(default_factory=dict)
    maintenance_promotion_recommendations: dict[str, MemoryMaintenancePromotionRecommendation] = field(default_factory=dict)
    maintenance_controller_states: dict[str, MemoryMaintenanceControllerState] = field(default_factory=dict)
    maintenance_rollouts: dict[str, MemoryMaintenanceRolloutRecord] = field(default_factory=dict)
    maintenance_workers: dict[str, MemoryMaintenanceWorkerRecord] = field(default_factory=dict)
    maintenance_schedules: dict[str, MemoryMaintenanceSchedule] = field(default_factory=dict)
    maintenance_recoveries: dict[str, MemoryMaintenanceRecoveryRecord] = field(default_factory=dict)
    maintenance_analytics: dict[str, MemoryMaintenanceAnalyticsRecord] = field(default_factory=dict)
    maintenance_incidents: dict[str, MemoryMaintenanceIncidentRecord] = field(default_factory=dict)
    lifecycle_traces: dict[str, MemoryLifecycleTrace] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.query_service = MemoryQueryService(self)
        self.maintenance_service = MemoryMaintenanceService(self)

    def __getattr__(self, name: str) -> object:
        for attr_name in ("query_service", "maintenance_service"):
            service = object.__getattribute__(self, attr_name)
            if hasattr(type(service), name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")

    def write(
        self,
        memory_type: str,
        summary: str,
        content: dict[str, object],
        sources: list[str],
    ) -> MemoryRecord:
        now = utc_now()
        record = MemoryRecord(
            version="1.0",
            memory_id=f"memory-{uuid4().hex[:10]}",
            memory_type=memory_type,
            state="provisional",
            summary=summary,
            content=content,
            sources=sources,
            created_at=now,
            updated_at=now,
        )
        self.records[record.memory_id] = record
        if self.repository is not None:
            self.repository.save_memory_record(record)
        return record

    def validate(self, memory_id: str) -> MemoryRecord:
        record = self.get(memory_id)
        if record is None:
            raise KeyError(memory_id)
        record.state = "validated"
        record.updated_at = utc_now()
        if self.repository is not None:
            self.repository.save_memory_record(record)
        return record

    def promote(self, memory_id: str) -> MemoryPromotionRecord:
        record = self.get(memory_id)
        if record is None:
            raise KeyError(memory_id)
        if record.state != "validated":
            raise ValueError("Only validated memories can be promoted")
        promotion = MemoryPromotionRecord(
            version="1.0",
            promotion_id=f"promotion-{uuid4().hex[:10]}",
            memory_id=memory_id,
            previous_state=record.state,
            new_state="promoted",
            rationale="passed validation and is stable enough for reuse",
            promoted_at=utc_now(),
        )
        record.state = "promoted"
        record.updated_at = utc_now()
        self.promotions.append(promotion)
        if self.repository is not None:
            self.repository.save_memory_record(record)
            self.repository.save_memory_promotion(promotion)
        return promotion

    def get(self, memory_id: str) -> MemoryRecord | None:
        if memory_id in self.records:
            return self.records[memory_id]
        if self.repository is None:
            return None
        matches = [record for record in self.repository.list_memory_records() if record.memory_id == memory_id]
        if not matches:
            return None
        self.records[memory_id] = matches[0]
        return matches[0]

    def query(self, memory_type: str | None = None, state: str | None = None) -> list[MemoryRecord]:
        values = list(self.records.values()) if self.records else (
            [] if self.repository is None else self.repository.list_memory_records(memory_type=memory_type, state=state)
        )
        if memory_type:
            values = [record for record in values if record.memory_type == memory_type]
        if state:
            values = [record for record in values if record.state == state]
        return values

    def compress(self, memory_type: str) -> dict[str, object]:
        items = self.query(memory_type=memory_type)
        return {
            "memory_type": memory_type,
            "count": len(items),
            "summaries": [item.summary for item in items],
        }

    def detect_conflicts(self, memory_type: str) -> list[tuple[str, str]]:
        items = self.query(memory_type=memory_type)
        conflicts: list[tuple[str, str]] = []
        for index, left in enumerate(items):
            for right in items[index + 1 :]:
                if left.summary == right.summary and left.content != right.content:
                    conflicts.append((left.memory_id, right.memory_id))
        return conflicts

    def rollback(self, memory_id: str, state: str = "validated") -> MemoryRecord:
        record = self.get(memory_id)
        if record is None:
            raise KeyError(memory_id)
        record.state = state
        record.updated_at = utc_now()
        if self.repository is not None:
            self.repository.save_memory_record(record)
        return record

    def evict(self, memory_id: str) -> MemoryRecord | None:
        return self.records.pop(memory_id, None)

    def record_raw_episode(
        self,
        *,
        task_id: str,
        episode_type: str,
        actor: str,
        scope_key: str,
        project_id: str | None,
        content: dict[str, object],
        source: str,
        consent: str,
        trust: float,
        dialogue_time: datetime,
        event_time_start: datetime | None,
        event_time_end: datetime | None = None,
    ) -> RawEpisodeRecord:
        episode = RawEpisodeRecord(
            version="1.0",
            episode_id=f"episode-{uuid4().hex[:10]}",
            task_id=task_id,
            episode_type=episode_type,
            actor=actor,
            scope_key=scope_key,
            project_id=project_id,
            content=dict(content),
            source=source,
            consent=consent,
            trust=trust,
            dialogue_time=dialogue_time,
            event_time_start=event_time_start,
            event_time_end=event_time_end,
            created_at=utc_now(),
        )
        self.raw_episodes[episode.episode_id] = episode
        if self.repository is not None:
            self.repository.save_raw_episode(episode)
        return episode

    def list_raw_episodes(self, task_id: str | None = None, scope_key: str | None = None) -> list[RawEpisodeRecord]:
        records = list(self.raw_episodes.values())
        if self.repository is not None:
            repository_records = self.repository.list_raw_episodes(task_id=task_id, scope_key=scope_key)
            for record in repository_records:
                self.raw_episodes[record.episode_id] = record
            records = repository_records
        if task_id is not None:
            records = [record for record in records if record.task_id == task_id]
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        tombstones_by_scope = self._tombstone_index(scope_key)
        records = [
            record
            for record in records
            if ("raw_episode", record.episode_id) not in tombstones_by_scope.get(record.scope_key, set())
        ]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def capture_working_memory(
        self,
        *,
        task_id: str,
        scope_key: str,
        active_goal: str,
        constraints: list[str],
        confirmed_facts: list[str],
        tentative_facts: list[str],
        evidence_refs: list[str],
        pending_actions: list[str],
        preferences: dict[str, str],
        scratchpad: list[str],
    ) -> WorkingMemorySnapshot:
        snapshot = WorkingMemorySnapshot(
            version="1.0",
            snapshot_id=f"working-{uuid4().hex[:10]}",
            task_id=task_id,
            scope_key=scope_key,
            active_goal=active_goal,
            constraints=list(constraints),
            confirmed_facts=list(confirmed_facts),
            tentative_facts=list(tentative_facts),
            evidence_refs=list(evidence_refs),
            pending_actions=list(pending_actions),
            preferences=dict(preferences),
            scratchpad=list(scratchpad),
            captured_at=utc_now(),
        )
        self.working_snapshots[snapshot.snapshot_id] = snapshot
        if self.repository is not None:
            self.repository.save_working_memory_snapshot(snapshot)
        return snapshot

    def latest_working_memory_snapshot(self, task_id: str) -> WorkingMemorySnapshot | None:
        if self.repository is not None:
            repository_snapshot = self.repository.latest_working_memory_snapshot(task_id)
            if repository_snapshot is not None:
                self.working_snapshots[repository_snapshot.snapshot_id] = repository_snapshot
        local = [record for record in self.working_snapshots.values() if record.task_id == task_id]
        if not local:
            return None
        return sorted(local, key=lambda item: item.captured_at, reverse=True)[0]

    def _load_admission_policy(self, scope_key: str) -> MemoryAdmissionPolicy | None:
        if scope_key in self.admission_policies:
            return self.admission_policies[scope_key]
        if self.repository is None:
            return None
        policy = self.repository.load_memory_admission_policy(scope_key)
        if policy is not None:
            self.admission_policies[scope_key] = policy
        return policy

    def _load_admission_learning_state(self, scope_key: str) -> MemoryAdmissionLearningState | None:
        if scope_key in self.admission_learning_states:
            return self.admission_learning_states[scope_key]
        if self.repository is None:
            return None
        state = self.repository.load_memory_admission_learning_state(scope_key)
        if state is not None:
            self.admission_learning_states[scope_key] = state
        return state

    def _load_maintenance_learning_state(self, scope_key: str) -> MemoryMaintenanceLearningState | None:
        if scope_key in self.maintenance_learning_states:
            return self.maintenance_learning_states[scope_key]
        if self.repository is None:
            return None
        matches = self.repository.list_memory_maintenance_learning_states(scope_key=scope_key)
        if not matches:
            return None
        state = sorted(matches, key=lambda item: item.trained_at, reverse=True)[0]
        self.maintenance_learning_states[scope_key] = state
        return state

    def _load_maintenance_controller_state(self, scope_key: str) -> MemoryMaintenanceControllerState:
        if scope_key in self.maintenance_controller_states:
            return self.maintenance_controller_states[scope_key]
        if self.repository is not None:
            matches = self.repository.list_memory_maintenance_controller_states(scope_key=scope_key)
            if matches:
                state = sorted(matches, key=lambda item: item.updated_at, reverse=True)[0]
                self.maintenance_controller_states[scope_key] = state
                return state
        state = MemoryMaintenanceControllerState(
            version="1.0",
            state_id=f"maintenance-controller-state-{uuid4().hex[:10]}",
            scope_key=scope_key,
            active_controller_version="v1",
            status="active",
            updated_at=utc_now(),
            last_canary_run_id=None,
            last_promotion_recommendation_id=None,
            last_rollout_id=None,
        )
        self.maintenance_controller_states[scope_key] = state
        if self.repository is not None:
            self.repository.save_memory_maintenance_controller_state(state)
        return state

    def _get_maintenance_worker(self, worker_id: str) -> MemoryMaintenanceWorkerRecord:
        if worker_id in self.maintenance_workers:
            return self.maintenance_workers[worker_id]
        if self.repository is not None:
            matches = [item for item in self.repository.list_memory_maintenance_worker_records() if item.worker_id == worker_id]
            if matches:
                self.maintenance_workers[worker_id] = matches[0]
                return matches[0]
        raise KeyError(worker_id)

    def _repair_scope_group_key(self, scope_keys: list[str]) -> str:
        return "|".join(sorted(scope_keys))

    def _load_repair_learning_state(self, scope_keys: list[str]) -> MemoryRepairLearningState | None:
        group_key = self._repair_scope_group_key(scope_keys)
        if group_key in self.repair_learning_states:
            return self.repair_learning_states[group_key]
        if self.repository is None:
            return None
        matches = self.repository.list_memory_repair_learning_states(scope_keys=scope_keys)
        if not matches:
            return None
        state = sorted(matches, key=lambda item: item.trained_at, reverse=True)[0]
        self.repair_learning_states[group_key] = state
        return state

    def list_admission_feature_scores(
        self,
        *,
        candidate_id: str | None = None,
        scope_key: str | None = None,
    ) -> list[MemoryAdmissionFeatureScore]:
        records = list(self.admission_feature_scores.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_admission_feature_scores(candidate_id)
            for record in repository_records:
                self.admission_feature_scores[record.score_id] = record
            records = repository_records
        if candidate_id is not None:
            records = [record for record in records if record.candidate_id == candidate_id]
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_purge_manifests(self, *, scope_key: str | None = None) -> list[MemoryPurgeManifest]:
        records = list(self.purge_manifests.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_purge_manifests(scope_key=scope_key)
            for record in repository_records:
                self.purge_manifests[record.manifest_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_project_state_snapshots(self, *, scope_key: str | None = None) -> list[MemoryProjectStateSnapshot]:
        records = list(self.project_state_snapshots.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_project_state_snapshots(scope_key)
            for record in repository_records:
                self.project_state_snapshots[record.snapshot_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_artifacts(
        self,
        *,
        scope_key: str | None = None,
        artifact_kind: str | None = None,
    ) -> list[MemoryArtifactRecord]:
        records = list(self.artifact_records.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_artifact_records(scope_key=scope_key)
            for record in repository_records:
                self.artifact_records[record.artifact_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        if artifact_kind is not None:
            records = [record for record in records if record.artifact_kind == artifact_kind]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def list_memory_contradiction_repairs(
        self,
        *,
        scope_keys: list[str] | None = None,
    ) -> list[MemoryContradictionRepairRecord]:
        records = list(self.contradiction_repairs.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_contradiction_repair_records(scope_keys=scope_keys)
            for record in repository_records:
                self.contradiction_repairs[record.repair_id] = record
            records = repository_records
        if scope_keys is not None:
            expected = set(scope_keys)
            records = [record for record in records if set(record.scope_keys) == expected]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_admission_canary_runs(self, *, scope_key: str | None = None) -> list[MemoryAdmissionCanaryRun]:
        records = list(self.admission_canary_runs.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_admission_canary_runs(scope_key=scope_key)
            for record in repository_records:
                self.admission_canary_runs[record.run_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.completed_at, reverse=True)

    def list_selective_rebuild_runs(self, *, scope_key: str | None = None) -> list[MemorySelectiveRebuildRun]:
        records = list(self.selective_rebuild_runs.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_selective_rebuild_runs(scope_key=scope_key)
            for record in repository_records:
                self.selective_rebuild_runs[record.run_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.completed_at, reverse=True)

    def list_repair_canary_runs(self, *, scope_keys: list[str] | None = None) -> list[MemoryRepairCanaryRun]:
        records = list(self.repair_canary_runs.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_repair_canary_runs(scope_keys=scope_keys)
            for record in repository_records:
                self.repair_canary_runs[record.run_id] = record
            records = repository_records
        if scope_keys is not None:
            expected = set(scope_keys)
            records = [record for record in records if set(record.scope_keys) == expected]
        return sorted(records, key=lambda item: item.completed_at, reverse=True)

    def list_repair_action_runs(self, *, repair_id: str | None = None) -> list[MemoryRepairActionRun]:
        records = list(self.repair_action_runs.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_repair_action_runs(repair_id=repair_id)
            for record in repository_records:
                self.repair_action_runs[record.run_id] = record
            records = repository_records
        if repair_id is not None:
            records = [record for record in records if record.repair_id == repair_id]
        return sorted(records, key=lambda item: item.completed_at, reverse=True)

    def list_repair_safety_assessments(
        self,
        *,
        scope_keys: list[str] | None = None,
    ) -> list[MemoryRepairSafetyAssessment]:
        records = list(self.repair_safety_assessments.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_repair_safety_assessments(scope_keys=scope_keys)
            for record in repository_records:
                self.repair_safety_assessments[record.assessment_id] = record
            records = repository_records
        if scope_keys is not None:
            expected = set(scope_keys)
            records = [record for record in records if set(record.scope_keys) == expected]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_repair_learning_states(
        self,
        *,
        scope_keys: list[str] | None = None,
    ) -> list[MemoryRepairLearningState]:
        records = list(self.repair_learning_states.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_repair_learning_states(scope_keys=scope_keys)
            for record in repository_records:
                self.repair_learning_states[self._repair_scope_group_key(record.scope_keys)] = record
            records = repository_records
        if scope_keys is not None:
            expected = set(scope_keys)
            records = [record for record in records if set(record.scope_keys) == expected]
        return sorted(records, key=lambda item: item.trained_at, reverse=True)

    def list_repair_rollout_analytics(
        self,
        *,
        repair_id: str | None = None,
    ) -> list[MemoryRepairRolloutAnalyticsRecord]:
        records = list(self.repair_rollout_analytics.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_repair_rollout_analytics_records(repair_id=repair_id)
            for record in repository_records:
                self.repair_rollout_analytics[record.analytics_id] = record
            records = repository_records
        if repair_id is not None:
            records = [record for record in records if record.repair_id == repair_id]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_operations_loop_runs(self, *, scope_key: str | None = None) -> list[MemoryOperationsLoopRun]:
        records = list(self.operations_loop_runs.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_operations_loop_runs(scope_key=scope_key)
            for record in repository_records:
                self.operations_loop_runs[record.run_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.completed_at, reverse=True)

    def list_admission_promotion_recommendations(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryAdmissionPromotionRecommendation]:
        records = list(self.admission_promotion_recommendations.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_admission_promotion_recommendations(scope_key=scope_key)
            for record in repository_records:
                self.admission_promotion_recommendations[record.recommendation_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_operations_loop_schedules(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryOperationsLoopSchedule]:
        records = list(self.operations_loop_schedules.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_operations_loop_schedules(scope_key=scope_key)
            for record in repository_records:
                self.operations_loop_schedules[record.schedule_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def list_memory_operations_loop_recoveries(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryOperationsLoopRecoveryRecord]:
        records = list(self.operations_loop_recoveries.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_operations_loop_recovery_records(scope_key=scope_key)
            for record in repository_records:
                self.operations_loop_recoveries[record.recovery_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_operations_diagnostics(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryOperationsDiagnosticRecord]:
        records = list(self.operations_diagnostics.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_operations_diagnostic_records(scope_key=scope_key)
            for record in repository_records:
                self.operations_diagnostics[record.diagnostic_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_artifact_backend_health(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryArtifactBackendHealthRecord]:
        records = list(self.artifact_backend_health_records.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_artifact_backend_health_records(scope_key=scope_key)
            for record in repository_records:
                self.artifact_backend_health_records[record.health_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_artifact_backend_repairs(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryArtifactBackendRepairRun]:
        records = list(self.artifact_backend_repair_runs.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_artifact_backend_repair_runs(scope_key=scope_key)
            for record in repository_records:
                self.artifact_backend_repair_runs[record.run_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.completed_at, reverse=True)

    def list_memory_artifact_drift(
        self,
        *,
        scope_key: str | None = None,
        status: str | None = None,
    ) -> list[MemoryArtifactDriftRecord]:
        records = list(self.artifact_drift_records.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_artifact_drift_records(scope_key=scope_key)
            for record in repository_records:
                self.artifact_drift_records[record.drift_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        if status is not None:
            records = [record for record in records if record.status == status]
        return sorted(records, key=lambda item: item.detected_at, reverse=True)

    def list_memory_maintenance_recommendations(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceRecommendation]:
        records = list(self.maintenance_recommendations.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_maintenance_recommendations(scope_key=scope_key)
            for record in repository_records:
                self.maintenance_recommendations[record.recommendation_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_maintenance_runs(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceRun]:
        records = list(self.maintenance_runs.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_maintenance_runs(scope_key=scope_key)
            for record in repository_records:
                self.maintenance_runs[record.run_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.completed_at, reverse=True)

    def list_memory_maintenance_learning_states(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceLearningState]:
        records = list(self.maintenance_learning_states.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_maintenance_learning_states(scope_key=scope_key)
            for record in repository_records:
                self.maintenance_learning_states[record.scope_key] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.trained_at, reverse=True)

    def list_memory_maintenance_canary_runs(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceCanaryRun]:
        records = list(self.maintenance_canary_runs.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_maintenance_canary_runs(scope_key=scope_key)
            for record in repository_records:
                self.maintenance_canary_runs[record.run_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.completed_at, reverse=True)

    def list_memory_maintenance_promotions(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenancePromotionRecommendation]:
        records = list(self.maintenance_promotion_recommendations.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_maintenance_promotion_recommendations(scope_key=scope_key)
            for record in repository_records:
                self.maintenance_promotion_recommendations[record.recommendation_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_maintenance_controller_states(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceControllerState]:
        records = list(self.maintenance_controller_states.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_maintenance_controller_states(scope_key=scope_key)
            for record in repository_records:
                self.maintenance_controller_states[record.scope_key] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def list_memory_maintenance_rollouts(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceRolloutRecord]:
        records = list(self.maintenance_rollouts.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_maintenance_rollout_records(scope_key=scope_key)
            for record in repository_records:
                self.maintenance_rollouts[record.rollout_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_maintenance_workers(self) -> list[MemoryMaintenanceWorkerRecord]:
        records = list(self.maintenance_workers.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_maintenance_worker_records()
            for record in repository_records:
                self.maintenance_workers[record.worker_id] = record
            records = repository_records
        return sorted(records, key=lambda item: item.last_heartbeat_at, reverse=True)

    def list_memory_maintenance_schedules(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceSchedule]:
        records = list(self.maintenance_schedules.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_maintenance_schedules(scope_key=scope_key)
            for record in repository_records:
                self.maintenance_schedules[record.schedule_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.updated_at, reverse=True)

    def list_memory_maintenance_recoveries(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceRecoveryRecord]:
        records = list(self.maintenance_recoveries.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_maintenance_recovery_records(scope_key=scope_key)
            for record in repository_records:
                self.maintenance_recoveries[record.recovery_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_maintenance_analytics(
        self,
        *,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceAnalyticsRecord]:
        records = list(self.maintenance_analytics.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_maintenance_analytics_records(scope_key=scope_key)
            for record in repository_records:
                self.maintenance_analytics[record.analytics_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_maintenance_incidents(
        self,
        *,
        scope_key: str | None = None,
        status: str | None = None,
    ) -> list[MemoryMaintenanceIncidentRecord]:
        records = list(self.maintenance_incidents.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_maintenance_incident_records(scope_key=scope_key)
            for record in repository_records:
                self.maintenance_incidents[record.incident_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        if status is not None:
            records = [record for record in records if record.status == status]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_lifecycle_traces(self, *, scope_key: str | None = None) -> list[MemoryLifecycleTrace]:
        records = list(self.lifecycle_traces.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_lifecycle_traces(scope_key=scope_key)
            for record in repository_records:
                self.lifecycle_traces[record.trace_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_matrix_association_pointers(
        self,
        *,
        scope_key: str | None = None,
        task_id: str | None = None,
    ) -> list[MatrixAssociationPointer]:
        return self._list_matrix_pointers(scope_key=scope_key, task_id=task_id)

    def list_procedural_patterns(
        self,
        *,
        scope_key: str | None = None,
        task_id: str | None = None,
    ) -> list[ProceduralPattern]:
        return self._list_procedural_patterns(scope_key=scope_key, task_id=task_id)

    def list_memory_software_procedures(self, *, scope_key: str | None = None) -> list[MemorySoftwareProcedureRecord]:
        records = list(self.software_procedures.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_software_procedures(scope_key=scope_key)
            for record in repository_records:
                self.software_procedures[record.procedure_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_write_receipts(self, *, scope_key: str | None = None) -> list[MemoryWriteReceipt]:
        records = list(self.write_receipts.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_write_receipts(scope_key=scope_key)
            for record in repository_records:
                self.write_receipts[record.receipt_id] = record
            records = repository_records
        existing_candidates = {record.candidate_id for record in records}
        candidates = list(self.candidates.values())
        if self.repository is not None:
            repository_candidates = self.repository.list_memory_write_candidates(scope_key=scope_key)
            for candidate in repository_candidates:
                self.candidates[candidate.candidate_id] = candidate
            candidates = repository_candidates
        if scope_key is not None:
            candidates = [candidate for candidate in candidates if candidate.scope_key == scope_key]
        traces = self.list_memory_lifecycle_traces(scope_key=scope_key)
        trace_ids = [trace.trace_id for trace in traces[:3]]
        for candidate in candidates:
            if candidate.candidate_id in existing_candidates:
                continue
            decision = self.governance_decisions.get(candidate.candidate_id)
            if decision is None and self.repository is not None:
                decision = self.repository.latest_memory_governance_decision(candidate.candidate_id)
                if decision is not None:
                    self.governance_decisions[decision.candidate_id] = decision
            facts = [
                fact.fact_id
                for fact in self.list_temporal_semantic_facts(scope_key=candidate.scope_key, task_id=candidate.task_id)
                if set(candidate.sources) & set(fact.provenance)
            ]
            patterns = [
                pattern.pattern_id
                for pattern in self._list_procedural_patterns(scope_key=candidate.scope_key, task_id=candidate.task_id)
                if set(candidate.sources) & set(pattern.sources)
            ]
            explicit_records = []
            if self.repository is not None:
                explicit_records = [
                    record.record_id
                    for record in self.repository.list_explicit_memory_records(scope_key=candidate.scope_key)
                    if set(candidate.sources) & set(record.sources)
                ]
            pointers = [
                pointer.pointer_id
                for pointer in self._list_matrix_pointers(scope_key=candidate.scope_key, task_id=candidate.task_id)
                if set(pointer.target_fact_ids) & set(facts) or set(pointer.target_pattern_ids) & set(patterns)
            ]
            receipt = MemoryWriteReceipt(
                version="1.0",
                receipt_id=f"memory-write-receipt-{candidate.candidate_id}",
                candidate_id=candidate.candidate_id,
                task_id=candidate.task_id,
                scope_key=candidate.scope_key,
                lane=candidate.lane,
                summary=candidate.summary,
                governance_action=candidate.governance_status if decision is None else decision.action,
                source_ids=list(candidate.sources),
                semantic_fact_ids=facts,
                procedural_pattern_ids=patterns,
                matrix_pointer_ids=pointers,
                explicit_record_ids=explicit_records,
                lifecycle_trace_ids=list(trace_ids),
                created_at=candidate.created_at,
            )
            self.write_receipts[receipt.receipt_id] = receipt
            if self.repository is not None:
                self.repository.save_memory_write_receipt(receipt)
            records.append(receipt)
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def list_memory_deletion_receipts(self, *, scope_key: str | None = None) -> list[MemoryDeletionReceipt]:
        records = list(self.deletion_receipts.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_deletion_receipts(scope_key=scope_key)
            for record in repository_records:
                self.deletion_receipts[record.receipt_id] = record
            records = repository_records
        existing_receipt_ids = {record.receipt_id for record in records}
        for run in self.list_memory_deletion_runs(scope_key=scope_key):
            receipt_id = f"memory-delete-receipt-{run.run_id}"
            if receipt_id in existing_receipt_ids:
                continue
            receipt = MemoryDeletionReceipt(
                version="1.0",
                receipt_id=receipt_id,
                scope_key=run.scope_key,
                actor=run.actor,
                mode="tombstone",
                target_kinds=sorted(run.deleted_kinds),
                deleted_record_count=run.deleted_record_count,
                manifest_run_id=None,
                reason=run.reason,
                created_at=run.completed_at,
            )
            self.deletion_receipts[receipt.receipt_id] = receipt
            if self.repository is not None:
                self.repository.save_memory_deletion_receipt(receipt)
            records.append(receipt)
        for run in self.list_selective_purge_runs(scope_key=scope_key):
            receipt_id = f"memory-delete-receipt-{run.run_id}"
            if receipt_id in existing_receipt_ids:
                continue
            receipt = MemoryDeletionReceipt(
                version="1.0",
                receipt_id=receipt_id,
                scope_key=run.scope_key,
                actor=run.actor,
                mode="selective_purge",
                target_kinds=list(run.target_kinds),
                deleted_record_count=run.purged_record_count,
                manifest_run_id=run.run_id,
                reason=run.reason,
                created_at=run.completed_at,
            )
            self.deletion_receipts[receipt.receipt_id] = receipt
            if self.repository is not None:
                self.repository.save_memory_deletion_receipt(receipt)
            records.append(receipt)
        for run in self.list_hard_purge_runs(scope_key=scope_key):
            receipt_id = f"memory-delete-receipt-{run.run_id}"
            if receipt_id in existing_receipt_ids:
                continue
            receipt = MemoryDeletionReceipt(
                version="1.0",
                receipt_id=receipt_id,
                scope_key=run.scope_key,
                actor=run.actor,
                mode="hard_purge",
                target_kinds=list(run.target_kinds),
                deleted_record_count=run.purged_record_count,
                manifest_run_id=run.run_id,
                reason=run.reason,
                created_at=run.completed_at,
            )
            self.deletion_receipts[receipt.receipt_id] = receipt
            if self.repository is not None:
                self.repository.save_memory_deletion_receipt(receipt)
            records.append(receipt)
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def consolidation_policy(self, *, scope_key: str) -> MemoryConsolidationPolicy:
        return MemoryConsolidationPolicy(
            version="1.0",
            policy_id=f"memory-consolidation-policy-{scope_key}",
            scope_key=scope_key,
            controller_version="v3",
            synthesis_mode="rule_grounded_v3",
            contradiction_merge_enabled=True,
            cross_scope_stitching_enabled=True,
            pointer_regeneration_enabled=True,
            created_at=utc_now(),
        )

    def repair_policy(self, *, scope_key: str) -> MemoryRepairPolicy:
        controller_version = "v1"
        learning = self._load_repair_learning_state([scope_key])
        if learning is not None:
            controller_version = learning.controller_version
        return MemoryRepairPolicy(
            version="1.0",
            policy_id=f"memory-repair-policy-{scope_key}",
            scope_key=scope_key,
            controller_version=controller_version,
            safety_gate_required=True,
            canary_required=True,
            auto_apply_enabled=False,
            rollback_supported=True,
            created_at=utc_now(),
        )

    def record_lifecycle_trace(
        self,
        *,
        scope_key: str,
        events: list[str],
        metrics: dict[str, float],
    ) -> MemoryLifecycleTrace:
        trace = MemoryLifecycleTrace(
            version="1.0",
            trace_id=f"memory-trace-{uuid4().hex[:10]}",
            scope_key=scope_key,
            events=list(events),
            metrics=dict(metrics),
            created_at=utc_now(),
        )
        self.lifecycle_traces[trace.trace_id] = trace
        if self.repository is not None:
            self.repository.save_memory_lifecycle_trace(trace)
        return trace

    def train_admission_controller(self, *, scope_key: str) -> MemoryAdmissionLearningState:
        traces = self.list_memory_lifecycle_traces(scope_key=scope_key)
        policy = self._load_admission_policy(scope_key)
        suspicious_events = 0
        contradiction_events = 0
        privacy_events = 0
        tool_override_events = 0
        instruction_override_events = 0
        for trace in traces:
            suspicious_events += sum(
                1
                for event in trace.events
                if event in {"candidate_quarantined", "suspicious_override_detected", "hard_purge_completed", "selective_purge_completed"}
            )
            contradiction_events += sum(1 for event in trace.events if "contradiction" in event)
            privacy_events += sum(1 for event in trace.events if "privacy" in event or "sensitive" in event)
            tool_override_events += sum(1 for event in trace.events if "tool_override" in event)
            instruction_override_events += sum(1 for event in trace.events if "override" in event or "approval" in event)
            suspicious_events += int(float(trace.metrics.get("memory_poison_signal_rate", 0.0)) >= 0.5)
        base_quarantine = 0.65 if policy is None else policy.quarantine_poison_threshold
        base_block = 0.9 if policy is None else policy.block_poison_threshold
        base_confirmation = 0.8 if policy is None else policy.require_confirmation_threshold
        poison_pattern_boost = min(0.25, suspicious_events * 0.05)
        contradiction_boost = min(0.2, contradiction_events * 0.05)
        privacy_confirmation_boost = min(0.2, privacy_events * 0.05)
        feature_weights = {
            "instruction_override_signal": min(0.25, 0.08 + instruction_override_events * 0.03),
            "tool_override_signal": min(0.2, tool_override_events * 0.04),
            "contradiction_signal": min(0.2, contradiction_events * 0.05),
            "privacy_signal": min(0.2, privacy_events * 0.05),
            "single_source_signal": min(0.1, max(0, len(traces) - 1) * 0.01),
        }
        state = MemoryAdmissionLearningState(
            version="1.0",
            learning_id=f"admission-learning-{uuid4().hex[:10]}",
            scope_key=scope_key,
            examples_seen=len(traces),
            poison_pattern_boost=poison_pattern_boost,
            contradiction_boost=contradiction_boost,
            privacy_confirmation_boost=privacy_confirmation_boost,
            recommended_quarantine_threshold=max(0.35, base_quarantine - poison_pattern_boost),
            recommended_block_threshold=base_block,
            recommended_confirmation_threshold=max(0.2, base_confirmation - privacy_confirmation_boost / 2.0),
            controller_version="v2",
            feature_weights=feature_weights,
            trained_at=utc_now(),
        )
        self.admission_learning_states[scope_key] = state
        if self.repository is not None:
            self.repository.save_memory_admission_learning_state(state)
        return state

    def train_repair_controller(self, *, scope_keys: list[str]) -> MemoryRepairLearningState:
        assessments = self.list_repair_safety_assessments(scope_keys=scope_keys)
        rollout_records = [
            record
            for repair in self.list_memory_contradiction_repairs(scope_keys=scope_keys)
            for record in self.list_repair_rollout_analytics(repair_id=repair.repair_id)
        ]
        hold_signal_count = sum(1 for item in assessments if item.recommendation != "apply")
        rollback_signal_count = sum(1 for item in rollout_records if item.action == "rollback")
        learned_risk_penalty = min(0.3, hold_signal_count * 0.04 + rollback_signal_count * 0.08)
        state = MemoryRepairLearningState(
            version="1.0",
            learning_id=f"repair-learning-{uuid4().hex[:10]}",
            scope_keys=sorted(scope_keys),
            examples_seen=len(assessments) + len(rollout_records),
            hold_signal_count=hold_signal_count,
            rollback_signal_count=rollback_signal_count,
            learned_risk_penalty=learned_risk_penalty,
            apply_threshold=min(0.9, 0.75 + learned_risk_penalty / 2.0),
            trained_at=utc_now(),
            controller_version="v2",
        )
        group_key = self._repair_scope_group_key(scope_keys)
        self.repair_learning_states[group_key] = state
        if self.repository is not None:
            self.repository.save_memory_repair_learning_state(state)
        return state

    def configure_admission_policy(
        self,
        *,
        scope_key: str,
        policy_name: str,
        quarantine_poison_threshold: float,
        block_poison_threshold: float,
        require_confirmation_threshold: float,
    ) -> MemoryAdmissionPolicy:
        now = utc_now()
        policy = MemoryAdmissionPolicy(
            version="1.0",
            policy_id=f"memory-admission-{uuid4().hex[:10]}",
            scope_key=scope_key,
            policy_name=policy_name,
            quarantine_poison_threshold=quarantine_poison_threshold,
            block_poison_threshold=block_poison_threshold,
            require_confirmation_threshold=require_confirmation_threshold,
            created_at=now,
            updated_at=now,
        )
        self.admission_policies[scope_key] = policy
        if self.repository is not None:
            self.repository.save_memory_admission_policy(policy)
        return policy

    def list_quarantined_candidates(self, *, scope_key: str | None = None) -> list[MemoryWriteCandidate]:
        records = list(self.candidates.values())
        if self.repository is not None:
            for record in self.repository.list_memory_write_candidates(scope_key=scope_key):
                self.candidates[record.candidate_id] = record
            records = list(self.candidates.values())
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return [record for record in records if record.governance_status == "quarantined"]

    def create_candidate(
        self,
        *,
        task_id: str,
        scope_key: str,
        lane: str,
        summary: str,
        content: dict[str, object],
        sources: list[str],
    ) -> MemoryWriteCandidate:
        importance = min(1.0, 0.45 + (0.1 if lane in {"semantic", "procedural"} else 0.0) + 0.02 * len(sources))
        novelty = min(1.0, 0.6 + 0.01 * len(_tokenize(summary)))
        utility = min(1.0, 0.55 + (0.15 if lane in {"semantic", "procedural"} else 0.0))
        repetition = min(1.0, 0.4 + 0.05 * max(len(sources) - 1, 0))
        privacy_risk = 0.85 if self._contains_privacy_terms(summary, content) else 0.05
        poison_risk = self._poison_risk_score(summary, content)
        contradiction_risk = 0.4 if lane == "semantic" and self._has_existing_semantic_conflict(scope_key, content) else 0.05
        candidate = MemoryWriteCandidate(
            version="1.0",
            candidate_id=f"candidate-{uuid4().hex[:10]}",
            task_id=task_id,
            scope_key=scope_key,
            lane=lane,
            summary=summary,
            content=dict(content),
            sources=list(sources),
            importance=importance,
            novelty=novelty,
            utility=utility,
            repetition=repetition,
            privacy_risk=privacy_risk,
            poison_risk=poison_risk,
            contradiction_risk=contradiction_risk,
            governance_status="pending",
            created_at=utc_now(),
        )
        self.candidates[candidate.candidate_id] = candidate
        if self.repository is not None:
            self.repository.save_memory_write_candidate(candidate)
        return candidate

    def _record_admission_decision(
        self,
        *,
        candidate: MemoryWriteCandidate,
        action: str,
        risk_score: float,
        reasons: list[str],
        policy: MemoryAdmissionPolicy | None,
    ) -> MemoryAdmissionDecision:
        decision = MemoryAdmissionDecision(
            version="1.0",
            decision_id=f"memory-admission-{uuid4().hex[:10]}",
            candidate_id=candidate.candidate_id,
            scope_key=candidate.scope_key,
            action=action,
            risk_score=risk_score,
            reasons=reasons,
            policy_id=None if policy is None else policy.policy_id,
            decided_at=utc_now(),
        )
        self.admission_decisions[candidate.candidate_id] = decision
        if self.repository is not None:
            self.repository.save_memory_admission_decision(decision)
        return decision

    def govern_candidate(self, candidate_id: str) -> MemoryGovernanceDecision:
        candidate = self._get_candidate(candidate_id)
        policy = self._load_admission_policy(candidate.scope_key)
        learning_state = self._load_admission_learning_state(candidate.scope_key)
        adjusted_poison_risk = candidate.poison_risk
        adjusted_privacy_risk = candidate.privacy_risk
        adjusted_contradiction_risk = candidate.contradiction_risk
        if learning_state is not None:
            if candidate.poison_risk >= 0.5:
                adjusted_poison_risk = min(1.0, candidate.poison_risk + learning_state.poison_pattern_boost)
            adjusted_privacy_risk = min(1.0, candidate.privacy_risk + learning_state.privacy_confirmation_boost)
            adjusted_contradiction_risk = min(1.0, candidate.contradiction_risk + learning_state.contradiction_boost)
        feature_values = self._extract_admission_features(candidate)
        feature_score = self._score_admission_features(
            candidate=candidate,
            feature_values=feature_values,
            learning_state=learning_state,
        )
        risk_score = max(adjusted_poison_risk, adjusted_privacy_risk, adjusted_contradiction_risk, feature_score.weighted_score)
        blocked_reasons: list[str] = []
        admission_action = "accepted"
        quarantine_threshold = 0.65
        block_threshold = 0.9
        confirmation_threshold = 0.8
        if policy is not None:
            quarantine_threshold = policy.quarantine_poison_threshold
            block_threshold = policy.block_poison_threshold
            confirmation_threshold = policy.require_confirmation_threshold
        if learning_state is not None:
            quarantine_threshold = min(quarantine_threshold, learning_state.recommended_quarantine_threshold)
            block_threshold = min(block_threshold, learning_state.recommended_block_threshold)
            confirmation_threshold = min(
                confirmation_threshold,
                learning_state.recommended_confirmation_threshold,
            )
        if policy is not None:
            if max(adjusted_poison_risk, feature_score.weighted_score) >= block_threshold:
                admission_action = "blocked"
                blocked_reasons.append("candidate exceeded blocking poison threshold")
            elif max(adjusted_poison_risk, feature_score.weighted_score) >= quarantine_threshold:
                admission_action = "quarantined"
                blocked_reasons.append("candidate quarantined due to suspicious procedural override pattern")
            elif (
                adjusted_privacy_risk >= confirmation_threshold
                or adjusted_contradiction_risk >= confirmation_threshold
            ):
                admission_action = "requires_confirmation"
                blocked_reasons.append("candidate requires confirmation before durable write")
        else:
            if max(adjusted_poison_risk, feature_score.weighted_score) >= block_threshold:
                admission_action = "blocked"
                blocked_reasons.append("candidate exceeded default poison block threshold")
            elif max(adjusted_poison_risk, feature_score.weighted_score) >= quarantine_threshold:
                admission_action = "quarantined"
                blocked_reasons.append("candidate quarantined by default poison heuristics")
            elif adjusted_privacy_risk >= confirmation_threshold:
                admission_action = "requires_confirmation"
                blocked_reasons.append("sensitive content requires explicit confirmation")
        self._record_admission_decision(
            candidate=candidate,
            action=admission_action,
            risk_score=risk_score,
            reasons=list(blocked_reasons),
            policy=policy,
        )

        blocked_reasons: list[str] = []
        if admission_action in {"blocked", "quarantined", "requires_confirmation"}:
            blocked_reasons.extend(self.admission_decisions[candidate.candidate_id].reasons)
        elif adjusted_poison_risk >= 0.8:
            blocked_reasons.append("suspected memory poisoning or policy override attempt")
        if adjusted_privacy_risk >= 0.9:
            blocked_reasons.append("sensitive content requires explicit confirmation")
        if (
            feature_score.recommended_action in {"quarantined", "blocked"}
            and feature_score.feature_values.get("instruction_override_signal", 0.0) >= 0.5
        ):
            blocked_reasons.append("feature-scored controller detected instruction override pattern")
        if (
            feature_score.recommended_action in {"quarantined", "blocked"}
            and feature_score.feature_values.get("tool_override_signal", 0.0) >= 0.5
        ):
            blocked_reasons.append("feature-scored controller detected hidden tool override pattern")
        action_map = {
            "semantic": "semantic_memory",
            "procedural": "procedural_memory",
            "episodic": "episodic_only",
            "matrix": "matrix_memory",
            "explicit": "explicit_memory",
        }
        if admission_action in {"blocked", "quarantined", "requires_confirmation"}:
            action = admission_action
        else:
            action = "blocked" if blocked_reasons else action_map.get(candidate.lane, "episodic_only")
        candidate.governance_status = action
        decision = MemoryGovernanceDecision(
            version="1.0",
            decision_id=f"memory-governance-{uuid4().hex[:10]}",
            candidate_id=candidate.candidate_id,
            task_id=candidate.task_id,
            scope_key=candidate.scope_key,
            action=action,
            trust=max(0.0, 1.0 - adjusted_poison_risk - adjusted_privacy_risk / 2.0),
            blocked_reasons=blocked_reasons,
            sensitivity="high" if candidate.privacy_risk >= 0.8 else "normal",
            decided_at=utc_now(),
        )
        self.governance_decisions[candidate_id] = decision
        self.admission_feature_scores[feature_score.score_id] = feature_score
        if self.repository is not None:
            self.repository.save_memory_write_candidate(candidate)
            self.repository.save_memory_governance_decision(decision)
            self.repository.save_memory_admission_feature_score(feature_score)
        return decision

    def consolidate_candidate(self, candidate_id: str) -> dict[str, object]:
        candidate = self._get_candidate(candidate_id)
        decision = self._get_governance_decision(candidate_id)
        if decision is None or decision.action == "blocked":
            return {"status": "blocked"}
        if decision.action == "quarantined":
            return {"status": "quarantined"}
        if decision.action == "requires_confirmation":
            return {"status": "requires_confirmation"}
        if decision.action == "semantic_memory":
            fact = self._consolidate_semantic_candidate(candidate)
            pointer = self._write_matrix_pointer(
                candidate=candidate,
                head=str(candidate.content.get("head", "semantic")),
                summary=candidate.summary,
                target_fact_ids=[fact.fact_id],
                target_episode_ids=[source for source in candidate.sources if source.startswith("episode-")],
                target_pattern_ids=[],
            )
            return {"status": "consolidated", "semantic_facts": [fact], "matrix_associations": [pointer]}
        if decision.action == "procedural_memory":
            pattern = self._consolidate_procedural_candidate(candidate)
            pointer = self._write_matrix_pointer(
                candidate=candidate,
                head="procedure",
                summary=candidate.summary,
                target_fact_ids=[],
                target_episode_ids=[source for source in candidate.sources if source.startswith("episode-")],
                target_pattern_ids=[pattern.pattern_id],
            )
            return {"status": "consolidated", "procedural_patterns": [pattern], "matrix_associations": [pointer]}
        if decision.action == "explicit_memory":
            record = self._consolidate_explicit_candidate(candidate)
            return {"status": "consolidated", "explicit_records": [record]}
        return {"status": "skipped"}

    def tombstone_scope(self, *, scope_key: str, actor: str, reason: str) -> MemoryDeletionRun:
        started_at = utc_now()
        deleted_kinds: dict[str, int] = {}
        for record in self.list_raw_episodes(scope_key=scope_key):
            self._write_tombstone(scope_key=scope_key, target_kind="raw_episode", target_id=record.episode_id, actor=actor, reason=reason)
            deleted_kinds["raw_episode"] = deleted_kinds.get("raw_episode", 0) + 1
        for fact in self.list_temporal_semantic_facts(scope_key=scope_key):
            self._write_tombstone(scope_key=scope_key, target_kind="semantic_fact", target_id=fact.fact_id, actor=actor, reason=reason)
            deleted_kinds["semantic_fact"] = deleted_kinds.get("semantic_fact", 0) + 1
        for pointer in self._list_matrix_pointers(scope_key=scope_key):
            self._write_tombstone(scope_key=scope_key, target_kind="matrix_pointer", target_id=pointer.pointer_id, actor=actor, reason=reason)
            deleted_kinds["matrix_pointer"] = deleted_kinds.get("matrix_pointer", 0) + 1
        for pattern in self._list_procedural_patterns(scope_key=scope_key):
            self._write_tombstone(scope_key=scope_key, target_kind="procedural_pattern", target_id=pattern.pattern_id, actor=actor, reason=reason)
            deleted_kinds["procedural_pattern"] = deleted_kinds.get("procedural_pattern", 0) + 1
        for record in self.list_durative_memories(scope_key=scope_key):
            self._write_tombstone(scope_key=scope_key, target_kind="durative_record", target_id=record.durative_id, actor=actor, reason=reason)
            deleted_kinds["durative_record"] = deleted_kinds.get("durative_record", 0) + 1
        run = MemoryDeletionRun(
            version="1.0",
            run_id=f"memory-delete-{uuid4().hex[:10]}",
            scope_key=scope_key,
            actor=actor,
            reason=reason,
            deleted_record_count=sum(deleted_kinds.values()),
            deleted_kinds=deleted_kinds,
            started_at=started_at,
            completed_at=utc_now(),
        )
        self.deletion_runs[run.run_id] = run
        if self.repository is not None:
            self.repository.save_memory_deletion_run(run)
        return run

    def run_sleep_consolidation(self, *, scope_key: str, reason: str) -> MemoryConsolidationRun:
        started_at = utc_now()
        facts = self.list_temporal_semantic_facts(scope_key=scope_key)
        grouped: dict[tuple[str, str], list[TemporalSemanticFact]] = {}
        for fact in facts:
            grouped.setdefault((fact.subject, fact.predicate), []).append(fact)
        created_durative_count = 0
        deduplicated_pointer_count = 0
        for (subject, predicate), items in grouped.items():
            if len(items) < 2:
                continue
            ordered = sorted(items, key=lambda item: item.valid_from or item.observed_at)
            record = DurativeMemoryRecord(
                version="1.0",
                durative_id=f"durative-{subject}-{predicate}".replace(" ", "-"),
                task_id=ordered[-1].task_id,
                scope_key=scope_key,
                subject=subject,
                predicate=predicate,
                summary=f"{subject} has durative state for {predicate}",
                event_fact_ids=[item.fact_id for item in ordered],
                valid_from=ordered[0].valid_from,
                valid_until=ordered[-1].valid_until,
                status="active",
                created_at=utc_now(),
            )
            touched = record.durative_id not in self.durative_records or bool(ordered)
            self.durative_records[record.durative_id] = record
            if self.repository is not None:
                self.repository.save_durative_memory(record)
            if touched:
                created_durative_count += 1
        deduplicated_pointer_count = self._deduplicate_pointers(scope_key=scope_key)
        synthesized_project_state_count = 0
        contradiction_merge_count = 0
        seen_subjects = sorted({fact.subject for fact in facts})
        for subject in seen_subjects:
            snapshot = self.reconstruct_project_state(scope_key=scope_key, subject=subject)
            synthesized_project_state_count += 1
            contradiction_merge_count += snapshot.contradiction_count
        run = MemoryConsolidationRun(
            version="1.0",
            run_id=f"memory-consolidate-{uuid4().hex[:10]}",
            scope_key=scope_key,
            reason=reason,
            created_durative_count=created_durative_count,
            superseded_fact_count=sum(1 for fact in facts if fact.status == "superseded"),
            deduplicated_pointer_count=deduplicated_pointer_count,
            started_at=started_at,
            completed_at=utc_now(),
            synthesized_project_state_count=synthesized_project_state_count,
            contradiction_merge_count=contradiction_merge_count,
            contradiction_repair_count=0,
        )
        self.consolidation_runs[run.run_id] = run
        if self.repository is not None:
            self.repository.save_memory_consolidation_run(run)
        return run

    def rebuild_indexes(self, *, scope_key: str, reason: str) -> MemoryRebuildRun:
        started_at = utc_now()
        rebuilt_pointer_count = self._rebuild_missing_matrix_pointers(scope_key=scope_key)
        dashboard = self.dashboard(scope_key=scope_key)
        rebuilt_artifact_count = self._materialize_memory_index_artifacts(scope_key=scope_key, reason=reason)
        run = MemoryRebuildRun(
            version="1.0",
            run_id=f"memory-rebuild-{uuid4().hex[:10]}",
            scope_key=scope_key,
            reason=reason,
            rebuild_status="completed",
            rebuilt_pointer_count=rebuilt_pointer_count + len(self._list_matrix_pointers(scope_key=scope_key)),
            rebuilt_dashboard_item_count=len(dashboard),
            started_at=started_at,
            completed_at=utc_now(),
            rebuilt_artifact_count=rebuilt_artifact_count,
        )
        self.rebuild_runs[run.run_id] = run
        if self.repository is not None:
            self.repository.save_memory_rebuild_run(run)
        return run

    def selective_rebuild_scope(
        self,
        *,
        scope_key: str,
        reason: str,
        target_kinds: list[str],
    ) -> MemorySelectiveRebuildRun:
        started_at = utc_now()
        rebuilt_counts: dict[str, int] = {}
        if "matrix_pointer" in target_kinds:
            rebuilt_counts["matrix_pointer"] = self._rebuild_missing_matrix_pointers(scope_key=scope_key)
        if "dashboard_item" in target_kinds:
            rebuilt_counts["dashboard_item"] = len(self.dashboard(scope_key=scope_key))
        if "project_state_snapshot" in target_kinds:
            rebuilt_counts["project_state_snapshot"] = self._rebuild_project_state_snapshots(scope_key=scope_key)
        if "artifact_file" in target_kinds:
            rebuilt_counts["artifact_file"] = self._materialize_memory_index_artifacts(
                scope_key=scope_key,
                reason=reason,
                only_missing=True,
                include_local=True,
                include_shared=False,
            )
        if "shared_artifact_file" in target_kinds:
            rebuilt_counts["shared_artifact_file"] = self._materialize_memory_index_artifacts(
                scope_key=scope_key,
                reason=reason,
                only_missing=True,
                include_local=False,
                include_shared=True,
            )
        run = MemorySelectiveRebuildRun(
            version="1.0",
            run_id=f"memory-selective-rebuild-{uuid4().hex[:10]}",
            scope_key=scope_key,
            reason=reason,
            target_kinds=list(target_kinds),
            rebuilt_counts=rebuilt_counts,
            started_at=started_at,
            completed_at=utc_now(),
        )
        self.selective_rebuild_runs[run.run_id] = run
        if self.repository is not None:
            self.repository.save_memory_selective_rebuild_run(run)
        return run

    def register_artifact(
        self,
        *,
        scope_key: str,
        artifact_kind: str,
        path: str,
        source_run_id: str | None = None,
        status: str = "active",
        backend_kind: str = "local_fs",
        backend_ref: str | None = None,
    ) -> MemoryArtifactRecord:
        now = utc_now()
        existing = next(
            (
                record
                for record in self.list_memory_artifacts(scope_key=scope_key, artifact_kind=artifact_kind)
                if record.path == path and record.backend_kind == backend_kind
            ),
            None,
        )
        if existing is not None:
            existing.status = status
            existing.source_run_id = source_run_id
            existing.backend_ref = backend_ref
            existing.updated_at = now
            self.artifact_records[existing.artifact_id] = existing
            if self.repository is not None:
                self.repository.save_memory_artifact_record(existing)
            return existing
        record = MemoryArtifactRecord(
            version="1.0",
            artifact_id=f"memory-artifact-{uuid4().hex[:10]}",
            scope_key=scope_key,
            artifact_kind=artifact_kind,
            path=path,
            status=status,
            source_run_id=source_run_id,
            created_at=now,
            updated_at=now,
            backend_kind=backend_kind,
            backend_ref=backend_ref,
        )
        self.artifact_records[record.artifact_id] = record
        if self.repository is not None:
            self.repository.save_memory_artifact_record(record)
        return record

    def hard_purge_scope(
        self,
        *,
        scope_key: str,
        actor: str,
        reason: str,
        target_kinds: list[str] | None = None,
    ) -> MemoryHardPurgeRun:
        started_at = utc_now()
        requested = list(target_kinds or [
            "raw_episode",
            "semantic_fact",
            "matrix_pointer",
            "procedural_pattern",
            "durative_record",
            "explicit_record",
            "working_snapshot",
            "evidence_pack",
            "dashboard_item",
            "write_candidate",
            "admission_decision",
            "admission_feature_score",
            "governance_decision",
            "admission_learning_state",
            "lifecycle_trace",
            "timeline_segment",
            "cross_scope_timeline_segment",
            "project_state_snapshot",
            "artifact_file",
        ])
        purged_record_count = 0
        purged_record_ids: dict[str, list[str]] = {}
        kind_to_records = {
            "raw_episode": ("memory_raw_episode", self.raw_episodes, lambda: self.list_raw_episodes(scope_key=scope_key)),
            "semantic_fact": ("memory_temporal_semantic_fact", self.semantic_facts, lambda: self.list_temporal_semantic_facts(scope_key=scope_key)),
            "matrix_pointer": ("memory_matrix_pointer", self.matrix_pointers, lambda: self._list_matrix_pointers(scope_key=scope_key)),
            "procedural_pattern": ("memory_procedural_pattern", self.procedural_patterns, lambda: self._list_procedural_patterns(scope_key=scope_key)),
            "durative_record": ("memory_durative_record", self.durative_records, lambda: self.list_durative_memories(scope_key=scope_key)),
            "explicit_record": (
                "memory_explicit_record",
                self.explicit_records,
                lambda: self.repository.list_explicit_memory_records(scope_key=scope_key)
                if self.repository is not None
                else [record for record in self.explicit_records.values() if record.scope_key == scope_key],
            ),
            "working_snapshot": (
                "memory_working_snapshot",
                self.working_snapshots,
                lambda: self.repository.list_working_memory_snapshots(scope_key=scope_key)
                if self.repository is not None
                else [record for record in self.working_snapshots.values() if record.scope_key == scope_key],
            ),
            "evidence_pack": (
                "memory_evidence_pack",
                self.evidence_packs,
                lambda: self.repository.list_memory_evidence_packs(scope_key=scope_key)
                if self.repository is not None
                else [record for record in self.evidence_packs.values() if record.scope_key == scope_key],
            ),
            "dashboard_item": (
                "memory_dashboard_item",
                None,
                lambda: self.repository.list_memory_dashboard_items(scope_key=scope_key)
                if self.repository is not None
                else [],
            ),
            "write_candidate": (
                "memory_write_candidate",
                self.candidates,
                lambda: self.repository.list_memory_write_candidates(scope_key=scope_key)
                if self.repository is not None
                else [record for record in self.candidates.values() if record.scope_key == scope_key],
            ),
            "admission_decision": (
                "memory_admission_decision",
                self.admission_decisions,
                lambda: self.repository.list_memory_admission_decisions(scope_key=scope_key)
                if self.repository is not None
                else [record for record in self.admission_decisions.values() if record.scope_key == scope_key],
            ),
            "admission_feature_score": (
                "memory_admission_feature_score",
                self.admission_feature_scores,
                lambda: [
                    record
                    for record in (
                        self.repository.list_memory_admission_feature_scores()
                        if self.repository is not None
                        else self.admission_feature_scores.values()
                    )
                    if record.scope_key == scope_key
                ],
            ),
            "governance_decision": (
                "memory_governance_decision",
                self.governance_decisions,
                lambda: [
                    record
                    for record in (
                        self.repository.list_memory_governance_decisions()
                        if self.repository is not None
                        else self.governance_decisions.values()
                    )
                    if record.scope_key == scope_key
                ],
            ),
            "admission_learning_state": (
                "memory_admission_learning_state",
                self.admission_learning_states,
                lambda: [state]
                if (state := self._load_admission_learning_state(scope_key)) is not None
                else [],
            ),
            "lifecycle_trace": (
                "memory_lifecycle_trace",
                self.lifecycle_traces,
                lambda: self.list_memory_lifecycle_traces(scope_key=scope_key),
            ),
            "timeline_segment": ("memory_timeline_segment", self.timeline_segments, lambda: self.list_memory_timeline_segments(scope_key=scope_key)),
            "cross_scope_timeline_segment": (
                "memory_cross_scope_timeline_segment",
                self.cross_scope_timeline_segments,
                lambda: [
                    record
                    for record in (
                        self.repository.list_memory_cross_scope_timeline_segments()
                        if self.repository is not None
                        else self.cross_scope_timeline_segments.values()
                    )
                    if scope_key in record.scope_keys
                ],
            ),
            "project_state_snapshot": (
                "memory_project_state_snapshot",
                self.project_state_snapshots,
                lambda: self.repository.list_memory_project_state_snapshots(scope_key)
                if self.repository is not None
                else [record for record in self.project_state_snapshots.values() if record.scope_key == scope_key],
            ),
            "artifact_file": (
                "memory_artifact_record",
                self.artifact_records,
                lambda: self.list_memory_artifacts(scope_key=scope_key),
            ),
        }
        cascaded_matrix_pointer_ids: set[str] = set()
        if "semantic_fact" in requested and "matrix_pointer" not in requested:
            fact_ids = {fact.fact_id for fact in self.list_temporal_semantic_facts(scope_key=scope_key)}
            cascaded_matrix_pointer_ids = {
                pointer.pointer_id
                for pointer in self._list_matrix_pointers(scope_key=scope_key)
                if any(fact_id in fact_ids for fact_id in pointer.target_fact_ids)
            }
        for kind in requested:
            mapping = kind_to_records.get(kind)
            if mapping is None:
                continue
            record_type, cache, loader = mapping
            records = list(loader())
            record_ids = [
                getattr(record, field_name)
                for record in records
                for field_name in (
                    "episode_id",
                    "fact_id",
                    "pointer_id",
                    "pattern_id",
                    "durative_id",
                    "pack_id",
                    "item_id",
                    "decision_id",
                    "score_id",
                    "snapshot_id",
                    "learning_id",
                    "trace_id",
                    "record_id",
                    "segment_id",
                    "candidate_id",
                    "artifact_id",
                )
                if hasattr(record, field_name)
            ]
            if not record_ids:
                continue
            purged_record_count += len(record_ids)
            purged_record_ids[kind] = sorted(record_ids)
            for record in records:
                if cache is None:
                    continue
                if hasattr(record, "candidate_id") and (
                    cache is self.admission_decisions or cache is self.governance_decisions
                ):
                    cache.pop(record.candidate_id, None)
                    continue
                if hasattr(record, "learning_id") and cache is self.admission_learning_states:
                    cache.pop(record.scope_key, None)
                    continue
                if hasattr(record, "artifact_id") and cache is self.artifact_records:
                    self._delete_artifact_path(getattr(record, "path", ""))
                    cache.pop(record.artifact_id, None)
                    continue
                for field_name in (
                    "episode_id",
                    "fact_id",
                    "pointer_id",
                    "pattern_id",
                    "durative_id",
                    "pack_id",
                    "item_id",
                    "decision_id",
                    "score_id",
                    "snapshot_id",
                    "learning_id",
                    "trace_id",
                    "record_id",
                    "segment_id",
                    "candidate_id",
                    "artifact_id",
                ):
                    if hasattr(record, field_name):
                        cache.pop(getattr(record, field_name), None)
                        break
            if self.repository is not None:
                self.repository._delete_runtime_state_records(
                    record_type=record_type,
                    scope_key=None if kind == "governance_decision" else scope_key,
                    record_ids=record_ids,
                )
        if cascaded_matrix_pointer_ids:
            purged_record_count += len(cascaded_matrix_pointer_ids)
            purged_record_ids["matrix_pointer"] = sorted(
                set(purged_record_ids.get("matrix_pointer", [])) | cascaded_matrix_pointer_ids
            )
            for record_id in cascaded_matrix_pointer_ids:
                self.matrix_pointers.pop(record_id, None)
            if self.repository is not None:
                self.repository._delete_runtime_state_records(
                    record_type="memory_matrix_pointer",
                    scope_key=scope_key,
                    record_ids=sorted(cascaded_matrix_pointer_ids),
                )
            if "matrix_pointer" not in requested:
                requested.append("matrix_pointer")
        run = MemoryHardPurgeRun(
            version="1.0",
            run_id=f"memory-hard-purge-{uuid4().hex[:10]}",
            scope_key=scope_key,
            actor=actor,
            reason=reason,
            target_kinds=requested,
            purged_record_count=purged_record_count,
            started_at=started_at,
            completed_at=utc_now(),
        )
        self.hard_purge_runs[run.run_id] = run
        manifest = MemoryPurgeManifest(
            version="1.0",
            manifest_id=f"memory-purge-manifest-{uuid4().hex[:10]}",
            run_id=run.run_id,
            scope_key=scope_key,
            purge_mode="hard",
            target_kinds=requested,
            purged_record_ids=purged_record_ids,
            cascaded_record_ids={"matrix_pointer": sorted(cascaded_matrix_pointer_ids)} if cascaded_matrix_pointer_ids else {},
            preserved_summary={},
            created_at=utc_now(),
        )
        self.purge_manifests[manifest.manifest_id] = manifest
        if self.repository is not None:
            self.repository.save_memory_hard_purge_run(run)
            self.repository.save_memory_purge_manifest(manifest)
        return run

    def selective_purge_scope(
        self,
        *,
        scope_key: str,
        actor: str,
        reason: str,
        target_kinds: list[str],
    ) -> MemorySelectivePurgeRun:
        started_at = utc_now()
        kind_to_records = {
            "evidence_pack": (
                "memory_evidence_pack",
                self.evidence_packs,
                lambda: self.repository.list_memory_evidence_packs(scope_key=scope_key) if self.repository is not None else list(self.evidence_packs.values()),
            ),
            "dashboard_item": (
                "memory_dashboard_item",
                None,
                lambda: self.repository.list_memory_dashboard_items(scope_key=scope_key) if self.repository is not None else [],
            ),
            "write_candidate": (
                "memory_write_candidate",
                self.candidates,
                lambda: self.repository.list_memory_write_candidates(scope_key=scope_key) if self.repository is not None else list(self.candidates.values()),
            ),
            "admission_decision": (
                "memory_admission_decision",
                self.admission_decisions,
                lambda: self.repository.list_memory_admission_decisions(scope_key=scope_key) if self.repository is not None else list(self.admission_decisions.values()),
            ),
            "admission_feature_score": (
                "memory_admission_feature_score",
                self.admission_feature_scores,
                lambda: [
                    record
                    for record in (
                        self.repository.list_memory_admission_feature_scores()
                        if self.repository is not None
                        else self.admission_feature_scores.values()
                    )
                    if record.scope_key == scope_key
                ],
            ),
            "governance_decision": (
                "memory_governance_decision",
                self.governance_decisions,
                lambda: [record for record in self.repository.list_memory_governance_decisions() if record.scope_key == scope_key]
                if self.repository is not None
                else [record for record in self.governance_decisions.values() if record.scope_key == scope_key],
            ),
            "working_snapshot": (
                "memory_working_snapshot",
                self.working_snapshots,
                lambda: [snapshot]
                if (snapshot := self.latest_working_memory_snapshot(scope_key)) is not None
                else [],
            ),
            "explicit_record": (
                "memory_explicit_record",
                self.explicit_records,
                lambda: self.repository.list_explicit_memory_records(scope_key=scope_key) if self.repository is not None else [record for record in self.explicit_records.values() if record.scope_key == scope_key],
            ),
            "project_state_snapshot": (
                "memory_project_state_snapshot",
                self.project_state_snapshots,
                lambda: self.repository.list_memory_project_state_snapshots(scope_key)
                if self.repository is not None
                else [record for record in self.project_state_snapshots.values() if record.scope_key == scope_key],
            ),
            "artifact_file": (
                "memory_artifact_record",
                self.artifact_records,
                lambda: self.list_memory_artifacts(scope_key=scope_key),
            ),
        }
        purged_record_count = 0
        purged_record_ids: dict[str, list[str]] = {}
        preserved_record_count = len(self.list_temporal_semantic_facts(scope_key=scope_key)) + len(self.list_raw_episodes(scope_key=scope_key))
        for kind in target_kinds:
            mapping = kind_to_records.get(kind)
            if mapping is None:
                continue
            record_type, cache, loader = mapping
            records = list(loader())
            record_ids = [
                getattr(record, field_name)
                for record in records
                for field_name in (
                    "pack_id",
                    "item_id",
                    "decision_id",
                    "score_id",
                    "snapshot_id",
                    "record_id",
                    "candidate_id",
                    "artifact_id",
                )
                if hasattr(record, field_name)
            ]
            if not record_ids:
                continue
            purged_record_count += len(record_ids)
            purged_record_ids[kind] = sorted(record_ids)
            for record in records:
                if cache is None:
                    continue
                if hasattr(record, "candidate_id") and (
                    cache is self.admission_decisions or cache is self.governance_decisions
                ):
                    cache.pop(record.candidate_id, None)
                elif hasattr(record, "artifact_id") and cache is self.artifact_records:
                    self._delete_artifact_path(getattr(record, "path", ""))
                    cache.pop(record.artifact_id, None)
                else:
                    for field_name in ("pack_id", "item_id", "decision_id", "score_id", "snapshot_id", "record_id", "candidate_id", "artifact_id"):
                        if hasattr(record, field_name):
                            cache.pop(getattr(record, field_name), None)
                            break
            if self.repository is not None:
                self.repository._delete_runtime_state_records(
                    record_type=record_type,
                    scope_key=None if kind == "governance_decision" else scope_key,
                    record_ids=record_ids,
                )
        run = MemorySelectivePurgeRun(
            version="1.0",
            run_id=f"memory-selective-purge-{uuid4().hex[:10]}",
            scope_key=scope_key,
            actor=actor,
            reason=reason,
            target_kinds=list(target_kinds),
            purged_record_count=purged_record_count,
            preserved_record_count=preserved_record_count,
            started_at=started_at,
            completed_at=utc_now(),
        )
        self.selective_purge_runs[run.run_id] = run
        manifest = MemoryPurgeManifest(
            version="1.0",
            manifest_id=f"memory-purge-manifest-{uuid4().hex[:10]}",
            run_id=run.run_id,
            scope_key=scope_key,
            purge_mode="selective",
            target_kinds=list(target_kinds),
            purged_record_ids=purged_record_ids,
            cascaded_record_ids={},
            preserved_summary={
                "semantic_fact": len(self.list_temporal_semantic_facts(scope_key=scope_key)),
                "raw_episode": len(self.list_raw_episodes(scope_key=scope_key)),
            },
            created_at=utc_now(),
        )
        self.purge_manifests[manifest.manifest_id] = manifest
        if self.repository is not None:
            self.repository.save_memory_selective_purge_run(run)
            self.repository.save_memory_purge_manifest(manifest)
        return run

    def reconstruct_timeline(
        self,
        *,
        scope_key: str,
        subject: str | None = None,
        predicate: str | None = None,
    ) -> list[MemoryTimelineSegment]:
        facts = self.list_temporal_semantic_facts(scope_key=scope_key)
        if subject is not None:
            facts = [fact for fact in facts if fact.subject == subject]
        if predicate is not None:
            facts = [fact for fact in facts if fact.predicate == predicate]
        ordered = sorted(facts, key=lambda item: (item.valid_from or item.observed_at, item.observed_at))
        groups: list[list[TemporalSemanticFact]] = []
        for fact in ordered:
            if not groups or groups[-1][-1].object != fact.object:
                groups.append([fact])
            else:
                groups[-1].append(fact)

        stale_segments = [
            segment.segment_id
            for segment in self.list_memory_timeline_segments(scope_key=scope_key)
            if (subject is None or segment.subject == subject) and (predicate is None or segment.predicate == predicate)
        ]
        for segment_id in stale_segments:
            self.timeline_segments.pop(segment_id, None)
        if stale_segments and self.repository is not None:
            self.repository._delete_runtime_state_records(
                record_type="memory_timeline_segment",
                scope_key=scope_key,
                record_ids=stale_segments,
            )

        segments: list[MemoryTimelineSegment] = []
        previous_segment_id: str | None = None
        seen_states: dict[str, list[str]] = {}
        for index, items in enumerate(groups):
            start_at = items[0].valid_from or items[0].observed_at
            end_fact = items[-1]
            end_at = end_fact.valid_until or end_fact.observed_at
            next_object = groups[index + 1][0].object if index + 1 < len(groups) else None
            transition_kind = "terminal"
            if next_object is not None:
                transition_kind = "state_change" if next_object != items[-1].object else "continued"
            contradicted_fact_ids = [
                prior_id
                for prior_object, prior_ids in seen_states.items()
                if prior_object != items[-1].object
                for prior_id in prior_ids
            ]
            merge_reason = ""
            if items[-1].object in seen_states:
                merge_reason = "resumed_prior_state_after_contradiction" if contradicted_fact_ids else "resumed_prior_state"
            segment = MemoryTimelineSegment(
                version="1.0",
                segment_id=f"timeline-{uuid4().hex[:10]}",
                scope_key=scope_key,
                subject=items[0].subject,
                predicate=items[0].predicate,
                state_object=items[-1].object,
                start_at=start_at,
                end_at=end_at,
                supporting_fact_ids=[item.fact_id for item in items],
                previous_segment_id=previous_segment_id,
                next_segment_id=None,
                transition_kind=transition_kind,
                contradicted_fact_ids=contradicted_fact_ids,
                merge_reason=merge_reason,
                created_at=utc_now(),
            )
            if segments:
                segments[-1].next_segment_id = segment.segment_id
                if self.repository is not None:
                    self.repository.save_memory_timeline_segment(segments[-1])
            segments.append(segment)
            self.timeline_segments[segment.segment_id] = segment
            if self.repository is not None:
                self.repository.save_memory_timeline_segment(segment)
            previous_segment_id = segment.segment_id
            seen_states.setdefault(segment.state_object, []).extend(segment.supporting_fact_ids)
        return segments

    def reconstruct_cross_scope_timeline(
        self,
        *,
        scope_keys: list[str],
        subject: str,
        predicate: str,
    ) -> list[MemoryCrossScopeTimelineSegment]:
        facts: list[TemporalSemanticFact] = []
        for scope_key in scope_keys:
            facts.extend(
                fact
                for fact in self.list_temporal_semantic_facts(scope_key=scope_key)
                if fact.subject == subject and fact.predicate == predicate
            )
        ordered = sorted(facts, key=lambda item: (item.valid_from or item.observed_at, item.observed_at))
        groups: list[list[TemporalSemanticFact]] = []
        for fact in ordered:
            if not groups:
                groups.append([fact])
                continue
            previous = groups[-1][-1]
            if previous.object == fact.object and previous.scope_key == fact.scope_key:
                groups[-1].append(fact)
            else:
                groups.append([fact])

        stale = [
            segment.segment_id
            for segment in self.repository.list_memory_cross_scope_timeline_segments(scope_keys=scope_keys)
        ] if self.repository is not None else list(self.cross_scope_timeline_segments)
        for segment_id in stale:
            self.cross_scope_timeline_segments.pop(segment_id, None)
        if stale and self.repository is not None:
            self.repository._delete_runtime_state_records(
                record_type="memory_cross_scope_timeline_segment",
                record_ids=stale,
            )

        segments: list[MemoryCrossScopeTimelineSegment] = []
        previous_segment_id: str | None = None
        seen_states: dict[str, list[str]] = {}
        for index, items in enumerate(groups):
            next_items = groups[index + 1] if index + 1 < len(groups) else None
            transition_kind = "terminal"
            if next_items is not None:
                if next_items[0].scope_key != items[-1].scope_key:
                    transition_kind = "scope_change"
                elif next_items[0].object != items[-1].object:
                    transition_kind = "state_change"
                else:
                    transition_kind = "continued"
            contradicted_fact_ids = [
                prior_id
                for prior_object, prior_ids in seen_states.items()
                if prior_object != items[-1].object
                for prior_id in prior_ids
            ]
            merge_reason = ""
            if items[-1].object in seen_states:
                merge_reason = "resumed_prior_state_after_contradiction" if contradicted_fact_ids else "resumed_prior_state"
            segment = MemoryCrossScopeTimelineSegment(
                version="1.0",
                segment_id=f"cross-timeline-{uuid4().hex[:10]}",
                scope_keys=sorted({item.scope_key for item in items}),
                subject=subject,
                predicate=predicate,
                state_object=items[-1].object,
                start_at=items[0].valid_from or items[0].observed_at,
                end_at=items[-1].valid_until or items[-1].observed_at,
                supporting_fact_ids=[item.fact_id for item in items],
                previous_segment_id=previous_segment_id,
                next_segment_id=None,
                transition_kind=transition_kind,
                contradicted_fact_ids=contradicted_fact_ids,
                merge_reason=merge_reason,
                created_at=utc_now(),
            )
            if segments:
                segments[-1].next_segment_id = segment.segment_id
                if self.repository is not None:
                    self.repository.save_memory_cross_scope_timeline_segment(segments[-1])
            segments.append(segment)
            self.cross_scope_timeline_segments[segment.segment_id] = segment
            if self.repository is not None:
                self.repository.save_memory_cross_scope_timeline_segment(segment)
            previous_segment_id = segment.segment_id
            seen_states.setdefault(segment.state_object, []).extend(segment.supporting_fact_ids)
        return segments

    def reconstruct_project_state(
        self,
        *,
        scope_key: str,
        subject: str = "user",
    ) -> MemoryProjectStateSnapshot:
        timeline = [
            segment
            for segment in self.list_memory_timeline_segments(scope_key=scope_key)
            if segment.subject == subject
        ]
        if not timeline:
            timeline = self.reconstruct_timeline(scope_key=scope_key, subject=subject)
        active_facts = [
            fact
            for fact in self.list_temporal_semantic_facts(scope_key=scope_key)
            if fact.subject == subject and fact.status == "active"
        ]
        contradiction_count = sum(
            1 for segment in timeline if segment.merge_reason == "resumed_prior_state_after_contradiction"
        )
        active_states = [fact.object for fact in active_facts]
        summary = (
            f"{subject} active states: {', '.join(active_states)}"
            if active_states
            else f"{subject} has no active reconstructed state"
        )
        snapshot = MemoryProjectStateSnapshot(
            version="1.0",
            snapshot_id=f"project-state-{uuid4().hex[:10]}",
            scope_key=scope_key,
            subject=subject,
            summary=summary,
            active_states=active_states,
            contradiction_count=contradiction_count,
            timeline_segment_ids=[segment.segment_id for segment in timeline],
            supporting_fact_ids=[fact.fact_id for fact in active_facts],
            created_at=utc_now(),
        )
        self.project_state_snapshots[snapshot.snapshot_id] = snapshot
        if self.repository is not None:
            self.repository.save_memory_project_state_snapshot(snapshot)
        return snapshot

    def repair_cross_scope_contradictions(
        self,
        *,
        scope_keys: list[str],
        subject: str,
        predicate: str,
    ) -> list[MemoryContradictionRepairRecord]:
        facts: list[TemporalSemanticFact] = []
        for scope_key in scope_keys:
            facts.extend(
                fact
                for fact in self.list_temporal_semantic_facts(scope_key=scope_key)
                if fact.subject == subject and fact.predicate == predicate and fact.status == "active"
            )
        by_object: dict[str, list[TemporalSemanticFact]] = {}
        for fact in facts:
            by_object.setdefault(fact.object, []).append(fact)
        if len(by_object) <= 1:
            return []
        latest = max(facts, key=lambda item: item.valid_from or item.observed_at)
        rationale = (
            f"Detected conflicting active states across scopes; recommend preserving the most recent state "
            f"'{latest.object}' while keeping prior states as contradiction evidence."
        )
        record = MemoryContradictionRepairRecord(
            version="1.0",
            repair_id=f"memory-repair-{uuid4().hex[:10]}",
            scope_keys=sorted(scope_keys),
            subject=subject,
            predicate=predicate,
            conflicting_fact_ids=[fact.fact_id for fact in facts],
            recommended_state_object=latest.object,
            rationale=rationale,
            repair_status="recommended",
            created_at=utc_now(),
        )
        self.contradiction_repairs[record.repair_id] = record
        if self.repository is not None:
            self.repository.save_memory_contradiction_repair_record(record)
        return [record]

    def run_contradiction_repair_canary(
        self,
        *,
        scope_keys: list[str],
        subject: str,
        predicate: str,
    ) -> MemoryRepairCanaryRun:
        started_at = utc_now()
        learning_state = self._load_repair_learning_state(scope_keys)
        repairs = self.repair_cross_scope_contradictions(
            scope_keys=scope_keys,
            subject=subject,
            predicate=predicate,
        )
        assessments = [self._assess_repair_safety(item, learning_state=learning_state) for item in repairs]
        recommendation = "hold"
        if assessments:
            recommendation = assessments[0].recommendation
        run = MemoryRepairCanaryRun(
            version="1.0",
            run_id=f"memory-repair-canary-{uuid4().hex[:10]}",
            scope_keys=sorted(scope_keys),
            subject=subject,
            predicate=predicate,
            repair_ids=[item.repair_id for item in repairs],
            recommendation=recommendation,
            metrics={
                "repair_count": float(len(repairs)),
                "conflict_fact_count": float(sum(len(item.conflicting_fact_ids) for item in repairs)),
                "safety_score": 0.0 if not assessments else assessments[0].safety_score,
                "learned_risk_penalty": 0.0 if learning_state is None else learning_state.learned_risk_penalty,
                "effective_safety_score": 0.0 if not assessments else float(assessments[0].effective_safety_score or assessments[0].safety_score),
                "apply_ready_rate": 1.0 if recommendation == "apply" else 0.0,
            },
            started_at=started_at,
            completed_at=utc_now(),
            controller_version="v1" if learning_state is None else learning_state.controller_version,
        )
        self.repair_canary_runs[run.run_id] = run
        if self.repository is not None:
            self.repository.save_memory_repair_canary_run(run)
        return run

    def apply_contradiction_repair(
        self,
        *,
        repair_id: str,
        actor: str,
        reason: str,
    ) -> MemoryRepairActionRun:
        repair = self._get_contradiction_repair(repair_id)
        assessment = self._latest_repair_safety_assessment(repair.scope_keys, repair_id=repair_id)
        if assessment is not None and assessment.recommendation != "apply":
            raise ValueError("repair safety assessment does not allow apply")
        facts = self._repair_facts(repair)
        if not facts:
            raise KeyError(repair_id)
        latest = max(facts, key=lambda item: item.valid_from or item.observed_at)
        previous_statuses = {fact.fact_id: fact.status for fact in facts}
        updated_statuses: dict[str, str] = {}
        started_at = utc_now()
        for fact in facts:
            fact.status = "active" if fact.fact_id == latest.fact_id else "superseded"
            updated_statuses[fact.fact_id] = fact.status
            if self.repository is not None:
                self.repository.save_temporal_semantic_fact(fact)
        repair.repair_status = "applied"
        if self.repository is not None:
            self.repository.save_memory_contradiction_repair_record(repair)
        for scope_key in repair.scope_keys:
            for subject in sorted({fact.subject for fact in facts if fact.scope_key == scope_key}):
                self.reconstruct_project_state(scope_key=scope_key, subject=subject)
        run = MemoryRepairActionRun(
            version="1.0",
            run_id=f"memory-repair-action-{uuid4().hex[:10]}",
            repair_id=repair_id,
            action="apply",
            actor=actor,
            reason=reason,
            previous_statuses=previous_statuses,
            updated_statuses=updated_statuses,
            started_at=started_at,
            completed_at=utc_now(),
        )
        self.repair_action_runs[run.run_id] = run
        if self.repository is not None:
            self.repository.save_memory_repair_action_run(run)
        analytics = MemoryRepairRolloutAnalyticsRecord(
            version="1.0",
            analytics_id=f"memory-repair-analytics-{uuid4().hex[:10]}",
            repair_id=repair_id,
            action="apply",
            affected_fact_ids=[fact.fact_id for fact in facts],
            active_state_count_before=sum(1 for status in previous_statuses.values() if status == "active"),
            active_state_count_after=sum(1 for status in updated_statuses.values() if status == "active"),
            rollback_restored_count=0,
            safety_score=0.0 if assessment is None else assessment.safety_score,
            created_at=utc_now(),
        )
        self.repair_rollout_analytics[analytics.analytics_id] = analytics
        if self.repository is not None:
            self.repository.save_memory_repair_rollout_analytics_record(analytics)
        return run

    def rollback_contradiction_repair(
        self,
        *,
        repair_id: str,
        actor: str,
        reason: str,
    ) -> MemoryRepairActionRun:
        repair = self._get_contradiction_repair(repair_id)
        prior_apply = next(
            (run for run in self.list_repair_action_runs(repair_id=repair_id) if run.action == "apply"),
            None,
        )
        if prior_apply is None:
            raise KeyError(repair_id)
        started_at = utc_now()
        updated_statuses: dict[str, str] = {}
        for fact in self._repair_facts(repair):
            restored = prior_apply.previous_statuses.get(fact.fact_id, fact.status)
            fact.status = restored
            updated_statuses[fact.fact_id] = restored
            if self.repository is not None:
                self.repository.save_temporal_semantic_fact(fact)
        repair.repair_status = "rolled_back"
        if self.repository is not None:
            self.repository.save_memory_contradiction_repair_record(repair)
        run = MemoryRepairActionRun(
            version="1.0",
            run_id=f"memory-repair-action-{uuid4().hex[:10]}",
            repair_id=repair_id,
            action="rollback",
            actor=actor,
            reason=reason,
            previous_statuses=dict(prior_apply.updated_statuses),
            updated_statuses=updated_statuses,
            started_at=started_at,
            completed_at=utc_now(),
        )
        self.repair_action_runs[run.run_id] = run
        if self.repository is not None:
            self.repository.save_memory_repair_action_run(run)
        assessment = self._latest_repair_safety_assessment(repair.scope_keys, repair_id=repair_id)
        analytics = MemoryRepairRolloutAnalyticsRecord(
            version="1.0",
            analytics_id=f"memory-repair-analytics-{uuid4().hex[:10]}",
            repair_id=repair_id,
            action="rollback",
            affected_fact_ids=[fact.fact_id for fact in self._repair_facts(repair)],
            active_state_count_before=sum(1 for status in prior_apply.updated_statuses.values() if status == "active"),
            active_state_count_after=sum(1 for status in updated_statuses.values() if status == "active"),
            rollback_restored_count=sum(
                1 for fact_id, status in updated_statuses.items() if prior_apply.previous_statuses.get(fact_id) == status
            ),
            safety_score=0.0 if assessment is None else assessment.safety_score,
            created_at=utc_now(),
        )
        self.repair_rollout_analytics[analytics.analytics_id] = analytics
        if self.repository is not None:
            self.repository.save_memory_repair_rollout_analytics_record(analytics)
        return run

    def recommend_admission_policy_promotion(self, *, scope_key: str) -> MemoryAdmissionPromotionRecommendation:
        canaries = self.list_admission_canary_runs(scope_key=scope_key)
        learning_state = self._load_admission_learning_state(scope_key)
        latest = None if not canaries else canaries[0]
        confidence = 0.0
        recommendation = "hold"
        rationale = "No admission canary evidence yet."
        if latest is not None:
            confidence = min(
                1.0,
                float(latest.metrics.get("high_risk_override_count", 0.0)) * 0.4
                + float(latest.metrics.get("promoted_quarantine_count", 0.0)) * 0.1
                + (0.2 if learning_state is not None else 0.0),
            )
            if latest.recommendation == "promote" and confidence >= 0.5:
                recommendation = "promote"
                rationale = "Admission canary found additional high-risk overrides and the learned controller is stable enough for governed promotion."
            elif latest.recommendation == "rollback":
                recommendation = "rollback"
                rationale = "Admission canary reduced quarantine sensitivity and should not be promoted."
            else:
                rationale = "Admission canary evidence is not strong enough for promotion."
        record = MemoryAdmissionPromotionRecommendation(
            version="1.0",
            recommendation_id=f"memory-admission-promotion-{uuid4().hex[:10]}",
            scope_key=scope_key,
            source_canary_run_ids=[] if latest is None else [latest.run_id],
            controller_version="v2" if learning_state is not None else "v1",
            recommendation=recommendation,
            confidence=confidence,
            rationale=rationale,
            created_at=utc_now(),
        )
        self.admission_promotion_recommendations[record.recommendation_id] = record
        if self.repository is not None:
            self.repository.save_memory_admission_promotion_recommendation(record)
        return record

    def schedule_memory_operations_loop(
        self,
        *,
        scope_key: str,
        cadence_hours: int,
        actor: str,
        start_at: datetime | None = None,
    ) -> MemoryOperationsLoopSchedule:
        now = utc_now()
        existing = next(iter(self.list_memory_operations_loop_schedules(scope_key=scope_key)), None)
        if existing is not None:
            existing.cadence_hours = cadence_hours
            existing.actor = actor
            existing.enabled = True
            existing.next_run_at = start_at or existing.next_run_at
            existing.updated_at = now
            if self.repository is not None:
                self.repository.save_memory_operations_loop_schedule(existing)
            return existing
        record = MemoryOperationsLoopSchedule(
            version="1.0",
            schedule_id=f"memory-ops-schedule-{uuid4().hex[:10]}",
            scope_key=scope_key,
            cadence_hours=cadence_hours,
            enabled=True,
            actor=actor,
            next_run_at=start_at or now,
            last_run_at=None,
            created_at=now,
            updated_at=now,
        )
        self.operations_loop_schedules[record.schedule_id] = record
        if self.repository is not None:
            self.repository.save_memory_operations_loop_schedule(record)
        return record

    def run_due_memory_operations(
        self,
        *,
        at_time: datetime | None = None,
        interrupt_after_phase: str | None = None,
    ) -> list[MemoryOperationsLoopRun]:
        now = utc_now() if at_time is None else at_time
        runs: list[MemoryOperationsLoopRun] = []
        for schedule in self.list_memory_operations_loop_schedules():
            if not schedule.enabled or schedule.next_run_at > now:
                continue
            run = self.run_memory_operations_loop(
                scope_key=schedule.scope_key,
                reason="scheduled memory operations loop",
                interrupt_after_phase=interrupt_after_phase,
            )
            schedule.last_run_at = now
            schedule.next_run_at = now.replace() if schedule.cadence_hours == 0 else now + timedelta(hours=schedule.cadence_hours)
            schedule.updated_at = utc_now()
            self.operations_loop_schedules[schedule.schedule_id] = schedule
            if self.repository is not None:
                self.repository.save_memory_operations_loop_schedule(schedule)
            runs.append(run)
        return runs

    def run_memory_operations_loop(
        self,
        *,
        scope_key: str,
        reason: str,
        interrupt_after_phase: str | None = None,
    ) -> MemoryOperationsLoopRun:
        started_at = utc_now()
        consolidation = self.run_sleep_consolidation(scope_key=scope_key, reason=reason)
        if interrupt_after_phase == "consolidation":
            run = MemoryOperationsLoopRun(
                version="1.0",
                run_id=f"memory-ops-loop-{uuid4().hex[:10]}",
                scope_key=scope_key,
                reason=reason,
                consolidation_run_id=consolidation.run_id,
                selective_rebuild_run_id=None,
                status="interrupted",
                synthesized_project_state_count=consolidation.synthesized_project_state_count,
                rebuilt_artifact_count=0,
                contradiction_repair_count=consolidation.contradiction_repair_count,
                started_at=started_at,
                completed_at=utc_now(),
                interrupted_phase="consolidation",
            )
            self.operations_loop_runs[run.run_id] = run
            recovery = MemoryOperationsLoopRecoveryRecord(
                version="1.0",
                recovery_id=f"memory-ops-recovery-{uuid4().hex[:10]}",
                loop_run_id=run.run_id,
                scope_key=scope_key,
                interrupted_phase="consolidation",
                status="pending",
                actor="system",
                created_at=utc_now(),
                recovered_at=None,
            )
            self.operations_loop_recoveries[recovery.recovery_id] = recovery
            if self.repository is not None:
                self.repository.save_memory_operations_loop_run(run)
                self.repository.save_memory_operations_loop_recovery_record(recovery)
            return run
        selective_rebuild = self.selective_rebuild_scope(
            scope_key=scope_key,
            reason=reason,
            target_kinds=["matrix_pointer", "dashboard_item", "project_state_snapshot", "artifact_file", "shared_artifact_file"],
        )
        run = MemoryOperationsLoopRun(
            version="1.0",
            run_id=f"memory-ops-loop-{uuid4().hex[:10]}",
            scope_key=scope_key,
            reason=reason,
            consolidation_run_id=consolidation.run_id,
            selective_rebuild_run_id=selective_rebuild.run_id,
            status="completed",
            synthesized_project_state_count=consolidation.synthesized_project_state_count,
            rebuilt_artifact_count=selective_rebuild.rebuilt_counts.get("artifact_file", 0) + selective_rebuild.rebuilt_counts.get("shared_artifact_file", 0),
            contradiction_repair_count=consolidation.contradiction_repair_count,
            started_at=started_at,
            completed_at=utc_now(),
        )
        self.operations_loop_runs[run.run_id] = run
        if self.repository is not None:
            self.repository.save_memory_operations_loop_run(run)
        return run

    def resume_memory_operations_loop(
        self,
        *,
        loop_run_id: str,
        actor: str,
        reason: str,
    ) -> MemoryOperationsLoopRun:
        prior_run = self._get_operations_loop_run(loop_run_id)
        if prior_run.status != "interrupted":
            return prior_run
        selective_rebuild = self.selective_rebuild_scope(
            scope_key=prior_run.scope_key,
            reason=reason,
            target_kinds=["matrix_pointer", "dashboard_item", "project_state_snapshot", "artifact_file", "shared_artifact_file"],
        )
        resumed_run = MemoryOperationsLoopRun(
            version="1.0",
            run_id=f"memory-ops-loop-{uuid4().hex[:10]}",
            scope_key=prior_run.scope_key,
            reason=reason,
            consolidation_run_id=prior_run.consolidation_run_id,
            selective_rebuild_run_id=selective_rebuild.run_id,
            status="completed",
            synthesized_project_state_count=prior_run.synthesized_project_state_count,
            rebuilt_artifact_count=selective_rebuild.rebuilt_counts.get("artifact_file", 0) + selective_rebuild.rebuilt_counts.get("shared_artifact_file", 0),
            contradiction_repair_count=prior_run.contradiction_repair_count,
            started_at=prior_run.started_at,
            completed_at=utc_now(),
            interrupted_phase=None,
            resumed_from_run_id=loop_run_id,
        )
        self.operations_loop_runs[resumed_run.run_id] = resumed_run
        recovery = next(
            (item for item in self.list_memory_operations_loop_recoveries(scope_key=prior_run.scope_key) if item.loop_run_id == loop_run_id and item.status == "pending"),
            None,
        )
        if recovery is not None:
            recovery.status = "recovered"
            recovery.recovered_at = utc_now()
            recovery.actor = actor
            self.operations_loop_recoveries[recovery.recovery_id] = recovery
            if self.repository is not None:
                self.repository.save_memory_operations_loop_recovery_record(recovery)
        if self.repository is not None:
            self.repository.save_memory_operations_loop_run(resumed_run)
        return resumed_run

    def run_maintenance_recommendation_canary(self, *, scope_key: str) -> MemoryMaintenanceCanaryRun:
        started_at = utc_now()
        learning_state = self._load_maintenance_learning_state(scope_key)
        if learning_state is None:
            learning_state = self.train_maintenance_controller(scope_key=scope_key)
        baseline = self._build_maintenance_recommendation(scope_key=scope_key, learning_state=None)
        learned = self._build_maintenance_recommendation(scope_key=scope_key, learning_state=learning_state)
        changed = len(set(learned.actions) ^ set(baseline.actions))
        recommendation = "promote" if learning_state.examples_seen >= 1 else "hold"
        run = MemoryMaintenanceCanaryRun(
            version="1.0",
            run_id=f"maintenance-canary-{uuid4().hex[:10]}",
            scope_key=scope_key,
            controller_version=learning_state.controller_version,
            baseline_actions=list(baseline.actions),
            learned_actions=list(learned.actions),
            recommendation=recommendation,
            metrics={
                "changed_action_count": float(changed),
                "baseline_action_count": float(len(baseline.actions)),
                "learned_action_count": float(len(learned.actions)),
            },
            started_at=started_at,
            completed_at=utc_now(),
        )
        self.maintenance_canary_runs[run.run_id] = run
        controller_state = self._load_maintenance_controller_state(scope_key)
        controller_state.last_canary_run_id = run.run_id
        controller_state.updated_at = utc_now()
        self.maintenance_controller_states[scope_key] = controller_state
        if self.repository is not None:
            self.repository.save_memory_maintenance_canary_run(run)
            self.repository.save_memory_maintenance_controller_state(controller_state)
        return run

    def recommend_maintenance_policy_promotion(self, *, scope_key: str) -> MemoryMaintenancePromotionRecommendation:
        canaries = self.list_memory_maintenance_canary_runs(scope_key=scope_key)
        latest = None if not canaries else canaries[0]
        recommendation = "hold"
        confidence = 0.0
        rationale = "No maintenance canary evidence yet."
        controller_version = "v2"
        if latest is not None:
            recommendation = "promote" if latest.recommendation == "promote" else "hold"
            confidence = 0.65 if recommendation == "promote" else min(1.0, 0.4 + latest.metrics.get("learned_action_count", 0.0) * 0.1)
            rationale = "Maintenance canary suggests the learned controller is ready for broader use."
            controller_version = latest.controller_version
        record = MemoryMaintenancePromotionRecommendation(
            version="1.0",
            recommendation_id=f"maintenance-promotion-{uuid4().hex[:10]}",
            scope_key=scope_key,
            source_canary_run_ids=[] if latest is None else [latest.run_id],
            controller_version=controller_version,
            recommendation=recommendation,
            confidence=confidence,
            rationale=rationale,
            created_at=utc_now(),
        )
        self.maintenance_promotion_recommendations[record.recommendation_id] = record
        controller_state = self._load_maintenance_controller_state(scope_key)
        controller_state.last_promotion_recommendation_id = record.recommendation_id
        controller_state.updated_at = utc_now()
        self.maintenance_controller_states[scope_key] = controller_state
        if self.repository is not None:
            self.repository.save_memory_maintenance_promotion_recommendation(record)
            self.repository.save_memory_maintenance_controller_state(controller_state)
        return record

    def maintenance_controller_state(self, *, scope_key: str) -> MemoryMaintenanceControllerState:
        state = self._load_maintenance_controller_state(scope_key)
        return MemoryMaintenanceControllerState.from_dict(state.to_dict())

    def apply_maintenance_promotion(
        self,
        *,
        scope_key: str,
        recommendation_id: str,
        actor: str,
        reason: str,
    ) -> MemoryMaintenanceRolloutRecord:
        recommendation = next(
            item
            for item in self.list_memory_maintenance_promotions(scope_key=scope_key)
            if item.recommendation_id == recommendation_id
        )
        controller_state = self._load_maintenance_controller_state(scope_key)
        rollout = MemoryMaintenanceRolloutRecord(
            version="1.0",
            rollout_id=f"maintenance-rollout-{uuid4().hex[:10]}",
            scope_key=scope_key,
            recommendation_id=recommendation_id,
            action="apply",
            from_controller_version=controller_state.active_controller_version,
            to_controller_version=recommendation.controller_version,
            actor=actor,
            reason=reason,
            created_at=utc_now(),
            related_rollout_id=None,
            status="completed",
        )
        self.maintenance_rollouts[rollout.rollout_id] = rollout
        controller_state.active_controller_version = rollout.to_controller_version
        controller_state.last_rollout_id = rollout.rollout_id
        controller_state.status = "active"
        controller_state.updated_at = utc_now()
        self.maintenance_controller_states[scope_key] = controller_state
        if self.repository is not None:
            self.repository.save_memory_maintenance_rollout_record(rollout)
            self.repository.save_memory_maintenance_controller_state(controller_state)
        return rollout

    def rollback_maintenance_rollout(
        self,
        *,
        rollout_id: str,
        actor: str,
        reason: str,
    ) -> MemoryMaintenanceRolloutRecord:
        original = next(item for item in self.list_memory_maintenance_rollouts() if item.rollout_id == rollout_id)
        controller_state = self._load_maintenance_controller_state(original.scope_key)
        rollback = MemoryMaintenanceRolloutRecord(
            version="1.0",
            rollout_id=f"maintenance-rollout-{uuid4().hex[:10]}",
            scope_key=original.scope_key,
            recommendation_id=original.recommendation_id,
            action="rollback",
            from_controller_version=controller_state.active_controller_version,
            to_controller_version=original.from_controller_version,
            actor=actor,
            reason=reason,
            created_at=utc_now(),
            related_rollout_id=original.rollout_id,
            status="completed",
        )
        self.maintenance_rollouts[rollback.rollout_id] = rollback
        controller_state.active_controller_version = rollback.to_controller_version
        controller_state.last_rollout_id = rollback.rollout_id
        controller_state.status = "rolled_back"
        controller_state.updated_at = utc_now()
        self.maintenance_controller_states[original.scope_key] = controller_state
        if self.repository is not None:
            self.repository.save_memory_maintenance_rollout_record(rollback)
            self.repository.save_memory_maintenance_controller_state(controller_state)
        return rollback

    def run_maintenance_worker_cycle(
        self,
        *,
        worker_id: str,
        at_time: datetime | None = None,
        interrupt_after_phase: str | None = None,
        lease_seconds: int = 300,
    ) -> list[MemoryMaintenanceRun]:
        self.heartbeat_maintenance_worker(worker_id=worker_id, current_mode="running")
        runs = self.run_due_background_maintenance(
            at_time=at_time,
            interrupt_after_phase=interrupt_after_phase,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        current_mode = "running" if runs else "idle"
        self.heartbeat_maintenance_worker(worker_id=worker_id, current_mode=current_mode)
        return runs

    def resolve_maintenance_incident(
        self,
        *,
        incident_id: str,
        actor: str,
        resolution: str,
    ) -> MemoryMaintenanceIncidentRecord:
        incident = next(item for item in self.list_memory_maintenance_incidents() if item.incident_id == incident_id)
        incident.status = "resolved"
        incident.resolved_at = utc_now()
        incident.summary = f"{incident.summary} Resolved by {actor}: {resolution}"
        self.maintenance_incidents[incident.incident_id] = incident
        if self.repository is not None:
            self.repository.save_memory_maintenance_incident_record(incident)
        return incident

    def schedule_background_maintenance(
        self,
        *,
        scope_key: str,
        cadence_hours: int,
        actor: str,
        start_at: datetime | None = None,
    ) -> MemoryMaintenanceSchedule:
        now = utc_now()
        record = MemoryMaintenanceSchedule(
            version="1.0",
            schedule_id=f"maintenance-schedule-{uuid4().hex[:10]}",
            scope_key=scope_key,
            cadence_hours=cadence_hours,
            enabled=True,
            actor=actor,
            next_run_at=now if start_at is None else start_at,
            last_run_at=None,
            created_at=now,
            updated_at=now,
            claimed_by_worker_id=None,
            lease_expires_at=None,
        )
        self.maintenance_schedules[record.schedule_id] = record
        if self.repository is not None:
            self.repository.save_memory_maintenance_schedule(record)
        return record

    def run_due_background_maintenance(
        self,
        *,
        at_time: datetime | None = None,
        interrupt_after_phase: str | None = None,
        worker_id: str | None = None,
        lease_seconds: int = 300,
    ) -> list[MemoryMaintenanceRun]:
        now = utc_now() if at_time is None else at_time
        runs: list[MemoryMaintenanceRun] = []
        for schedule in self.list_memory_maintenance_schedules():
            if not schedule.enabled or schedule.next_run_at > now:
                continue
            if worker_id is not None:
                claimed_by_other = (
                    schedule.claimed_by_worker_id is not None
                    and schedule.claimed_by_worker_id != worker_id
                    and schedule.lease_expires_at is not None
                    and schedule.lease_expires_at > now
                )
                if claimed_by_other:
                    continue
                schedule.claimed_by_worker_id = worker_id
                schedule.lease_expires_at = now + timedelta(seconds=lease_seconds)
                schedule.updated_at = utc_now()
                self.maintenance_schedules[schedule.schedule_id] = schedule
                worker = self._get_maintenance_worker(worker_id)
                worker.current_mode = "running"
                worker.last_heartbeat_at = utc_now()
                worker.claimed_schedule_ids = sorted(set(worker.claimed_schedule_ids + [schedule.schedule_id]))
                self.maintenance_workers[worker.worker_id] = worker
                if self.repository is not None:
                    self.repository.save_memory_maintenance_schedule(schedule)
                    self.repository.save_memory_maintenance_worker_record(worker)
            run = self.run_background_memory_maintenance(
                scope_keys=[schedule.scope_key],
                actor=schedule.actor,
                at_time=now,
                interrupt_after_phase=interrupt_after_phase,
                schedule_id=schedule.schedule_id,
                claimed_by_worker_id=worker_id,
            )[0]
            if run.status == "completed":
                schedule.last_run_at = now
                schedule.next_run_at = now + timedelta(hours=schedule.cadence_hours)
                schedule.claimed_by_worker_id = None
                schedule.lease_expires_at = None
                schedule.updated_at = utc_now()
                self.maintenance_schedules[schedule.schedule_id] = schedule
                if worker_id is not None:
                    worker = self._get_maintenance_worker(worker_id)
                    worker.current_mode = "idle"
                    worker.active_run_ids = [item for item in worker.active_run_ids if item != run.run_id]
                    worker.claimed_schedule_ids = [item for item in worker.claimed_schedule_ids if item != schedule.schedule_id]
                    worker.last_heartbeat_at = utc_now()
                    self.maintenance_workers[worker.worker_id] = worker
                    if self.repository is not None:
                        self.repository.save_memory_maintenance_worker_record(worker)
                if self.repository is not None:
                    self.repository.save_memory_maintenance_schedule(schedule)
            runs.append(run)
        return runs

    def resume_background_maintenance(
        self,
        *,
        run_id: str,
        actor: str,
        reason: str,
        worker_id: str | None = None,
    ) -> MemoryMaintenanceRun:
        prior = next(item for item in self.list_memory_maintenance_runs() if item.run_id == run_id)
        if prior.status != "interrupted":
            return prior
        resumed = self.run_background_memory_maintenance(
            scope_keys=[prior.scope_key],
            actor=actor,
            schedule_id=prior.schedule_id,
            claimed_by_worker_id=worker_id or prior.claimed_by_worker_id,
        )[0]
        resumed.resumed_from_run_id = run_id
        resumed.schedule_id = prior.schedule_id
        resumed.claimed_by_worker_id = worker_id or prior.claimed_by_worker_id
        self.maintenance_runs[resumed.run_id] = resumed
        recovery = next(
            (item for item in self.list_memory_maintenance_recoveries(scope_key=prior.scope_key) if item.maintenance_run_id == run_id and item.status == "pending"),
            None,
        )
        if recovery is not None:
            recovery.status = "recovered"
            recovery.recovered_at = utc_now()
            recovery.actor = actor
            self.maintenance_recoveries[recovery.recovery_id] = recovery
            if self.repository is not None:
                self.repository.save_memory_maintenance_recovery_record(recovery)
        if prior.schedule_id is not None:
            schedules = [item for item in self.list_memory_maintenance_schedules(scope_key=prior.scope_key) if item.schedule_id == prior.schedule_id]
            if schedules:
                schedule = schedules[0]
                schedule.last_run_at = utc_now()
                schedule.next_run_at = schedule.last_run_at + timedelta(hours=schedule.cadence_hours)
                schedule.claimed_by_worker_id = None
                schedule.lease_expires_at = None
                schedule.updated_at = utc_now()
                self.maintenance_schedules[schedule.schedule_id] = schedule
                if self.repository is not None:
                    self.repository.save_memory_maintenance_schedule(schedule)
        if worker_id is not None:
            worker = self._get_maintenance_worker(worker_id)
            worker.current_mode = "idle"
            worker.active_run_ids = [item for item in worker.active_run_ids if item not in {prior.run_id, resumed.run_id}]
            if prior.schedule_id is not None:
                worker.claimed_schedule_ids = [item for item in worker.claimed_schedule_ids if item != prior.schedule_id]
            worker.last_heartbeat_at = utc_now()
            self.maintenance_workers[worker.worker_id] = worker
            if self.repository is not None:
                self.repository.save_memory_maintenance_worker_record(worker)
        if self.repository is not None:
            self.repository.save_memory_maintenance_run(resumed)
        return resumed

    def run_background_memory_maintenance(
        self,
        *,
        scope_keys: list[str] | None = None,
        actor: str,
        at_time: datetime | None = None,
        interrupt_after_phase: str | None = None,
        schedule_id: str | None = None,
        claimed_by_worker_id: str | None = None,
    ) -> list[MemoryMaintenanceRun]:
        now = utc_now() if at_time is None else at_time
        if scope_keys is None:
            derived: set[str] = set()
            derived.update(item.scope_key for item in self.list_memory_operations_loop_schedules() if item.enabled and item.next_run_at <= now)
            derived.update(item.scope_key for item in self.list_memory_operations_loop_recoveries() if item.status == "pending")
            derived.update(item.scope_key for item in self.list_memory_artifacts())
            scope_keys = sorted(derived)
        runs: list[MemoryMaintenanceRun] = []
        for scope_key in scope_keys:
            recommendation = self.recommend_memory_maintenance(scope_key=scope_key)
            started_at = utc_now()
            if interrupt_after_phase == "recommendation":
                run = MemoryMaintenanceRun(
                    version="1.0",
                    run_id=f"memory-maintenance-run-{uuid4().hex[:10]}",
                    scope_key=scope_key,
                    recommendation_id=recommendation.recommendation_id,
                    actor=actor,
                    executed_actions=[],
                    resumed_loop_run_ids=[],
                    repair_canary_run_ids=[],
                    repair_action_run_ids=[],
                    artifact_backend_repair_run_ids=[],
                    started_at=started_at,
                    completed_at=utc_now(),
                    status="interrupted",
                    interrupted_phase="recommendation",
                    schedule_id=schedule_id,
                    claimed_by_worker_id=claimed_by_worker_id,
                )
                self.maintenance_runs[run.run_id] = run
                if claimed_by_worker_id is not None:
                    worker = self._get_maintenance_worker(claimed_by_worker_id)
                    worker.active_run_ids = sorted(set(worker.active_run_ids + [run.run_id]))
                    self.maintenance_workers[worker.worker_id] = worker
                    if self.repository is not None:
                        self.repository.save_memory_maintenance_worker_record(worker)
                recovery = MemoryMaintenanceRecoveryRecord(
                    version="1.0",
                    recovery_id=f"maintenance-recovery-{uuid4().hex[:10]}",
                    maintenance_run_id=run.run_id,
                    scope_key=scope_key,
                    interrupted_phase="recommendation",
                    status="pending",
                    actor=actor,
                    created_at=utc_now(),
                    recovered_at=None,
                    schedule_id=schedule_id,
                )
                self.maintenance_recoveries[recovery.recovery_id] = recovery
                if self.repository is not None:
                    self.repository.save_memory_maintenance_run(run)
                    self.repository.save_memory_maintenance_recovery_record(recovery)
                runs.append(run)
                continue

            executed_actions: list[str] = []
            resumed_loop_run_ids: list[str] = []
            repair_canary_run_ids: list[str] = []
            repair_action_run_ids: list[str] = []
            artifact_backend_repair_run_ids: list[str] = []
            fallback_action_count = 0

            for recovery in [
                item
                for item in self.list_memory_operations_loop_recoveries(scope_key=scope_key)
                if item.status == "pending"
            ]:
                resumed = self.resume_memory_operations_loop(
                    loop_run_id=recovery.loop_run_id,
                    actor=actor,
                    reason="background maintenance resumed interrupted loop",
                )
                resumed_loop_run_ids.append(resumed.run_id)
            if resumed_loop_run_ids:
                executed_actions.append("resume_interrupted_loop")

            due_runs = [item for item in self.run_due_memory_operations(at_time=now) if item.scope_key == scope_key]
            if due_runs:
                executed_actions.append("run_due_schedule")

            if "repair_shared_artifacts" in recommendation.actions:
                repair = self.repair_artifact_backend(
                    scope_key=scope_key,
                    backend_kind="shared_fs",
                    actor=actor,
                    reason="background maintenance repaired shared artifact backend",
                )
                artifact_backend_repair_run_ids.append(repair.run_id)
                executed_actions.append("repair_shared_artifacts")
                for incident in [
                    item
                    for item in self.list_memory_maintenance_incidents(scope_key=scope_key, status="active")
                    if item.incident_kind == "shared_backend_unavailable"
                ]:
                    self.resolve_maintenance_incident(
                        incident_id=incident.incident_id,
                        actor=actor,
                        resolution="shared artifact backend repaired and available again",
                    )

            if "reconcile_shared_artifacts" in recommendation.actions:
                self._materialize_memory_index_artifacts(
                    scope_key=scope_key,
                    reason="background maintenance reconciled shared artifact drift",
                    only_missing=False,
                    include_local=False,
                    include_shared=True,
                )
                self._mark_artifact_drift_reconciled(scope_key=scope_key)
                executed_actions.append("reconcile_shared_artifacts")
                for incident in [
                    item
                    for item in self.list_memory_maintenance_incidents(scope_key=scope_key, status="active")
                    if item.incident_kind == "shared_backend_unavailable"
                ]:
                    self.resolve_maintenance_incident(
                        incident_id=incident.incident_id,
                        actor=actor,
                        resolution="shared artifact backend reconciled and healthy again",
                    )

            if "fallback_local_artifacts" in recommendation.actions:
                self._materialize_memory_index_artifacts(
                    scope_key=scope_key,
                    reason="background maintenance local fallback rebuild",
                    only_missing=False,
                    include_local=True,
                    include_shared=False,
                )
                executed_actions.append("fallback_local_artifacts")
                fallback_action_count += 1
                self._record_maintenance_incident(
                    scope_key=scope_key,
                    incident_kind="shared_backend_unavailable",
                    severity="warning",
                    summary="Shared artifact backend was unavailable; maintenance fell back to local artifacts.",
                    mode="degraded",
                )

            pending_repairs = [
                repair
                for repair in self.list_memory_contradiction_repairs()
                if scope_key in repair.scope_keys and repair.repair_status == "recommended"
            ]
            grouped_repairs: dict[tuple[tuple[str, ...], str, str], list[MemoryContradictionRepairRecord]] = {}
            for repair in pending_repairs:
                key = (tuple(sorted(repair.scope_keys)), repair.subject, repair.predicate)
                grouped_repairs.setdefault(key, []).append(repair)
            for (repair_scope_keys, subject, predicate), repairs in grouped_repairs.items():
                self.train_repair_controller(scope_keys=list(repair_scope_keys))
                canary = self.run_contradiction_repair_canary(
                    scope_keys=list(repair_scope_keys),
                    subject=subject,
                    predicate=predicate,
                )
                repair_canary_run_ids.append(canary.run_id)
                if canary.recommendation == "apply":
                    action = self.apply_contradiction_repair(
                        repair_id=canary.repair_ids[0],
                        actor=actor,
                        reason="background maintenance applied safe repair",
                    )
                    repair_action_run_ids.append(action.run_id)
                    executed_actions.append("apply_safe_repair")
                else:
                    executed_actions.append("evaluate_repair_backlog")

            run = MemoryMaintenanceRun(
                version="1.0",
                run_id=f"memory-maintenance-run-{uuid4().hex[:10]}",
                scope_key=scope_key,
                recommendation_id=recommendation.recommendation_id,
                actor=actor,
                executed_actions=executed_actions,
                resumed_loop_run_ids=resumed_loop_run_ids,
                repair_canary_run_ids=repair_canary_run_ids,
                repair_action_run_ids=repair_action_run_ids,
                artifact_backend_repair_run_ids=artifact_backend_repair_run_ids,
                started_at=started_at,
                completed_at=utc_now(),
                status="completed",
                schedule_id=schedule_id,
                claimed_by_worker_id=claimed_by_worker_id,
            )
            self.maintenance_runs[run.run_id] = run
            if claimed_by_worker_id is not None:
                worker = self._get_maintenance_worker(claimed_by_worker_id)
                worker.active_run_ids = sorted(set(worker.active_run_ids + [run.run_id]))
                self.maintenance_workers[worker.worker_id] = worker
                if self.repository is not None:
                    self.repository.save_memory_maintenance_worker_record(worker)
            analytics = MemoryMaintenanceAnalyticsRecord(
                version="1.0",
                analytics_id=f"maintenance-analytics-{uuid4().hex[:10]}",
                scope_key=scope_key,
                run_id=run.run_id,
                executed_actions=list(executed_actions),
                resumed_loop_count=len(resumed_loop_run_ids),
                applied_repair_count=len(repair_action_run_ids),
                repaired_shared_artifact_count=len(artifact_backend_repair_run_ids),
                fallback_action_count=fallback_action_count,
                created_at=utc_now(),
            )
            self.maintenance_analytics[analytics.analytics_id] = analytics
            if self.repository is not None:
                self.repository.save_memory_maintenance_run(run)
                self.repository.save_memory_maintenance_analytics_record(analytics)
            runs.append(run)
        return runs

    def run_admission_controller_canary(
        self,
        *,
        scope_key: str,
        candidate_ids: list[str],
    ) -> MemoryAdmissionCanaryRun:
        started_at = utc_now()
        policy = self._load_admission_policy(scope_key)
        learning_state = self._load_admission_learning_state(scope_key)
        baseline_quarantine_count = 0
        promoted_quarantine_count = 0
        high_risk_override_count = 0
        for candidate_id in candidate_ids:
            candidate = self._get_candidate(candidate_id)
            if candidate.scope_key != scope_key:
                continue
            feature_values = self._extract_admission_features(candidate)
            score = self._score_admission_features(
                candidate=candidate,
                feature_values=feature_values,
                learning_state=learning_state,
            )
            baseline_action = self._baseline_candidate_action(candidate, policy=policy)
            baseline_quarantine_count += int(baseline_action == "quarantined")
            promoted_quarantine_count += int(score.recommended_action == "quarantined")
            high_risk_override_count += int(
                score.recommended_action == "quarantined" and baseline_action != "quarantined"
            )
        recommendation = "hold"
        if high_risk_override_count > 0:
            recommendation = "promote"
        elif promoted_quarantine_count < baseline_quarantine_count:
            recommendation = "rollback"
        run = MemoryAdmissionCanaryRun(
            version="1.0",
            run_id=f"memory-admission-canary-{uuid4().hex[:10]}",
            scope_key=scope_key,
            candidate_ids=list(candidate_ids),
            controller_version="v2" if learning_state is not None else "v1",
            recommendation=recommendation,
            metrics={
                "baseline_quarantine_count": float(baseline_quarantine_count),
                "promoted_quarantine_count": float(promoted_quarantine_count),
                "high_risk_override_count": float(high_risk_override_count),
                "quarantine_delta": float(promoted_quarantine_count - baseline_quarantine_count),
            },
            started_at=started_at,
            completed_at=utc_now(),
        )
        self.admission_canary_runs[run.run_id] = run
        if self.repository is not None:
            self.repository.save_memory_admission_canary_run(run)
        return run

    def _baseline_candidate_action(
        self,
        candidate: MemoryWriteCandidate,
        *,
        policy: MemoryAdmissionPolicy | None,
    ) -> str:
        quarantine_threshold = 0.65
        block_threshold = 0.9
        confirmation_threshold = 0.8
        if policy is not None:
            quarantine_threshold = policy.quarantine_poison_threshold
            block_threshold = policy.block_poison_threshold
            confirmation_threshold = policy.require_confirmation_threshold
        if candidate.poison_risk >= block_threshold:
            return "blocked"
        if candidate.poison_risk >= quarantine_threshold:
            return "quarantined"
        if max(candidate.privacy_risk, candidate.contradiction_risk) >= confirmation_threshold:
            return "requires_confirmation"
        return "accepted"

    def _rebuild_missing_matrix_pointers(self, *, scope_key: str) -> int:
        rebuilt_pointer_count = 0
        active_facts = self.list_temporal_semantic_facts(scope_key=scope_key)
        existing = {
            (pointer.head, tuple(pointer.target_fact_ids), tuple(pointer.target_pattern_ids))
            for pointer in self._list_matrix_pointers(scope_key=scope_key)
        }
        for fact in active_facts:
            key = (fact.head, (fact.fact_id,), ())
            if key in existing:
                continue
            candidate = MemoryWriteCandidate(
                version="1.0",
                candidate_id=f"rebuild-candidate-{uuid4().hex[:10]}",
                task_id=fact.task_id,
                scope_key=scope_key,
                lane="semantic",
                summary=f"{fact.subject} {fact.predicate} {fact.object}",
                content={"head": fact.head, "subject": fact.subject, "predicate": fact.predicate, "object": fact.object},
                sources=list(fact.provenance),
                importance=fact.confidence,
                novelty=0.5,
                utility=0.5,
                repetition=0.5,
                privacy_risk=0.0,
                poison_risk=0.0,
                contradiction_risk=0.0,
                governance_status="semantic_memory",
                created_at=utc_now(),
            )
            self._write_matrix_pointer(
                candidate=candidate,
                head=fact.head,
                summary=candidate.summary,
                target_fact_ids=[fact.fact_id],
                target_episode_ids=[source for source in fact.provenance if source.startswith("episode-")],
                target_pattern_ids=[],
            )
            rebuilt_pointer_count += 1
        return rebuilt_pointer_count

    def _rebuild_project_state_snapshots(self, *, scope_key: str) -> int:
        subjects = sorted({fact.subject for fact in self.list_temporal_semantic_facts(scope_key=scope_key)})
        rebuilt = 0
        for subject in subjects:
            self.reconstruct_project_state(scope_key=scope_key, subject=subject)
            rebuilt += 1
        return rebuilt

    def _materialize_memory_index_artifacts(
        self,
        *,
        scope_key: str,
        reason: str,
        only_missing: bool = False,
        include_local: bool = True,
        include_shared: bool = True,
    ) -> int:
        if not include_local and not include_shared:
            return 0
        rebuilt_count = 0
        snapshots = self.list_project_state_snapshots(scope_key=scope_key)
        if not snapshots:
            for subject in sorted({fact.subject for fact in self.list_temporal_semantic_facts(scope_key=scope_key)}):
                self.reconstruct_project_state(scope_key=scope_key, subject=subject)
            snapshots = self.list_project_state_snapshots(scope_key=scope_key)
        artifact_specs: list[tuple[Path | None, str, str]] = []
        if include_local:
            artifact_specs.extend(
                [
                    (self.artifact_root, "memory_index", "local_fs"),
                    (self.artifact_root, "project_state_index", "local_fs"),
                ]
            )
        if include_shared:
            artifact_specs.extend(
                [
                    (self.shared_artifact_root, "memory_index", "shared_fs"),
                    (self.shared_artifact_root, "project_state_index", "shared_fs"),
                ]
            )
        dashboard_payload = json.dumps([item.to_dict() for item in self.dashboard(scope_key=scope_key)], ensure_ascii=True, indent=2)
        snapshot_payload = json.dumps([item.to_dict() for item in snapshots], ensure_ascii=True, indent=2)
        for root, artifact_kind, backend_kind in artifact_specs:
            if root is None:
                continue
            artifact_dir = root / "memory_indexes"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            if artifact_kind == "memory_index":
                artifact_path = artifact_dir / f"{scope_key.replace(':', '_')}-dashboard.json"
                payload = dashboard_payload
            else:
                artifact_path = artifact_dir / f"{scope_key.replace(':', '_')}-project-state.json"
                payload = snapshot_payload
            if not only_missing or not artifact_path.exists():
                artifact_path.write_text(payload, encoding="utf-8")
                rebuilt_count += 1
            self.register_artifact(
                scope_key=scope_key,
                artifact_kind=artifact_kind,
                path=str(artifact_path),
                source_run_id=reason,
                backend_kind=backend_kind,
                backend_ref=f"{backend_kind}:{root}",
            )
        return rebuilt_count

    def _delete_artifact_path(self, path: str) -> None:
        if not path:
            return
        artifact_path = Path(path)
        if artifact_path.exists() and artifact_path.is_file():
            artifact_path.unlink()

    def _get_contradiction_repair(self, repair_id: str) -> MemoryContradictionRepairRecord:
        if repair_id in self.contradiction_repairs:
            return self.contradiction_repairs[repair_id]
        if self.repository is None:
            raise KeyError(repair_id)
        matches = [record for record in self.repository.list_memory_contradiction_repair_records() if record.repair_id == repair_id]
        if not matches:
            raise KeyError(repair_id)
        self.contradiction_repairs[repair_id] = matches[0]
        return matches[0]

    def _latest_repair_safety_assessment(
        self,
        scope_keys: list[str],
        *,
        repair_id: str,
    ) -> MemoryRepairSafetyAssessment | None:
        assessments = [
            item
            for item in self.list_repair_safety_assessments(scope_keys=scope_keys)
            if item.repair_id == repair_id
        ]
        return None if not assessments else assessments[0]

    def _assess_repair_safety(
        self,
        repair: MemoryContradictionRepairRecord,
        *,
        learning_state: MemoryRepairLearningState | None = None,
    ) -> MemoryRepairSafetyAssessment:
        facts = self._repair_facts(repair)
        state_count = len({fact.object for fact in facts})
        conflict_fact_count = len(facts)
        penalty = max(0.0, (conflict_fact_count - 2) * 0.15 + (state_count - 2) * 0.15)
        safety_score = max(0.0, 1.0 - penalty)
        learned_risk_penalty = 0.0 if learning_state is None else learning_state.learned_risk_penalty
        effective_safety_score = max(0.0, safety_score - learned_risk_penalty)
        apply_threshold = 0.75 if learning_state is None else learning_state.apply_threshold
        recommendation = "apply" if effective_safety_score >= apply_threshold else "hold"
        rationale = (
            "Repair is safe enough to apply because the conflict remains narrow and the latest state is clearly preferred."
            if recommendation == "apply"
            else "Repair should stay in canary hold because too many conflicting states are active across scopes."
        )
        assessment = MemoryRepairSafetyAssessment(
            version="1.0",
            assessment_id=f"memory-repair-safety-{uuid4().hex[:10]}",
            repair_id=repair.repair_id,
            scope_keys=list(repair.scope_keys),
            conflict_fact_count=conflict_fact_count,
            conflicting_state_count=state_count,
            safety_score=safety_score,
            recommendation=recommendation,
            rationale=rationale,
            created_at=utc_now(),
            controller_version="v1" if learning_state is None else learning_state.controller_version,
            base_safety_score=safety_score,
            effective_safety_score=effective_safety_score,
        )
        self.repair_safety_assessments[assessment.assessment_id] = assessment
        if self.repository is not None:
            self.repository.save_memory_repair_safety_assessment(assessment)
        return assessment

    def _repair_facts(self, repair: MemoryContradictionRepairRecord) -> list[TemporalSemanticFact]:
        facts_by_id = {fact.fact_id: fact for fact in self.list_temporal_semantic_facts()}
        return [facts_by_id[fact_id] for fact_id in repair.conflicting_fact_ids if fact_id in facts_by_id]

    def _get_operations_loop_run(self, loop_run_id: str) -> MemoryOperationsLoopRun:
        if loop_run_id in self.operations_loop_runs:
            return self.operations_loop_runs[loop_run_id]
        if self.repository is None:
            raise KeyError(loop_run_id)
        matches = [record for record in self.repository.list_memory_operations_loop_runs() if record.run_id == loop_run_id]
        if not matches:
            raise KeyError(loop_run_id)
        self.operations_loop_runs[loop_run_id] = matches[0]
        return matches[0]

    def _get_candidate(self, candidate_id: str) -> MemoryWriteCandidate:
        if candidate_id in self.candidates:
            return self.candidates[candidate_id]
        if self.repository is None:
            raise KeyError(candidate_id)
        candidate = self.repository.load_memory_write_candidate(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)
        self.candidates[candidate_id] = candidate
        return candidate

    def _get_admission_decision(self, candidate_id: str) -> MemoryAdmissionDecision | None:
        if candidate_id in self.admission_decisions:
            return self.admission_decisions[candidate_id]
        if self.repository is None:
            return None
        matches = [
            decision
            for decision in self.repository.list_memory_admission_decisions()
            if decision.candidate_id == candidate_id
        ]
        if not matches:
            return None
        self.admission_decisions[candidate_id] = matches[0]
        return matches[0]

    def _get_governance_decision(self, candidate_id: str) -> MemoryGovernanceDecision | None:
        if candidate_id in self.governance_decisions:
            return self.governance_decisions[candidate_id]
        if self.repository is None:
            return None
        decision = self.repository.latest_memory_governance_decision(candidate_id)
        if decision is not None:
            self.governance_decisions[candidate_id] = decision
        return decision

    def _consolidate_semantic_candidate(self, candidate: MemoryWriteCandidate) -> TemporalSemanticFact:
        now = utc_now()
        valid_from = self._parse_datetime(candidate.content.get("valid_from")) or now
        subject = str(candidate.content.get("subject", "unknown"))
        predicate = str(candidate.content.get("predicate", "related_to"))
        obj = str(candidate.content.get("object", candidate.summary))
        head = str(candidate.content.get("head", "semantic"))
        existing = [
            fact
            for fact in self.list_temporal_semantic_facts(scope_key=candidate.scope_key)
            if fact.subject == subject and fact.predicate == predicate and fact.status == "active"
        ]
        status = "active"
        supersedes_fact_id: str | None = None
        for prior in existing:
            prior.valid_until = valid_from
            prior.status = "superseded"
            self.semantic_facts[prior.fact_id] = prior
            if self.repository is not None:
                self.repository.save_temporal_semantic_fact(prior)
            supersedes_fact_id = prior.fact_id
        fact = TemporalSemanticFact(
            version="1.0",
            fact_id=f"fact-{uuid4().hex[:10]}",
            task_id=candidate.task_id,
            scope_key=candidate.scope_key,
            subject=subject,
            predicate=predicate,
            object=obj,
            head=head,
            confidence=max(0.5, min(0.99, candidate.importance + candidate.utility - candidate.contradiction_risk / 2.0)),
            provenance=list(candidate.sources),
            observed_at=now,
            valid_from=valid_from,
            valid_until=None,
            status=status,
            supersedes_fact_id=supersedes_fact_id,
        )
        self.semantic_facts[fact.fact_id] = fact
        if self.repository is not None:
            self.repository.save_temporal_semantic_fact(fact)
        self._refresh_durative_memory(fact)
        return fact

    def _refresh_durative_memory(self, fact: TemporalSemanticFact) -> None:
        related = [
            item
            for item in self.list_temporal_semantic_facts(scope_key=fact.scope_key)
            if item.subject == fact.subject and item.predicate == fact.predicate
        ]
        if len(related) < 2:
            return
        ordered = sorted(related, key=lambda item: item.valid_from or item.observed_at)
        record = DurativeMemoryRecord(
            version="1.0",
            durative_id=f"durative-{fact.subject}-{fact.predicate}".replace(" ", "-"),
            task_id=fact.task_id,
            scope_key=fact.scope_key,
            subject=fact.subject,
            predicate=fact.predicate,
            summary=f"{fact.subject} has evolving state for {fact.predicate}",
            event_fact_ids=[item.fact_id for item in ordered],
            valid_from=ordered[0].valid_from,
            valid_until=ordered[-1].valid_until,
            status="active",
            created_at=utc_now(),
        )
        self.durative_records[record.durative_id] = record
        if self.repository is not None:
            self.repository.save_durative_memory(record)

    def _consolidate_procedural_candidate(self, candidate: MemoryWriteCandidate) -> ProceduralPattern:
        pattern = ProceduralPattern(
            version="1.0",
            pattern_id=f"pattern-{uuid4().hex[:10]}",
            task_id=candidate.task_id,
            scope_key=candidate.scope_key,
            summary=candidate.summary,
            trigger=str(candidate.content.get("trigger", candidate.summary)),
            preconditions=[str(item) for item in candidate.content.get("preconditions", [])],
            steps=[str(item) for item in candidate.content.get("steps", [])],
            tools=[str(item) for item in candidate.content.get("tools", [])],
            outcome=str(candidate.content.get("outcome", "unknown")),
            failure_modes=[str(item) for item in candidate.content.get("failure_modes", [])],
            sources=list(candidate.sources),
            confidence=max(0.5, min(0.98, candidate.importance + candidate.utility - candidate.poison_risk)),
            status="active",
            created_at=utc_now(),
        )
        self.procedural_patterns[pattern.pattern_id] = pattern
        if self.repository is not None:
            self.repository.save_procedural_pattern(pattern)
        return pattern

    def _consolidate_explicit_candidate(self, candidate: MemoryWriteCandidate) -> ExplicitMemoryRecord:
        record = ExplicitMemoryRecord(
            version="1.0",
            record_id=f"explicit-{uuid4().hex[:10]}",
            task_id=candidate.task_id,
            scope_key=candidate.scope_key,
            memory_class=str(candidate.content.get("memory_class", "explicit")),
            summary=candidate.summary,
            content=dict(candidate.content),
            editable=True,
            sources=list(candidate.sources),
            created_at=utc_now(),
        )
        self.explicit_records[record.record_id] = record
        if self.repository is not None:
            self.repository.save_explicit_memory_record(record)
        return record

    def _write_matrix_pointer(
        self,
        *,
        candidate: MemoryWriteCandidate,
        head: str,
        summary: str,
        target_fact_ids: list[str],
        target_episode_ids: list[str],
        target_pattern_ids: list[str],
    ) -> MatrixAssociationPointer:
        content_tokens = _tokenize(summary)
        for value in candidate.content.values():
            content_tokens.update(_tokenize(_safe_text(value)))
        pointer = MatrixAssociationPointer(
            version="1.0",
            pointer_id=f"pointer-{uuid4().hex[:10]}",
            task_id=candidate.task_id,
            scope_key=candidate.scope_key,
            head=head,
            key_terms=sorted(content_tokens)[:24],
            summary=summary,
            target_episode_ids=target_episode_ids,
            target_fact_ids=target_fact_ids,
            target_pattern_ids=target_pattern_ids,
            strength=max(0.4, min(0.99, candidate.importance + candidate.utility - candidate.poison_risk / 2.0)),
            created_at=utc_now(),
        )
        self.matrix_pointers[pointer.pointer_id] = pointer
        if self.repository is not None:
            self.repository.save_matrix_association_pointer(pointer)
        return pointer

    def _list_matrix_pointers(self, *, scope_key: str | None = None, task_id: str | None = None) -> list[MatrixAssociationPointer]:
        records = list(self.matrix_pointers.values())
        if self.repository is not None:
            repository_records = self.repository.list_matrix_association_pointers(scope_key=scope_key, task_id=task_id)
            for record in repository_records:
                self.matrix_pointers[record.pointer_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        if task_id is not None:
            records = [record for record in records if record.task_id == task_id]
        tombstones_by_scope = self._tombstone_index(scope_key)
        records = [
            record
            for record in records
            if ("matrix_pointer", record.pointer_id) not in tombstones_by_scope.get(record.scope_key, set())
        ]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def _list_procedural_patterns(self, *, scope_key: str | None = None, task_id: str | None = None) -> list[ProceduralPattern]:
        records = list(self.procedural_patterns.values())
        if self.repository is not None:
            repository_records = self.repository.list_procedural_patterns(scope_key=scope_key, task_id=task_id)
            for record in repository_records:
                self.procedural_patterns[record.pattern_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        if task_id is not None:
            records = [record for record in records if record.task_id == task_id]
        tombstones_by_scope = self._tombstone_index(scope_key)
        records = [
            record
            for record in records
            if ("procedural_pattern", record.pattern_id) not in tombstones_by_scope.get(record.scope_key, set())
        ]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def _score_overlap(self, query_tokens: set[str], text: str) -> float:
        if not query_tokens:
            return 0.0
        tokens = _tokenize(text)
        if not tokens:
            return 0.0
        overlap = len(query_tokens & tokens)
        return overlap / max(len(tokens), 1)

    def _score_semantic_facts(self, query_tokens: set[str], facts: list[TemporalSemanticFact]) -> list[TemporalSemanticFact]:
        return sorted(
            facts,
            key=lambda item: (
                self._score_overlap(query_tokens, f"{item.subject} {item.predicate} {item.object} {item.head}") + item.confidence,
                item.observed_at,
            ),
            reverse=True,
        )

    def _score_raw_episodes(self, query_tokens: set[str], records: list[RawEpisodeRecord]) -> list[RawEpisodeRecord]:
        return sorted(
            records,
            key=lambda item: (
                self._score_overlap(query_tokens, _safe_text(item.content)) + item.trust,
                item.created_at,
            ),
            reverse=True,
        )

    def _score_pointers(self, query_tokens: set[str], records: list[MatrixAssociationPointer]) -> list[MatrixAssociationPointer]:
        return sorted(
            records,
            key=lambda item: (
                self._score_overlap(query_tokens, " ".join(item.key_terms) + " " + item.summary) + item.strength,
                item.created_at,
            ),
            reverse=True,
        )

    def _score_patterns(self, query_tokens: set[str], records: list[ProceduralPattern]) -> list[ProceduralPattern]:
        return sorted(
            records,
            key=lambda item: (
                self._score_overlap(query_tokens, f"{item.summary} {item.trigger} {' '.join(item.steps)}") + item.confidence,
                item.created_at,
            ),
            reverse=True,
        )

    def _fact_is_relevant_at_time(self, fact: TemporalSemanticFact, at_time: datetime | None) -> bool:
        if at_time is None:
            return fact.status == "active" or fact.valid_until is None
        if fact.valid_from is not None and fact.valid_from > at_time:
            return False
        if fact.valid_until is not None and fact.valid_until < at_time:
            return False
        return True

    def _contains_privacy_terms(self, summary: str, content: dict[str, object]) -> bool:
        text = f"{summary} {_safe_text(content)}".lower()
        return any(term in text for term in {"password", "secret", "ssn", "api key", "credential"})

    def _contains_poison_terms(self, summary: str, content: dict[str, object]) -> bool:
        return self._poison_risk_score(summary, content) >= 0.9

    def _poison_risk_score(self, summary: str, content: dict[str, object]) -> float:
        text = f"{summary} {_safe_text(content)}".lower()
        severe_terms = {
            "ignore policy",
            "ignore previous safety",
            "bypass approval",
            "disable safety",
            "run rm -rf",
            "drop audit",
            "delete audit",
        }
        moderate_terms = {
            "skip approval",
            "skip normal approval flow",
            "hidden terminal shortcut",
            "hidden terminal shortcuts",
            "avoid normal review path",
            "override guardrails",
            "work around approval",
        }
        if any(term in text for term in severe_terms):
            return 0.95
        if any(term in text for term in moderate_terms):
            return 0.68
        return 0.05

    def _extract_admission_features(self, candidate: MemoryWriteCandidate) -> dict[str, float]:
        text = f"{candidate.summary} {_safe_text(candidate.content)}".lower()
        steps = " ".join(str(step) for step in candidate.content.get("steps", []))
        tools = " ".join(str(tool) for tool in candidate.content.get("tools", []))
        instruction_override_terms = {
            "ignore policy",
            "bypass approval",
            "skip approval",
            "skip normal approval flow",
            "override",
            "avoid normal review path",
        }
        tool_override_terms = {"hidden terminal shortcut", "terminal shortcut", "shell_patch", "work around approval"}
        destructive_terms = {"rm -rf", "delete audit", "drop audit", "disable safety"}
        return {
            "instruction_override_signal": 1.0 if any(term in text or term in steps for term in instruction_override_terms) else 0.0,
            "tool_override_signal": 1.0 if any(term in text or term in tools for term in tool_override_terms) else 0.0,
            "destructive_signal": 1.0 if any(term in text for term in destructive_terms) else 0.0,
            "privacy_signal": candidate.privacy_risk,
            "contradiction_signal": candidate.contradiction_risk,
            "single_source_signal": 1.0 if len(candidate.sources) <= 1 else 0.0,
        }

    def _score_admission_features(
        self,
        *,
        candidate: MemoryWriteCandidate,
        feature_values: dict[str, float],
        learning_state: MemoryAdmissionLearningState | None,
    ) -> MemoryAdmissionFeatureScore:
        weights = {
            "instruction_override_signal": 0.0,
            "tool_override_signal": 0.0,
            "destructive_signal": 0.2,
            "privacy_signal": 0.0,
            "contradiction_signal": 0.0,
            "single_source_signal": 0.0,
        }
        controller_version = "v1"
        if learning_state is not None:
            controller_version = learning_state.controller_version
            weights.update(learning_state.feature_weights)
            weights["privacy_signal"] = max(weights.get("privacy_signal", 0.0), learning_state.privacy_confirmation_boost)
            weights["contradiction_signal"] = max(weights.get("contradiction_signal", 0.0), learning_state.contradiction_boost)
        weighted_score = min(
            1.0,
            candidate.poison_risk
            + sum(weights.get(key, 0.0) * value for key, value in feature_values.items()),
        )
        recommended_action = "accepted"
        if learning_state is not None:
            if weighted_score >= learning_state.recommended_block_threshold:
                recommended_action = "blocked"
            elif weighted_score >= learning_state.recommended_quarantine_threshold:
                recommended_action = "quarantined"
            elif feature_values.get("privacy_signal", 0.0) >= learning_state.recommended_confirmation_threshold:
                recommended_action = "requires_confirmation"
        return MemoryAdmissionFeatureScore(
            version="1.0",
            score_id=f"admission-score-{uuid4().hex[:10]}",
            candidate_id=candidate.candidate_id,
            scope_key=candidate.scope_key,
            controller_version=controller_version,
            feature_values=feature_values,
            weighted_score=weighted_score,
            recommended_action=recommended_action,
            created_at=utc_now(),
        )

    def _has_existing_semantic_conflict(self, scope_key: str, content: dict[str, object]) -> bool:
        subject = str(content.get("subject", ""))
        predicate = str(content.get("predicate", ""))
        obj = str(content.get("object", ""))
        if not subject or not predicate or not obj:
            return False
        for fact in self.list_temporal_semantic_facts(scope_key=scope_key):
            if fact.subject == subject and fact.predicate == predicate and fact.object != obj and fact.status == "active":
                return True
        return False

    def _parse_datetime(self, value: object) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _write_tombstone(self, *, scope_key: str, target_kind: str, target_id: str, actor: str, reason: str) -> None:
        if self._is_tombstoned(scope_key=scope_key, target_kind=target_kind, target_id=target_id):
            return
        record = MemoryTombstoneRecord(
            version="1.0",
            tombstone_id=f"tombstone-{uuid4().hex[:10]}",
            scope_key=scope_key,
            target_kind=target_kind,
            target_id=target_id,
            actor=actor,
            reason=reason,
            deleted_at=utc_now(),
        )
        self.tombstones[record.tombstone_id] = record
        if self.repository is not None:
            self.repository.save_memory_tombstone(record)

    def _is_tombstoned(self, *, scope_key: str, target_kind: str, target_id: str) -> bool:
        return (target_kind, target_id) in self._tombstone_index(scope_key).get(scope_key, set())

    def _tombstone_index(self, scope_key: str | None = None) -> dict[str, set[tuple[str, str]]]:
        index: dict[str, set[tuple[str, str]]] = {}
        for record in self.list_memory_tombstones(scope_key=scope_key):
            index.setdefault(record.scope_key, set()).add((record.target_kind, record.target_id))
        return index

    def _deduplicate_pointers(self, *, scope_key: str) -> int:
        removed = 0
        seen: set[tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = set()
        for pointer in sorted(self._list_matrix_pointers(scope_key=scope_key), key=lambda item: item.created_at):
            key = (
                pointer.head,
                tuple(pointer.target_episode_ids),
                tuple(pointer.target_fact_ids),
                tuple(pointer.target_pattern_ids),
            )
            if key in seen:
                self._write_tombstone(
                    scope_key=scope_key,
                    target_kind="matrix_pointer",
                    target_id=pointer.pointer_id,
                    actor="system",
                    reason="deduplicated during sleep-time consolidation",
                )
                removed += 1
                continue
            seen.add(key)
        return removed
