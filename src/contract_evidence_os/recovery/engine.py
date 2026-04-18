"""Checkpoint and recovery engine."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.recovery.models import CheckpointRecord, IncidentReport
from contract_evidence_os.storage.repository import SQLiteRepository


@dataclass
class RecoveryEngine:
    """Persist checkpoints and classify recoverable failures."""

    storage_root: Path | None = None
    repository: SQLiteRepository | None = None
    checkpoints: dict[str, dict[str, object]] = field(default_factory=dict)
    checkpoint_records: dict[str, CheckpointRecord] = field(default_factory=dict)
    failure_context: dict[str, IncidentReport] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.repository is None and self.storage_root is not None:
            self.repository = SQLiteRepository(self.storage_root / "contract_evidence_os.sqlite3")

    def save_checkpoint(
        self,
        task_id: str,
        plan_node_id: str,
        state: dict[str, object],
    ) -> CheckpointRecord:
        checkpoint_id = f"checkpoint-{uuid4().hex[:10]}"
        state_ref = f"{checkpoint_id}.json"
        record = CheckpointRecord(
            version="1.0",
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            plan_node_id=plan_node_id,
            state_ref=state_ref,
            created_at=utc_now(),
            metadata={"keys": list(state.keys())},
        )
        self.checkpoints[checkpoint_id] = state
        self.checkpoint_records[checkpoint_id] = record
        if self.repository is not None:
            self.repository.save_checkpoint(record, state)
        return record

    def restore_checkpoint(self, checkpoint_id: str) -> dict[str, object]:
        if checkpoint_id in self.checkpoints:
            return self.checkpoints[checkpoint_id]
        if self.repository is None:
            raise KeyError(checkpoint_id)
        return self.repository.restore_checkpoint(checkpoint_id)

    def classify_failure(self, task_id: str, incident_type: str, summary: str) -> IncidentReport:
        recoverable = {
            "provider_error",
            "tool_failure",
            "network_failure",
            "environment_drift",
            "permission_denial",
            "verification_failure",
            "contract_ambiguity",
            "model_inconsistency",
            "budget_exhausted",
            "evidence_conflict",
            "evidence_inconsistency",
            "approval_wait",
            "approval_denied",
            "stale_continuity_packet",
            "replay_mismatch",
            "branch_divergence",
        }
        severity = "recoverable" if incident_type in recoverable else "critical"
        report = IncidentReport(
            version="1.0",
            incident_id=f"incident-{uuid4().hex[:10]}",
            task_id=task_id,
            incident_type=incident_type,
            severity=severity,
            summary=summary,
            recovery_attempted=severity == "recoverable",
            resolution="pending",
            created_at=utc_now(),
        )
        self.failure_context[report.incident_id] = report
        if self.repository is not None:
            self.repository.save_incident(report)
        return report

    def mark_failure_context(self, incident_id: str, resolution: str) -> IncidentReport:
        """Update stored failure context after recovery handling."""

        report = self.failure_context[incident_id]
        report.resolution = resolution
        if self.repository is not None:
            self.repository.save_incident(report)
        return report

    def fork_branch(self, checkpoint_id: str, patch: dict[str, object]) -> dict[str, object]:
        """Create a branch state from an existing checkpoint."""

        state = dict(self.restore_checkpoint(checkpoint_id))
        state.update(patch)
        return state

    def latest_checkpoint(self, task_id: str) -> tuple[CheckpointRecord, dict[str, object]] | None:
        """Load the latest durable checkpoint for a task."""

        if self.repository is None:
            return None
        return self.repository.latest_checkpoint(task_id)
