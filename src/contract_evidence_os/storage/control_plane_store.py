"""Trusted-runtime collaboration and strategy repository facade."""

from __future__ import annotations

from contract_evidence_os.evolution.models import (
    StrategyFeedbackSignal,
    StrategyPromotionDecision,
    StrategyRollbackDecision,
)
from contract_evidence_os.storage._base import SQLiteSubstore
from contract_evidence_os.trusted_runtime.models import (
    CollaborationEvent,
    HandoffWindow,
    TaskBranch,
    TaskCollaborationBinding,
    TaskLease,
)


class SQLiteControlPlaneStore(SQLiteSubstore):
    """Own trusted-runtime control-plane persistence."""

    def save_task_collaboration_binding(self, record: TaskCollaborationBinding) -> None:
        self._save_runtime_state_record(
            "trusted_task_collaboration",
            record.binding_id,
            record.task_id,
            record.updated_at.isoformat(),
            record,
        )

    def load_task_collaboration_binding(self, task_id: str) -> TaskCollaborationBinding | None:
        records = self.list_task_collaboration_bindings(task_id=task_id)
        return None if not records else records[0]

    def list_task_collaboration_bindings(self, *, task_id: str | None = None) -> list[TaskCollaborationBinding]:
        return self._list_runtime_state_records("trusted_task_collaboration", TaskCollaborationBinding, scope_key=task_id)

    def save_task_lease(self, record: TaskLease) -> None:
        self._save_runtime_state_record("trusted_task_lease", record.lease_id, record.task_id, record.created_at.isoformat(), record)

    def list_task_leases(self, *, task_id: str | None = None) -> list[TaskLease]:
        return self._list_runtime_state_records("trusted_task_lease", TaskLease, scope_key=task_id)

    def save_task_branch(self, record: TaskBranch) -> None:
        self._save_runtime_state_record("trusted_task_branch", record.branch_id, record.task_id, record.created_at.isoformat(), record)

    def list_task_branches(self, *, task_id: str | None = None) -> list[TaskBranch]:
        return self._list_runtime_state_records("trusted_task_branch", TaskBranch, scope_key=task_id)

    def save_handoff_window(self, record: HandoffWindow) -> None:
        self._save_runtime_state_record("trusted_handoff_window", record.handoff_id, record.task_id, record.created_at.isoformat(), record)

    def list_handoff_windows(self, *, task_id: str | None = None) -> list[HandoffWindow]:
        return self._list_runtime_state_records("trusted_handoff_window", HandoffWindow, scope_key=task_id)

    def save_collaboration_event(self, record: CollaborationEvent) -> None:
        self._save_runtime_state_record("trusted_collaboration_event", record.event_id, record.task_id, record.created_at.isoformat(), record)

    def list_collaboration_events(self, *, task_id: str | None = None) -> list[CollaborationEvent]:
        return self._list_runtime_state_records("trusted_collaboration_event", CollaborationEvent, scope_key=task_id)

    def save_strategy_feedback_signal(self, record: StrategyFeedbackSignal) -> None:
        self._save_runtime_state_record("strategy_feedback_signal", record.signal_id, record.scope_key, record.created_at.isoformat(), record)

    def list_strategy_feedback_signals(self, *, scope_key: str | None = None) -> list[StrategyFeedbackSignal]:
        return self._list_runtime_state_records("strategy_feedback_signal", StrategyFeedbackSignal, scope_key=scope_key)

    def save_strategy_promotion_decision(self, record: StrategyPromotionDecision) -> None:
        self._save_runtime_state_record(
            "strategy_promotion_decision",
            record.decision_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_strategy_promotion_decisions(self, *, scope_key: str | None = None) -> list[StrategyPromotionDecision]:
        return self._list_runtime_state_records("strategy_promotion_decision", StrategyPromotionDecision, scope_key=scope_key)

    def save_strategy_rollback_decision(self, record: StrategyRollbackDecision) -> None:
        self._save_runtime_state_record(
            "strategy_rollback_decision",
            record.decision_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_strategy_rollback_decisions(self, *, scope_key: str | None = None) -> list[StrategyRollbackDecision]:
        return self._list_runtime_state_records("strategy_rollback_decision", StrategyRollbackDecision, scope_key=scope_key)
