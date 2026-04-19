"""Operator-facing API for long-horizon task inspection and control."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from contract_evidence_os.api.contracts import operator_api_contract
from contract_evidence_os.api.service import ContractEvidenceAPI
from contract_evidence_os.evals.models import StrategyEvaluationReport
from contract_evidence_os.observability.dashboard import build_task_dashboard


@dataclass
class OperatorAPI(ContractEvidenceAPI):
    """Operational facade over the runtime with continuity-aware surfaces."""

    def __init__(self, storage_root: Path, **kwargs) -> None:
        super().__init__(storage_root=storage_root, **kwargs)

    def task_status(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task_id": task_id,
            "status": task["status"],
            "current_phase": task["current_phase"],
            "latest_checkpoint_id": task["latest_checkpoint_id"],
        }

    def handoff_packet(self, task_id: str):
        handoff = self.handoff_packet_for_task(task_id)
        if handoff is None:
            raise KeyError(task_id)
        return handoff

    def handoff_packet_for_task(self, task_id: str):
        return super().handoff_packet(task_id)

    def open_questions(self, task_id: str):
        return super().open_questions(task_id)

    def next_actions(self, task_id: str):
        return super().next_actions(task_id)

    def checkpoints(self, task_id: str):
        return super().checkpoints(task_id)

    def continuity_working_set(self, task_id: str, role_name: str = "Strategist"):
        return super().continuity_working_set(task_id, role_name=role_name)

    def memory_state(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task_id": task_id,
            "raw_episodes": [item.to_dict() for item in self.raw_episodes(task_id=task_id)],
            "working_memory": None
            if self.memory.latest_working_memory_snapshot(task_id) is None
            else self.memory.latest_working_memory_snapshot(task_id).to_dict(),
            "semantic_facts": [item.to_dict() for item in self.temporal_semantic_facts(scope_key=task_id)],
            "dashboard": [item.to_dict() for item in self.memory_dashboard(task_id)],
            "artifacts": [item.to_dict() for item in self.memory.list_memory_artifacts(scope_key=task_id)],
        }

    def memory_evidence_pack(self, task_id: str, query: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().memory_evidence_pack(query=query, scope_key=task_id).to_dict()

    def memory_kernel_state(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().memory_kernel_state(scope_key=task_id)

    def consolidate_memory(self, task_id: str, reason: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return self.consolidate_memory_scope(scope_key=task_id, reason=reason).to_dict()

    def rebuild_memory(self, task_id: str, reason: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return self.rebuild_memory_scope(scope_key=task_id, reason=reason).to_dict()

    def selective_rebuild_memory(self, task_id: str, reason: str, target_kinds: list[str]) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().selective_rebuild_memory_scope(
            scope_key=task_id,
            reason=reason,
            target_kinds=target_kinds,
        ).to_dict()

    def memory_operations_loop(self, task_id: str, reason: str, interrupt_after: str | None = None) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().memory_operations_loop(
            scope_key=task_id,
            reason=reason,
            interrupt_after=interrupt_after,
        ).to_dict()

    def schedule_memory_operations_loop(
        self,
        task_id: str,
        cadence_hours: int,
        actor: str,
    ) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().schedule_memory_operations_loop(
            scope_key=task_id,
            cadence_hours=cadence_hours,
            actor=actor,
        ).to_dict()

    def resume_memory_operations_loop(self, loop_run_id: str, actor: str, reason: str) -> dict[str, Any]:
        return super().resume_memory_operations_loop(loop_run_id=loop_run_id, actor=actor, reason=reason).to_dict()

    def selective_purge_memory_scope(
        self,
        task_id: str,
        actor: str,
        reason: str,
        target_kinds: list[str],
    ) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        run = super().selective_purge_memory_scope(
            scope_key=task_id,
            actor=actor,
            reason=reason,
            target_kinds=target_kinds,
        )
        manifest = next(
            (item for item in self.memory.list_memory_purge_manifests(scope_key=task_id) if item.run_id == run.run_id),
            None,
        )
        payload = run.to_dict()
        payload["manifest"] = None if manifest is None else manifest.to_dict()
        return payload

    def hard_purge_memory_scope(
        self,
        task_id: str,
        actor: str,
        reason: str,
        target_kinds: list[str] | None = None,
    ) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        run = super().hard_purge_memory_scope(
            scope_key=task_id,
            actor=actor,
            reason=reason,
            target_kinds=target_kinds,
        )
        manifest = next(
            (item for item in self.memory.list_memory_purge_manifests(scope_key=task_id) if item.run_id == run.run_id),
            None,
        )
        payload = run.to_dict()
        payload["manifest"] = None if manifest is None else manifest.to_dict()
        return payload

    def memory_timeline(
        self,
        task_id: str,
        subject: str | None = None,
        predicate: str | None = None,
    ) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        segments = super().memory_timeline(
            scope_key=task_id,
            subject=subject,
            predicate=predicate,
        )
        return {
            "task_id": task_id,
            "segments": [segment.to_dict() for segment in segments],
        }

    def cross_scope_memory_timeline(
        self,
        scope_keys: list[str],
        subject: str,
        predicate: str,
    ) -> dict[str, Any]:
        segments = super().cross_scope_memory_timeline(
            scope_keys=scope_keys,
            subject=subject,
            predicate=predicate,
        )
        return {
            "scope_keys": scope_keys,
            "segments": [segment.to_dict() for segment in segments],
        }

    def memory_project_state(self, task_id: str, subject: str = "user") -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        snapshot = super().memory_project_state(scope_key=task_id, subject=subject)
        return {
            "task_id": task_id,
            "snapshot": snapshot.to_dict(),
        }

    def memory_artifacts(self, task_id: str, artifact_kind: str | None = None) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task_id": task_id,
            "items": [item.to_dict() for item in super().memory_artifacts(scope_key=task_id, artifact_kind=artifact_kind)],
        }

    def memory_artifact_health(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task_id": task_id,
            "items": [item.to_dict() for item in super().memory_artifact_health(scope_key=task_id)],
        }

    def memory_maintenance_drift(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task_id": task_id,
            "items": [item.to_dict() for item in super().memory_maintenance_drift(scope_key=task_id)],
        }

    def memory_maintenance_incidents(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task_id": task_id,
            "items": [item.to_dict() for item in super().memory_maintenance_incidents(scope_key=task_id)],
        }

    def memory_maintenance_mode(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().memory_maintenance_mode(scope_key=task_id)

    def memory_maintenance_workers(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task_id": task_id,
            "items": [item.to_dict() for item in super().memory_maintenance_workers()],
        }

    def register_maintenance_worker(self, task_id: str, worker_id: str, host_id: str, actor: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().register_maintenance_worker(
            worker_id=worker_id,
            host_id=host_id,
            actor=actor,
        ).to_dict()

    def run_maintenance_worker_cycle(self, worker_id: str, at_time: str | None = None, interrupt_after: str | None = None) -> dict[str, Any]:
        from datetime import datetime

        parsed = None if at_time is None else datetime.fromisoformat(at_time)
        return {
            "items": [
                item.to_dict()
                for item in super().run_maintenance_worker_cycle(
                    worker_id=worker_id,
                    at_time=parsed,
                    interrupt_after=interrupt_after,
                )
            ]
        }

    def resolve_maintenance_incident(self, task_id: str, incident_id: str, actor: str, resolution: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().resolve_maintenance_incident(
            incident_id=incident_id,
            actor=actor,
            resolution=resolution,
        ).to_dict()

    def memory_operations_diagnostics(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task_id": task_id,
            "diagnostics": super().memory_operations_diagnostics(scope_key=task_id).to_dict(),
        }

    def memory_admission_promotions(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task_id": task_id,
            "items": [item.to_dict() for item in super().memory_admission_promotions(scope_key=task_id)],
        }

    def memory_maintenance_recommendation(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task_id": task_id,
            "recommendation": super().memory_maintenance_recommendation(scope_key=task_id).to_dict(),
        }

    def background_memory_maintenance(self, task_id: str, actor: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task_id": task_id,
            "items": [item.to_dict() for item in super().background_memory_maintenance(scope_keys=[task_id], actor=actor)],
        }

    def schedule_background_maintenance(self, task_id: str, cadence_hours: int, actor: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().schedule_background_maintenance(
            scope_key=task_id,
            cadence_hours=cadence_hours,
            actor=actor,
        ).to_dict()

    def run_due_background_maintenance(self, at_time: str | None = None, interrupt_after: str | None = None) -> dict[str, Any]:
        from datetime import datetime

        parsed = None if at_time is None else datetime.fromisoformat(at_time)
        return {
            "items": [
                item.to_dict()
                for item in super().run_due_background_maintenance(
                    at_time=parsed,
                    interrupt_after=interrupt_after,
                )
            ]
        }

    def resume_background_maintenance(self, run_id: str, actor: str, reason: str) -> dict[str, Any]:
        return super().resume_background_maintenance(
            run_id=run_id,
            actor=actor,
            reason=reason,
        ).to_dict()

    def memory_maintenance_canary(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().memory_maintenance_canary(scope_key=task_id).to_dict()

    def memory_maintenance_promotions(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task_id": task_id,
            "items": [item.to_dict() for item in super().memory_maintenance_promotions(scope_key=task_id)],
        }

    def memory_maintenance_rollouts(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task_id": task_id,
            "items": [item.to_dict() for item in super().memory_maintenance_rollouts(scope_key=task_id)],
        }

    def apply_maintenance_promotion(self, task_id: str, recommendation_id: str, actor: str, reason: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().apply_maintenance_promotion(
            scope_key=task_id,
            recommendation_id=recommendation_id,
            actor=actor,
            reason=reason,
        ).to_dict()

    def rollback_maintenance_rollout(self, task_id: str, rollout_id: str, actor: str, reason: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().rollback_maintenance_rollout(
            rollout_id=rollout_id,
            actor=actor,
            reason=reason,
        ).to_dict()

    def memory_admission_canary(self, task_id: str, candidate_ids: list[str]) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().memory_admission_canary(scope_key=task_id, candidate_ids=candidate_ids).to_dict()

    def cross_scope_memory_repairs(
        self,
        scope_keys: list[str],
        subject: str,
        predicate: str,
    ) -> dict[str, Any]:
        records = super().memory_contradiction_repairs(
            scope_keys=scope_keys,
            subject=subject,
            predicate=predicate,
        )
        return {
            "scope_keys": scope_keys,
            "repairs": [item.to_dict() for item in records],
        }

    def cross_scope_memory_repair_canary(
        self,
        scope_keys: list[str],
        subject: str,
        predicate: str,
    ) -> dict[str, Any]:
        return super().memory_repair_canary(
            scope_keys=scope_keys,
            subject=subject,
            predicate=predicate,
        ).to_dict()

    def apply_cross_scope_memory_repair(self, repair_id: str, actor: str, reason: str) -> dict[str, Any]:
        return super().apply_memory_repair(repair_id=repair_id, actor=actor, reason=reason).to_dict()

    def rollback_cross_scope_memory_repair(self, repair_id: str, actor: str, reason: str) -> dict[str, Any]:
        return super().rollback_memory_repair(repair_id=repair_id, actor=actor, reason=reason).to_dict()

    def memory_policy_state(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().memory_policy_state(scope_key=task_id)

    def delete_memory_scope(self, task_id: str, actor: str, reason: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().delete_memory_scope(scope_key=task_id, actor=actor, reason=reason).to_dict()

    def trace_bundle(self, task_id: str) -> dict[str, Any]:
        return self.repository.export_trace_bundle(task_id)

    def task_dashboard(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        latest_incident = self.repository.list_incidents(task_id)
        handoff = self.handoff_packet_for_task(task_id)
        continuity = self.repository.latest_context_compaction(task_id)
        return build_task_dashboard(
            task=task,
            handoff_packet=None if handoff is None else handoff.to_dict(),
            open_questions=[item.to_dict() for item in self.open_questions(task_id)],
            next_actions=[item.to_dict() for item in self.next_actions(task_id)],
            approval_queue=[item.to_dict() for item in self.approval_inbox(task_id=task_id)],
            recent_failures=[item.to_dict() for item in latest_incident[-3:]],
            continuity_state=None if continuity is None else continuity.to_dict(),
        )

    def governance_state(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        execution_mode = self.repository.latest_execution_mode(task_id)
        budget_policy = self.repository.load_budget_policy(task_id)
        budget_ledger = self.repository.latest_budget_ledger(task_id)
        concurrency_state = self.repository.latest_concurrency_state(task_id)
        routing_decisions = self.repository.list_routing_decisions(task_id)
        return {
            "task_id": task_id,
            "execution_mode": None if execution_mode is None else execution_mode.to_dict(),
            "budget_policy": None if budget_policy is None else budget_policy.to_dict(),
            "budget_ledger": None if budget_ledger is None else budget_ledger.to_dict(),
            "provider_scorecards": [item.to_dict() for item in self.repository.list_provider_scorecards()],
            "tool_scorecards": [item.to_dict() for item in self.repository.list_tool_scorecards()],
            "routing_decisions": [item.to_dict() for item in routing_decisions],
            "governance_events": [item.to_dict() for item in self.repository.list_governance_events(task_id)],
            "concurrency_state": None if concurrency_state is None else concurrency_state.to_dict(),
            "degraded_mode_active": bool(execution_mode is not None and execution_mode.mode_name == "degraded"),
            "dominant_constraints": [] if execution_mode is None else execution_mode.active_constraints,
            "deferred_opportunities": [] if execution_mode is None else execution_mode.deferred_opportunities,
        }

    def control_governance(
        self,
        task_id: str,
        action: str,
        operator: str,
        reason: str,
        payload: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if self.repository.get_task(task_id) is None:
            raise KeyError(task_id)
        intervention = self.intervene_task(
            task_id=task_id,
            action=action,
            operator=operator,
            reason=reason,
            payload={} if payload is None else payload,
        )
        return {
            "status": "accepted",
            "task_id": task_id,
            "action": action,
            "intervention_id": intervention.intervention_id,
            "execution_mode": None
            if self.repository.latest_execution_mode(task_id) is None
            else self.repository.latest_execution_mode(task_id).to_dict(),
        }

    def queue_status(self) -> dict[str, Any]:
        return super().queue_status()

    def provider_health_state(self) -> dict[str, Any]:
        return super().provider_health_state()

    def software_harnesses(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.list_cli_anything_harnesses()],
            "bridges": [item.to_dict() for item in self.list_cli_anything_bridges()],
            "build_requests": [item.to_dict() for item in self.repository.list_software_build_requests("cli-anything")],
        }

    def software_harness_manifest(self, harness_id: str) -> dict[str, Any]:
        return {"manifest": super().software_harness_manifest(harness_id=harness_id).to_dict()}

    def software_action_receipts(
        self,
        task_id: str | None = None,
        harness_id: str | None = None,
        with_replay_diagnostics: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "items": [item.to_dict() for item in super().software_action_receipts(task_id=task_id, harness_id=harness_id)],
            "replays": [item.to_dict() for item in super().software_replay_records(task_id=task_id)],
            "failure_patterns": [item.to_dict() for item in super().software_failure_patterns(harness_id=harness_id)],
        }
        if with_replay_diagnostics:
            payload["replay_diagnostics"] = [
                item.to_dict() for item in super().software_replay_diagnostics(task_id=task_id, harness_id=harness_id)
            ]
        return payload

    def register_software_automation_macro(
        self,
        harness_id: str,
        actor: str,
        name: str,
        description: str,
        steps: list[dict[str, object]],
        automation_tags: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "macro": super().register_software_automation_macro(
                harness_id=harness_id,
                actor=actor,
                name=name,
                description=description,
                steps=steps,
                automation_tags=automation_tags,
            ).to_dict()
        }

    def invoke_software_automation_macro(
        self,
        macro_id: str,
        actor: str,
        task_id: str | None = None,
        approved: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if task_id is not None and self.repository.get_task(task_id) is None:
            raise KeyError(task_id)
        return super().invoke_software_automation_macro(
            macro_id=macro_id,
            actor=actor,
            task_id=task_id,
            approved=approved,
            dry_run=dry_run,
        )

    def software_harness_report(self, harness_id: str) -> dict[str, Any]:
        return {"report": super().software_harness_report(harness_id=harness_id)}

    def software_failure_clusters(self, harness_id: str | None = None) -> dict[str, Any]:
        return {"items": [item.to_dict() for item in super().software_failure_clusters(harness_id=harness_id)]}

    def software_recovery_hints(self, harness_id: str | None = None) -> dict[str, Any]:
        return {"items": [item.to_dict() for item in super().software_recovery_hints(harness_id=harness_id)]}

    def software_control_report(self) -> dict[str, Any]:
        return super().software_control_report()

    def api_contract(self) -> dict[str, Any]:
        return operator_api_contract()

    def policy_registry_state(self) -> dict[str, Any]:
        return super().policy_registry_state()

    def system_governance_state(self) -> dict[str, Any]:
        return super().system_governance_state()

    def system_report(self) -> dict[str, Any]:
        return super().system_report()

    def metrics_report(self) -> dict[str, Any]:
        return super().metrics_report()

    def metrics_history(self, window_hours: int = 24) -> dict[str, Any]:
        return super().metrics_history(window_hours=window_hours)

    def prometheus_metrics(self) -> str:
        return super().prometheus_metrics()

    def maintenance_report(self, task_id: str | None = None) -> dict[str, Any]:
        if task_id is not None and self.repository.get_task(task_id) is None:
            raise KeyError(task_id)
        return super().maintenance_report(task_id=task_id)

    def maintenance_daemon_state(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return super().maintenance_daemon_state(task_id=task_id)

    def run_resident_maintenance_daemon(
        self,
        task_id: str,
        worker_id: str,
        host_id: str,
        actor: str,
        daemon: bool = False,
        once: bool = False,
        poll_interval_seconds: int = 0,
        heartbeat_seconds: int = 30,
        lease_seconds: int = 300,
        max_cycles: int = 1,
        cycles: int | None = None,
        interrupt_after: str | None = None,
    ) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        payload = super().run_resident_maintenance_daemon(
            worker_id=worker_id,
            host_id=host_id,
            actor=actor,
            task_id=task_id,
            daemon=daemon,
            once=once,
            poll_interval_seconds=poll_interval_seconds,
            heartbeat_seconds=heartbeat_seconds,
            lease_seconds=lease_seconds,
            max_cycles=max_cycles,
            cycles=cycles,
            interrupt_after=interrupt_after,
        )
        payload["task_id"] = task_id
        return payload

    def startup_validation(self) -> dict[str, Any]:
        return super().startup_validation_summary()

    def graceful_shutdown(self, reason: str = "operator requested shutdown drain") -> dict[str, Any]:
        return super().graceful_shutdown(reason=reason)

    def restart_recovery(self) -> dict[str, Any]:
        return super().restart_recovery()

    def evaluate_policy_candidate_remote(self, candidate_id: str, metrics: dict[str, float]) -> dict[str, Any]:
        report = StrategyEvaluationReport(strategy_name=f"candidate:{candidate_id}", metrics=metrics)
        return self.evaluate_policy_candidate(candidate_id, report).to_dict()

    def promote_policy_candidate_remote(self, candidate_id: str) -> dict[str, Any]:
        return self.promote_policy_candidate(candidate_id).to_dict()

    def rollback_policy_scope_remote(self, scope_id: str, reason: str) -> dict[str, Any]:
        return self.rollback_policy_scope(scope_id, reason).to_dict()

    def control_system_governance(
        self,
        action: str,
        operator: str,
        reason: str,
        payload: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload = {} if payload is None else payload
        idempotency_key = payload.get("idempotency_key", "")
        existing = self.repository.find_operator_override(idempotency_key)
        if existing is not None:
            return {
                "status": "accepted",
                "override_id": existing.override_id,
                "system_mode": None
                if self.repository.latest_global_execution_mode() is None
                else self.repository.latest_global_execution_mode().to_dict(),
            }
        override = self.apply_operator_override(action=action, operator=operator, reason=reason, payload=payload)
        return {
            "status": "accepted",
            "override_id": override.override_id,
            "system_mode": None
            if self.repository.latest_global_execution_mode() is None
            else self.repository.latest_global_execution_mode().to_dict(),
        }
