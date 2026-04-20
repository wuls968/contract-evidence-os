"""Maintenance and repair-control behavior for AMOS memory."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.memory._base import MemorySubservice
from contract_evidence_os.memory.models import (
    MemoryArtifactBackendHealthRecord,
    MemoryArtifactBackendRepairRun,
    MemoryArtifactDriftRecord,
    MemoryMaintenanceCanaryRun,
    MemoryMaintenanceControllerState,
    MemoryMaintenanceIncidentRecord,
    MemoryMaintenanceLearningState,
    MemoryMaintenancePromotionRecommendation,
    MemoryMaintenanceRecommendation,
    MemoryMaintenanceRecoveryRecord,
    MemoryMaintenanceRolloutRecord,
    MemoryMaintenanceRun,
    MemoryMaintenanceSchedule,
    MemoryMaintenanceWorkerRecord,
    MemoryOperationsDiagnosticRecord,
)


class MemoryMaintenanceService(MemorySubservice):
    """Own long-running maintenance and maintenance-governance behavior."""

    def artifact_backend_health(
        self,
        *,
        scope_key: str,
    ) -> list[MemoryArtifactBackendHealthRecord]:
        records: list[MemoryArtifactBackendHealthRecord] = []
        for backend_kind in sorted({record.backend_kind for record in self.list_memory_artifacts(scope_key=scope_key)}):
            artifacts = [record for record in self.list_memory_artifacts(scope_key=scope_key) if record.backend_kind == backend_kind]
            if not artifacts:
                continue
            missing = sum(1 for record in artifacts if not Path(record.path).exists())
            health = MemoryArtifactBackendHealthRecord(
                version="1.0",
                health_id=f"memory-artifact-health-{uuid4().hex[:10]}",
                scope_key=scope_key,
                backend_kind=backend_kind,
                total_artifact_count=len(artifacts),
                missing_artifact_count=missing,
                healthy=missing == 0,
                created_at=utc_now(),
            )
            self.artifact_backend_health_records[health.health_id] = health
            if self.repository is not None:
                self.repository.save_memory_artifact_backend_health_record(health)
            records.append(health)
        return sorted(records, key=lambda item: (item.backend_kind, item.created_at))

    def scan_artifact_drift(
        self,
        *,
        scope_key: str,
    ) -> list[MemoryArtifactDriftRecord]:
        local_by_kind = {
            record.artifact_kind: record
            for record in self.list_memory_artifacts(scope_key=scope_key)
            if record.backend_kind == "local_fs"
        }
        shared_by_kind = {
            record.artifact_kind: record
            for record in self.list_memory_artifacts(scope_key=scope_key)
            if record.backend_kind == "shared_fs"
        }
        drifts: list[MemoryArtifactDriftRecord] = []
        for artifact_kind in sorted(set(local_by_kind) & set(shared_by_kind)):
            local = local_by_kind[artifact_kind]
            shared = shared_by_kind[artifact_kind]
            local_path = Path(local.path)
            shared_path = Path(shared.path)
            drift_kind = ""
            summary = ""
            if not local_path.exists() or not shared_path.exists():
                drift_kind = "missing"
                summary = "Local/shared artifact pair is missing one side."
            elif local_path.read_text(encoding="utf-8") != shared_path.read_text(encoding="utf-8"):
                drift_kind = "content_mismatch"
                summary = "Shared artifact content drifted away from the local source-grounded index."
            if not drift_kind:
                continue
            existing = next(
                (
                    item
                    for item in self.list_memory_artifact_drift(scope_key=scope_key, status="active")
                    if item.artifact_kind == artifact_kind and item.local_path == local.path and item.shared_path == shared.path
                ),
                None,
            )
            if existing is not None:
                existing.drift_kind = drift_kind
                existing.summary = summary
                drifts.append(existing)
                if self.repository is not None:
                    self.repository.save_memory_artifact_drift_record(existing)
                continue
            record = MemoryArtifactDriftRecord(
                version="1.0",
                drift_id=f"memory-artifact-drift-{uuid4().hex[:10]}",
                scope_key=scope_key,
                artifact_kind=artifact_kind,
                local_artifact_id=local.artifact_id,
                shared_artifact_id=shared.artifact_id,
                local_path=local.path,
                shared_path=shared.path,
                drift_kind=drift_kind,
                summary=summary,
                status="active",
                detected_at=utc_now(),
                reconciled_at=None,
            )
            self.artifact_drift_records[record.drift_id] = record
            if self.repository is not None:
                self.repository.save_memory_artifact_drift_record(record)
            drifts.append(record)
        return drifts

    def repair_artifact_backend(
        self,
        *,
        scope_key: str,
        backend_kind: str,
        actor: str,
        reason: str,
    ) -> MemoryArtifactBackendRepairRun:
        started_at = utc_now()
        repaired_paths_before = {
            record.path
            for record in self.list_memory_artifacts(scope_key=scope_key)
            if record.backend_kind == backend_kind and not Path(record.path).exists()
        }
        rebuilt_count = 0
        if backend_kind == "shared_fs":
            rebuilt_count = self._materialize_memory_index_artifacts(
                scope_key=scope_key,
                reason=reason,
                only_missing=True,
                include_local=False,
                include_shared=True,
            )
        else:
            rebuilt_count = self._materialize_memory_index_artifacts(
                scope_key=scope_key,
                reason=reason,
                only_missing=True,
                include_local=True,
                include_shared=False,
            )
        repaired_paths = [
            record.path
            for record in self.list_memory_artifacts(scope_key=scope_key)
            if record.backend_kind == backend_kind and record.path in repaired_paths_before and Path(record.path).exists()
        ]
        run = MemoryArtifactBackendRepairRun(
            version="1.0",
            run_id=f"memory-artifact-repair-{uuid4().hex[:10]}",
            scope_key=scope_key,
            backend_kind=backend_kind,
            actor=actor,
            reason=reason,
            repaired_artifact_count=max(rebuilt_count, len(repaired_paths)),
            repaired_paths=repaired_paths,
            started_at=started_at,
            completed_at=utc_now(),
        )
        self.artifact_backend_repair_runs[run.run_id] = run
        if self.repository is not None:
            self.repository.save_memory_artifact_backend_repair_run(run)
        return run

    def _mark_artifact_drift_reconciled(
        self,
        *,
        scope_key: str,
    ) -> list[MemoryArtifactDriftRecord]:
        reconciled: list[MemoryArtifactDriftRecord] = []
        for record in self.list_memory_artifact_drift(scope_key=scope_key, status="active"):
            record.status = "reconciled"
            record.reconciled_at = utc_now()
            self.artifact_drift_records[record.drift_id] = record
            if self.repository is not None:
                self.repository.save_memory_artifact_drift_record(record)
            reconciled.append(record)
        return reconciled

    def _record_maintenance_incident(
        self,
        *,
        scope_key: str,
        incident_kind: str,
        severity: str,
        summary: str,
        mode: str,
        related_run_id: str | None = None,
    ) -> MemoryMaintenanceIncidentRecord:
        existing = next(
            (
                item
                for item in self.list_memory_maintenance_incidents(scope_key=scope_key, status="active")
                if item.incident_kind == incident_kind
            ),
            None,
        )
        if existing is not None:
            existing.summary = summary
            existing.severity = severity
            existing.mode = mode
            existing.related_run_id = related_run_id
            self.maintenance_incidents[existing.incident_id] = existing
            if self.repository is not None:
                self.repository.save_memory_maintenance_incident_record(existing)
            return existing
        incident = MemoryMaintenanceIncidentRecord(
            version="1.0",
            incident_id=f"memory-maintenance-incident-{uuid4().hex[:10]}",
            scope_key=scope_key,
            incident_kind=incident_kind,
            severity=severity,
            summary=summary,
            mode=mode,
            status="active",
            created_at=utc_now(),
            related_run_id=related_run_id,
            resolved_at=None,
        )
        self.maintenance_incidents[incident.incident_id] = incident
        if self.repository is not None:
            self.repository.save_memory_maintenance_incident_record(incident)
        return incident

    def maintenance_mode(
        self,
        *,
        scope_key: str,
    ) -> dict[str, object]:
        active_incidents = self.list_memory_maintenance_incidents(scope_key=scope_key, status="active")
        active_drifts = self.list_memory_artifact_drift(scope_key=scope_key, status="active")
        mode = "normal"
        reasons: list[str] = []
        if active_drifts:
            mode = "degraded"
            reasons.append("artifact_drift_detected")
        if active_incidents:
            mode = "degraded"
            reasons.extend(sorted({incident.incident_kind for incident in active_incidents}))
        return {
            "scope_key": scope_key,
            "mode": mode,
            "reasons": reasons,
            "active_incident_count": len(active_incidents),
            "active_drift_count": len(active_drifts),
        }

    def memory_operations_diagnostics(self, *, scope_key: str) -> MemoryOperationsDiagnosticRecord:
        records = self.list_memory_artifacts(scope_key=scope_key)
        missing_artifact_count = sum(1 for record in records if not Path(record.path).exists())
        shared_health = [
            item
            for item in self.artifact_backend_health(scope_key=scope_key)
            if item.backend_kind == "shared_fs"
        ]
        missing_shared_artifact_count = sum(item.missing_artifact_count for item in shared_health)
        repair_backlog_count = sum(
            1 for repair in self.list_memory_contradiction_repairs() if scope_key in repair.scope_keys and repair.repair_status == "recommended"
        )
        interrupted_loop_count = sum(
            1 for recovery in self.list_memory_operations_loop_recoveries(scope_key=scope_key) if recovery.status == "pending"
        )
        due_schedule_count = sum(
            1 for schedule in self.list_memory_operations_loop_schedules(scope_key=scope_key) if schedule.enabled and schedule.next_run_at <= utc_now()
        )
        recommendation_count = len(self.list_admission_promotion_recommendations(scope_key=scope_key))
        maintenance_recommendation_count = len(self.list_memory_maintenance_recommendations(scope_key=scope_key))
        record = MemoryOperationsDiagnosticRecord(
            version="1.0",
            diagnostic_id=f"memory-ops-diagnostic-{uuid4().hex[:10]}",
            scope_key=scope_key,
            missing_artifact_count=missing_artifact_count,
            repair_backlog_count=repair_backlog_count,
            interrupted_loop_count=interrupted_loop_count,
            due_schedule_count=due_schedule_count,
            recommendation_count=recommendation_count,
            created_at=utc_now(),
            missing_shared_artifact_count=missing_shared_artifact_count,
            maintenance_recommendation_count=maintenance_recommendation_count,
        )
        self.operations_diagnostics[record.diagnostic_id] = record
        if self.repository is not None:
            self.repository.save_memory_operations_diagnostic_record(record)
        return record

    def train_maintenance_controller(self, *, scope_key: str) -> MemoryMaintenanceLearningState:
        diagnostics = self.memory_operations_diagnostics(scope_key=scope_key)
        prior_runs = self.list_memory_maintenance_runs(scope_key=scope_key)
        recovery_weight = min(0.4, diagnostics.interrupted_loop_count * 0.15 + sum("resume_interrupted_loop" in item.executed_actions for item in prior_runs) * 0.05)
        shared_backend_weight = min(0.4, diagnostics.missing_shared_artifact_count * 0.2)
        repair_backlog_weight = min(0.4, diagnostics.repair_backlog_count * 0.1)
        fallback_weight = min(0.4, sum("fallback_local_artifacts" in item.executed_actions for item in prior_runs) * 0.1)
        state = MemoryMaintenanceLearningState(
            version="1.0",
            learning_id=f"maintenance-learning-{uuid4().hex[:10]}",
            scope_key=scope_key,
            examples_seen=len(prior_runs) + diagnostics.maintenance_recommendation_count,
            recovery_weight=recovery_weight,
            shared_backend_weight=shared_backend_weight,
            repair_backlog_weight=repair_backlog_weight,
            fallback_weight=fallback_weight,
            trained_at=utc_now(),
            controller_version="v2",
        )
        self.maintenance_learning_states[scope_key] = state
        if self.repository is not None:
            self.repository.save_memory_maintenance_learning_state(state)
        return state

    def _build_maintenance_recommendation(
        self,
        *,
        scope_key: str,
        learning_state: MemoryMaintenanceLearningState | None,
    ) -> MemoryMaintenanceRecommendation:
        diagnostics = self.memory_operations_diagnostics(scope_key=scope_key)
        active_drifts = self.scan_artifact_drift(scope_key=scope_key)
        content_drifts = [item for item in active_drifts if item.drift_kind == "content_mismatch"]
        pending_repairs = [
            repair
            for repair in self.list_memory_contradiction_repairs()
            if scope_key in repair.scope_keys and repair.repair_status == "recommended"
        ]
        pending_recoveries = [
            recovery
            for recovery in self.list_memory_operations_loop_recoveries(scope_key=scope_key)
            if recovery.status == "pending"
        ]
        due_schedules = [
            schedule
            for schedule in self.list_memory_operations_loop_schedules(scope_key=scope_key)
            if schedule.enabled and schedule.next_run_at <= utc_now()
        ]
        scored_actions: list[tuple[float, str, str]] = []
        has_shared_artifacts = any(
            record.backend_kind == "shared_fs"
            for record in self.list_memory_artifacts(scope_key=scope_key)
        )
        if pending_recoveries:
            score = 1.0 + (0.0 if learning_state is None else learning_state.recovery_weight)
            scored_actions.append((score, "resume_interrupted_loop", "Interrupted maintenance loop has a pending recovery record."))
        if due_schedules:
            scored_actions.append((0.8, "run_due_schedule", "A scheduled memory operations loop is due."))
        if self.shared_artifact_root is None and has_shared_artifacts:
            score = 0.95 + (0.0 if learning_state is None else learning_state.fallback_weight)
            scored_actions.append((score, "fallback_local_artifacts", "Shared artifact backend is unavailable; rebuild local mirrors instead."))
        elif content_drifts and self.shared_artifact_root is not None:
            scored_actions.append((0.92, "reconcile_shared_artifacts", "Shared artifact mirror drifted from the local source-grounded index."))
        elif diagnostics.missing_shared_artifact_count > 0 and self.shared_artifact_root is not None:
            score = 0.9 + (0.0 if learning_state is None else learning_state.shared_backend_weight)
            scored_actions.append((score, "repair_shared_artifacts", "Shared artifact mirror has missing files."))
        if pending_repairs:
            score = 0.7 + (0.0 if learning_state is None else learning_state.repair_backlog_weight)
            scored_actions.append((score, "evaluate_repair_backlog", "Cross-scope contradiction repairs are waiting for canary evaluation."))
        if diagnostics.recommendation_count > 0:
            scored_actions.append((0.4, "review_admission_promotion", "Admission promotion recommendations exist for operator review."))
        scored_actions.sort(key=lambda item: (-item[0], item[1]))
        return MemoryMaintenanceRecommendation(
            version="1.0",
            recommendation_id=f"memory-maintenance-recommendation-{uuid4().hex[:10]}",
            scope_key=scope_key,
            actions=[item[1] for item in scored_actions],
            reasons=[item[2] for item in scored_actions],
            pending_repair_ids=[item.repair_id for item in pending_repairs],
            pending_recovery_ids=[item.recovery_id for item in pending_recoveries],
            due_schedule_ids=[item.schedule_id for item in due_schedules],
            created_at=utc_now(),
            controller_version="v1" if learning_state is None else learning_state.controller_version,
        )

    def recommend_memory_maintenance(self, *, scope_key: str) -> MemoryMaintenanceRecommendation:
        controller_state = self._load_maintenance_controller_state(scope_key)
        learning_state = self._load_maintenance_learning_state(scope_key)
        record = self._build_maintenance_recommendation(
            scope_key=scope_key,
            learning_state=learning_state if controller_state.active_controller_version != "v1" else None,
        )
        self.maintenance_recommendations[record.recommendation_id] = record
        if self.repository is not None:
            self.repository.save_memory_maintenance_recommendation(record)
        return record

    def register_maintenance_worker(
        self,
        *,
        worker_id: str,
        host_id: str,
        actor: str,
    ) -> MemoryMaintenanceWorkerRecord:
        now = utc_now()
        worker = MemoryMaintenanceWorkerRecord(
            version="1.0",
            worker_id=worker_id,
            host_id=host_id,
            actor=actor,
            status="active",
            current_mode="idle",
            registered_at=now,
            last_heartbeat_at=now,
            claimed_schedule_ids=[],
            active_run_ids=[],
        )
        self.maintenance_workers[worker_id] = worker
        if self.repository is not None:
            self.repository.save_memory_maintenance_worker_record(worker)
        return worker

    def heartbeat_maintenance_worker(
        self,
        *,
        worker_id: str,
        current_mode: str | None = None,
    ) -> MemoryMaintenanceWorkerRecord:
        worker = self._get_maintenance_worker(worker_id)
        worker.last_heartbeat_at = utc_now()
        if current_mode is not None:
            worker.current_mode = current_mode
        self.maintenance_workers[worker_id] = worker
        if self.repository is not None:
            self.repository.save_memory_maintenance_worker_record(worker)
        return worker

    def reclaim_stale_maintenance_workers(
        self,
        *,
        now: datetime | None = None,
        heartbeat_expiry_seconds: int = 300,
    ) -> list[MemoryMaintenanceWorkerRecord]:
        current_time = utc_now() if now is None else now
        cutoff = current_time - timedelta(seconds=heartbeat_expiry_seconds)
        reclaimed: list[MemoryMaintenanceWorkerRecord] = []
        for worker in self.list_memory_maintenance_workers():
            if worker.last_heartbeat_at >= cutoff or worker.status == "stale":
                continue
            worker.status = "stale"
            worker.current_mode = "reclaimed"
            worker.active_run_ids = []
            claimed_schedule_ids = list(worker.claimed_schedule_ids)
            worker.claimed_schedule_ids = []
            self.maintenance_workers[worker.worker_id] = worker
            if self.repository is not None:
                self.repository.save_memory_maintenance_worker_record(worker)
            for schedule_id in claimed_schedule_ids:
                schedule = next(
                    (item for item in self.list_memory_maintenance_schedules() if item.schedule_id == schedule_id),
                    None,
                )
                if schedule is None:
                    continue
                schedule.claimed_by_worker_id = None
                schedule.lease_expires_at = None
                schedule.updated_at = utc_now()
                self.maintenance_schedules[schedule.schedule_id] = schedule
                if self.repository is not None:
                    self.repository.save_memory_maintenance_schedule(schedule)
            reclaimed.append(worker)
        return reclaimed
