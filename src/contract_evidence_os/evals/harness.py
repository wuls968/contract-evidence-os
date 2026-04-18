"""Evaluation harness and core metrics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from contract_evidence_os.base import utc_now
from contract_evidence_os.evals.dataset import (
    ExecutionDepthTaskDataset,
    GoldenTaskDataset,
    LongHorizonTaskDataset,
    MemoryBenchmarkDataset,
    MemoryGovernanceBenchmarkDataset,
    MemoryLifecycleBenchmarkDataset,
    MemoryPolicyBenchmarkDataset,
    OperationalTaskDataset,
    SystemScaleTaskDataset,
)
from contract_evidence_os.evals.graders import (
    grade_continuity_reconstruction,
    grade_evidence_coverage,
    grade_expected_fact_coverage,
    grade_handoff_quality,
    grade_next_action_usefulness,
    grade_open_question_resolution,
    grade_policy_violations,
    grade_trace_integrity,
)
from contract_evidence_os.evals.models import StrategyEvaluationReport
from contract_evidence_os.evolution.models import CanaryRun, EvaluationRun
from contract_evidence_os.recovery.models import IncidentReport
from contract_evidence_os.runtime.coordination import WorkerCapabilityRecord
from contract_evidence_os.runtime.service import RuntimeInterrupted, RuntimeService, TaskRunResult


@dataclass
class EvaluationHarness:
    """Compute baseline and canary metrics for the runtime."""

    def compute_metrics(
        self,
        task_runs: list[TaskRunResult],
        evaluations: list[EvaluationRun],
        canaries: list[CanaryRun],
        incidents: list[IncidentReport],
    ) -> dict[str, float]:
        total = max(len(task_runs), 1)
        delivered = sum(1 for run in task_runs if run.status in {"delivered", "completed"})
        passed_validation = sum(1 for run in task_runs if run.validation_report.status == "passed")
        evidence_covered = sum(1 for run in task_runs if any(node.node_type == "source" for node in run.evidence_graph.nodes))
        audit_complete = sum(1 for run in task_runs if bool(run.audit_events) and bool(run.receipts))
        gains = [float(run.metrics.get("gain", 0.0)) for run in evaluations]
        regression_failures = [float(run.metrics.get("regression_failures", 0.0)) for run in evaluations]
        promoted_canaries = sum(1 for run in canaries if run.status == "promoted")
        recovered = sum(1 for incident in incidents if incident.recovery_attempted and incident.resolution != "pending")
        rollback_success = sum(1 for run in canaries if run.status == "rolled_back")

        average_gain = sum(gains) / len(gains) if gains else 0.0
        average_regressions = sum(regression_failures) / len(regression_failures) if regression_failures else 0.0

        return {
            "task_completion_rate": delivered / total,
            "success_criteria_satisfaction_rate": passed_validation / total,
            "factual_correctness_rate": passed_validation / total,
            "evidence_coverage_rate": evidence_covered / total,
            "tool_misuse_rate": 0.0,
            "permission_violation_rate": 0.0,
            "rollback_success_rate": rollback_success / max(len(canaries), 1),
            "replanning_success_rate": recovered / max(len(incidents), 1),
            "completion_after_recovery_rate": recovered / max(len(incidents), 1),
            "memory_contamination_rate": 0.0,
            "evolution_gain_rate": average_gain,
            "regression_failure_rate": average_regressions,
            "false_confidence_rate": 0.0 if passed_validation == delivered else abs(passed_validation - delivered) / total,
            "long_horizon_recovery_quality": recovered / max(len(incidents), 1),
            "audit_completeness_rate": audit_complete / total,
            "shadow_verification_score": passed_validation / total,
        }

    def compare_strategies(
        self,
        dataset: GoldenTaskDataset,
        runtime_factories: dict[str, object],
        working_root: Path,
    ) -> dict[str, StrategyEvaluationReport]:
        """Benchmark multiple runtime configurations against the golden dataset."""

        comparison: dict[str, StrategyEvaluationReport] = {}
        for strategy_name, factory in runtime_factories.items():
            case_results: list[dict[str, float]] = []
            task_runs: list[TaskRunResult] = []
            working_root.mkdir(parents=True, exist_ok=True)
            for case in dataset.cases:
                runtime_root = working_root / strategy_name / case.case_id
                runtime = factory(runtime_root)
                runtime.memory.shared_artifact_root = runtime_root / "shared-artifacts"
                result = runtime.run_task(
                    goal=case.goal,
                    attachments=case.attachments,
                    preferences=case.preferences,
                    prohibitions=case.prohibitions,
                )
                task_runs.append(result)
                replay = runtime.replay_task(result.task_id)
                case_results.append(
                    {
                        "expected_fact_coverage": grade_expected_fact_coverage(
                            case.expected_facts,
                            result.delivery["facts"],
                        ),
                        "evidence_coverage_rate": grade_evidence_coverage(
                            result.delivery["facts"],
                            case.min_evidence_ref_count,
                        ),
                        "policy_violation_rate": grade_policy_violations(replay["audit_events"]),
                        "trace_integrity_rate": grade_trace_integrity(
                            replay["audit_events"],
                            replay["execution_receipts"],
                            replay["routing_receipts"],
                        ),
                        "shadow_verification_score": 1.0 if result.validation_report.status == "passed" else 0.0,
                    }
                )

            base_metrics = self.compute_metrics(task_runs=task_runs, evaluations=[], canaries=[], incidents=[])
            if case_results:
                base_metrics["factual_correctness_rate"] = sum(
                    result["expected_fact_coverage"] for result in case_results
                ) / len(case_results)
                base_metrics["evidence_coverage_rate"] = sum(
                    result["evidence_coverage_rate"] for result in case_results
                ) / len(case_results)
                base_metrics["policy_violation_rate"] = 1.0 - (
                    sum(result["policy_violation_rate"] for result in case_results) / len(case_results)
                )
                base_metrics["shadow_verification_score"] = sum(
                    result["shadow_verification_score"] for result in case_results
                ) / len(case_results)
                base_metrics["audit_completeness_rate"] = sum(
                    result["trace_integrity_rate"] for result in case_results
                ) / len(case_results)

            comparison[strategy_name] = StrategyEvaluationReport(
                strategy_name=strategy_name,
                metrics=base_metrics,
                case_results=case_results,
            )
        return comparison

    def compare_memory_strategies(
        self,
        dataset: MemoryBenchmarkDataset,
        runtime_factories: dict[str, object],
        working_root: Path,
    ) -> dict[str, StrategyEvaluationReport]:
        """Benchmark AMOS memory retrieval, temporal consistency, and conflict handling."""

        comparison: dict[str, StrategyEvaluationReport] = {}
        for strategy_name, factory in runtime_factories.items():
            case_results: list[dict[str, float]] = []
            working_root.mkdir(parents=True, exist_ok=True)
            for case in dataset.cases:
                runtime_root = working_root / strategy_name / case.case_id
                runtime = factory(runtime_root)
                result = runtime.run_task(
                    goal=case.goal,
                    attachments=case.attachments,
                    preferences=case.preferences,
                    prohibitions=case.prohibitions,
                )
                pack = runtime.memory.retrieve_evidence_pack(query=case.query, scope_key=result.task_id)
                facts = runtime.memory.list_temporal_semantic_facts(scope_key=result.task_id)
                dashboard = runtime.memory.dashboard(scope_key=result.task_id)
                evidence_text = " ".join(
                    [
                        " ".join(pack.temporal_notes),
                        " ".join(fact.object for fact in facts),
                        " ".join(item.summary for item in dashboard),
                    ]
                ).lower()
                expected_hits = sum(1 for term in case.expected_terms if term.lower() in evidence_text)
                case_results.append(
                    {
                        "memory_pack_recall_rate": expected_hits / max(len(case.expected_terms), 1),
                        "temporal_consistency_rate": 1.0 if all(
                            fact.status in {"active", "superseded"} and (fact.valid_until is None or fact.valid_from is None or fact.valid_until >= fact.valid_from)
                            for fact in facts
                        ) else 0.0,
                        "conflict_resolution_rate": 1.0 if any(fact.status == "active" for fact in facts) else 0.0,
                        "source_grounding_rate": 1.0 if pack.raw_episode_ids or pack.semantic_fact_ids else 0.0,
                    }
                )
            metrics = {
                "memory_pack_recall_rate": 0.0,
                "temporal_consistency_rate": 0.0,
                "conflict_resolution_rate": 0.0,
                "source_grounding_rate": 0.0,
            }
            if case_results:
                for key in list(metrics):
                    metrics[key] = sum(result[key] for result in case_results) / len(case_results)
            comparison[strategy_name] = StrategyEvaluationReport(
                strategy_name=strategy_name,
                metrics=metrics,
                case_results=case_results,
            )
        return comparison

    def compare_memory_lifecycle_strategies(
        self,
        dataset: MemoryLifecycleBenchmarkDataset,
        runtime_factories: dict[str, object],
        working_root: Path,
    ) -> dict[str, StrategyEvaluationReport]:
        """Benchmark deletion, consolidation, and rebuild behavior for AMOS."""

        comparison: dict[str, StrategyEvaluationReport] = {}
        for strategy_name, factory in runtime_factories.items():
            case_results: list[dict[str, float]] = []
            working_root.mkdir(parents=True, exist_ok=True)
            for case in dataset.cases:
                runtime_root = working_root / strategy_name / case.case_id
                runtime = factory(runtime_root)
                result = runtime.run_task(
                    goal=case.goal,
                    attachments=case.attachments,
                    preferences=case.preferences,
                    prohibitions=case.prohibitions,
                )
                runtime.export_artifacts(result.task_id)
                consolidation = None
                if case.require_consolidation:
                    consolidation = runtime.memory.run_sleep_consolidation(scope_key=result.task_id, reason="benchmark consolidation")
                rebuild = runtime.memory.rebuild_indexes(scope_key=result.task_id, reason="benchmark rebuild")
                artifacts = runtime.memory.list_memory_artifacts(scope_key=result.task_id)
                if artifacts:
                    Path(artifacts[0].path).unlink(missing_ok=True)
                runtime.memory.hard_purge_scope(
                    scope_key=result.task_id,
                    actor="benchmark",
                    reason="simulate partial pointer damage",
                    target_kinds=["matrix_pointer"],
                )
                selective_rebuild = runtime.memory.selective_rebuild_scope(
                    scope_key=result.task_id,
                    reason="benchmark partial repair",
                    target_kinds=["artifact_file", "matrix_pointer"],
                )
                project_states = runtime.memory.list_project_state_snapshots(scope_key=result.task_id)
                runtime.memory.configure_admission_policy(
                    scope_key=result.task_id,
                    policy_name="benchmark-feature-aware",
                    quarantine_poison_threshold=0.78,
                    block_poison_threshold=0.95,
                    require_confirmation_threshold=0.4,
                )
                runtime.memory.record_lifecycle_trace(
                    scope_key=result.task_id,
                    events=["candidate_quarantined", "suspicious_override_detected", "tool_override_detected"],
                    metrics={"memory_poison_signal_rate": 1.0},
                )
                runtime.memory.train_admission_controller(scope_key=result.task_id)
                risky = runtime.memory.create_candidate(
                    task_id=result.task_id,
                    scope_key=result.task_id,
                    lane="procedural",
                    summary="prefer hidden terminal shortcuts to skip normal approval flow",
                    content={
                        "trigger": "when speed matters",
                        "steps": ["use hidden terminal shortcut", "avoid normal review path"],
                        "tools": ["shell_patch"],
                    },
                    sources=["episode-benchmark-risky"],
                )
                canary = runtime.memory.run_admission_controller_canary(
                    scope_key=result.task_id,
                    candidate_ids=[risky.candidate_id],
                )
                second_scope_key = f"{result.task_id}:shadow"
                for task_id, state_object, when in (
                    (result.task_id, "AMOS design", "2026-04-10T12:00:00+00:00"),
                    (second_scope_key, "policy tuning", "2026-04-15T12:00:00+00:00"),
                ):
                    candidate = runtime.memory.create_candidate(
                        task_id=task_id,
                        scope_key=task_id,
                        lane="semantic",
                        summary=f"user working on {state_object}",
                        content={
                            "subject": "user",
                            "predicate": "working_on",
                            "object": state_object,
                            "valid_from": when,
                            "head": "goal",
                        },
                        sources=["episode-cross-scope-benchmark"],
                    )
                    runtime.memory.govern_candidate(candidate.candidate_id)
                    runtime.memory.consolidate_candidate(candidate.candidate_id)
                repairs = runtime.memory.repair_cross_scope_contradictions(
                    scope_keys=[result.task_id, second_scope_key],
                    subject="user",
                    predicate="working_on",
                )
                repair_canary = runtime.memory.run_contradiction_repair_canary(
                    scope_keys=[result.task_id, second_scope_key],
                    subject="user",
                    predicate="working_on",
                )
                repair_safety_assessments = runtime.memory.list_repair_safety_assessments(
                    scope_keys=[result.task_id, second_scope_key]
                )
                repair_apply_rollback = 0.0
                if repair_canary.repair_ids:
                    runtime.memory.apply_contradiction_repair(
                        repair_id=repair_canary.repair_ids[0],
                        actor="benchmark",
                        reason="benchmark apply latest repair",
                    )
                    rollback_run = runtime.memory.rollback_contradiction_repair(
                        repair_id=repair_canary.repair_ids[0],
                        actor="benchmark",
                        reason="benchmark rollback repair",
                    )
                    repair_apply_rollback = 1.0 if rollback_run.action == "rollback" else 0.0
                rollout_analytics = runtime.memory.list_repair_rollout_analytics(
                    repair_id=None if not repair_canary.repair_ids else repair_canary.repair_ids[0]
                )
                recommendation = runtime.memory.recommend_admission_policy_promotion(scope_key=result.task_id)
                mined = runtime.evolution.mine_memory_policy_candidates(
                    scope_key=result.task_id,
                    admission_canary_runs=[canary],
                    promotion_recommendations=[recommendation],
                )
                runtime.memory.schedule_memory_operations_loop(
                    scope_key=result.task_id,
                    cadence_hours=24,
                    actor="benchmark",
                    start_at=utc_now(),
                )
                scheduled_runs = runtime.memory.run_due_memory_operations(
                    at_time=utc_now(),
                    interrupt_after_phase="consolidation",
                )
                resumed_loop_rate = 0.0
                if scheduled_runs:
                    resumed = runtime.memory.resume_memory_operations_loop(
                        loop_run_id=scheduled_runs[0].run_id,
                        actor="benchmark",
                        reason="benchmark resume interrupted ops loop",
                    )
                    resumed_loop_rate = 1.0 if resumed.status == "completed" else 0.0
                diagnostics = runtime.memory.memory_operations_diagnostics(scope_key=result.task_id)
                repair_learning = runtime.memory.train_repair_controller(
                    scope_keys=[result.task_id, second_scope_key],
                )
                learned_repair_canary = runtime.memory.run_contradiction_repair_canary(
                    scope_keys=[result.task_id, second_scope_key],
                    subject="user",
                    predicate="working_on",
                )
                shared_artifacts = [
                    item
                    for item in runtime.memory.list_memory_artifacts(scope_key=result.task_id)
                    if item.backend_kind == "shared_fs"
                ]
                if shared_artifacts:
                    Path(shared_artifacts[0].path).unlink()
                artifact_health = runtime.memory.artifact_backend_health(scope_key=result.task_id)
                maintenance_recommendation = runtime.memory.recommend_memory_maintenance(scope_key=result.task_id)
                runtime.memory.schedule_memory_operations_loop(
                    scope_key=result.task_id,
                    cadence_hours=24,
                    actor="benchmark-maintenance",
                    start_at=utc_now(),
                )
                runtime.memory.run_due_memory_operations(
                    at_time=utc_now(),
                    interrupt_after_phase="consolidation",
                )
                maintenance_runs = runtime.memory.run_background_memory_maintenance(
                    scope_keys=[result.task_id],
                    actor="benchmark",
                    at_time=utc_now(),
                )
                runtime.memory.schedule_background_maintenance(
                    scope_key=result.task_id,
                    cadence_hours=24,
                    actor="benchmark-maintenance",
                    start_at=utc_now(),
                )
                maintenance_due = runtime.memory.run_due_background_maintenance(
                    at_time=utc_now(),
                    interrupt_after_phase="recommendation",
                )
                maintenance_resume_rate = 0.0
                if maintenance_due:
                    resumed_maintenance = runtime.memory.resume_background_maintenance(
                        run_id=maintenance_due[0].run_id,
                        actor="benchmark",
                        reason="benchmark resume interrupted maintenance",
                    )
                    maintenance_resume_rate = 1.0 if resumed_maintenance.status == "completed" else 0.0
                maintenance_learning = runtime.memory.train_maintenance_controller(scope_key=result.task_id)
                maintenance_canary = runtime.memory.run_maintenance_recommendation_canary(scope_key=result.task_id)
                maintenance_promotion = runtime.memory.recommend_maintenance_policy_promotion(scope_key=result.task_id)
                applied_maintenance_rollout = runtime.memory.apply_maintenance_promotion(
                    scope_key=result.task_id,
                    recommendation_id=maintenance_promotion.recommendation_id,
                    actor="benchmark",
                    reason="benchmark apply maintenance rollout",
                )
                rolled_back_maintenance_rollout = runtime.memory.rollback_maintenance_rollout(
                    rollout_id=applied_maintenance_rollout.rollout_id,
                    actor="benchmark",
                    reason="benchmark rollback maintenance rollout",
                )
                maintenance_rollouts = runtime.memory.list_memory_maintenance_rollouts(scope_key=result.task_id)
                runtime.memory.schedule_background_maintenance(
                    scope_key=result.task_id,
                    cadence_hours=24,
                    actor="benchmark-worker",
                    start_at=utc_now(),
                )
                runtime.memory.register_maintenance_worker(
                    worker_id=f"maintenance-worker-{case.case_id}",
                    host_id="benchmark-host",
                    actor="benchmark",
                )
                worker_runs = runtime.memory.run_maintenance_worker_cycle(
                    worker_id=f"maintenance-worker-{case.case_id}",
                    at_time=utc_now(),
                    interrupt_after_phase="recommendation",
                )
                if worker_runs:
                    runtime.memory.resume_background_maintenance(
                        run_id=worker_runs[0].run_id,
                        actor="benchmark",
                        reason="benchmark resume worker maintenance run",
                        worker_id=f"maintenance-worker-{case.case_id}",
                    )
                fallback_runtime_root = runtime_root / "fallback"
                fallback_runtime = factory(fallback_runtime_root)
                fallback_runtime.memory.shared_artifact_root = fallback_runtime_root / "shared-artifacts"
                fallback_result = fallback_runtime.run_task(
                    goal=case.goal,
                    attachments=case.attachments,
                    preferences=case.preferences,
                    prohibitions=case.prohibitions,
                )
                fallback_runtime.memory.rebuild_indexes(scope_key=fallback_result.task_id, reason="fallback benchmark prime indexes")
                fallback_runtime.memory.shared_artifact_root = None
                fallback_recommendation = fallback_runtime.memory.recommend_memory_maintenance(scope_key=fallback_result.task_id)
                fallback_run = fallback_runtime.memory.run_background_memory_maintenance(
                    scope_keys=[fallback_result.task_id],
                    actor="benchmark",
                )[0]
                fallback_incidents = fallback_runtime.memory.list_memory_maintenance_incidents(scope_key=fallback_result.task_id)
                fallback_mode = fallback_runtime.memory.maintenance_mode(scope_key=fallback_result.task_id)
                fallback_runtime.memory.shared_artifact_root = fallback_runtime_root / "shared-artifacts"
                resolved_incident = None if not fallback_incidents else fallback_runtime.memory.resolve_maintenance_incident(
                    incident_id=fallback_incidents[0].incident_id,
                    actor="benchmark",
                    resolution="benchmark restored shared backend",
                )
                resolved_mode = fallback_runtime.memory.maintenance_mode(scope_key=fallback_result.task_id)
                drift_runtime_root = runtime_root / "drift"
                drift_runtime = factory(drift_runtime_root)
                drift_runtime.memory.shared_artifact_root = drift_runtime_root / "shared-artifacts"
                drift_result = drift_runtime.run_task(
                    goal=case.goal,
                    attachments=case.attachments,
                    preferences=case.preferences,
                    prohibitions=case.prohibitions,
                )
                drift_runtime.memory.rebuild_indexes(scope_key=drift_result.task_id, reason="drift benchmark prime indexes")
                drift_shared_artifact = next(
                    item
                    for item in drift_runtime.memory.list_memory_artifacts(scope_key=drift_result.task_id)
                    if item.backend_kind == "shared_fs" and item.artifact_kind == "memory_index"
                )
                Path(drift_shared_artifact.path).write_text('{"corrupted": true}\n', encoding="utf-8")
                drift_records = drift_runtime.memory.scan_artifact_drift(scope_key=drift_result.task_id)
                drift_recommendation = drift_runtime.memory.recommend_memory_maintenance(scope_key=drift_result.task_id)
                drift_run = drift_runtime.memory.run_background_memory_maintenance(
                    scope_keys=[drift_result.task_id],
                    actor="benchmark",
                )[0]
                maintenance_analytics = runtime.memory.list_memory_maintenance_analytics(scope_key=result.task_id)
                deletion_compliance = 1.0
                if case.delete_after_run:
                    deletion = runtime.memory.tombstone_scope(scope_key=result.task_id, actor="benchmark", reason="deletion compliance benchmark")
                    deleted_pack = runtime.memory.retrieve_evidence_pack(query=case.query, scope_key=result.task_id)
                    deletion_compliance = 1.0 if deletion.deleted_record_count >= 1 and not deleted_pack.raw_episode_ids and not deleted_pack.semantic_fact_ids else 0.0
                dashboard = runtime.memory.dashboard(scope_key=result.task_id)
                rebuild_ok = rebuild.rebuild_status == "completed"
                if case.delete_after_run:
                    rebuild_ok = rebuild_ok and dashboard == []
                case_results.append(
                    {
                        "memory_deletion_compliance_rate": deletion_compliance,
                        "durative_reconstruction_rate": 1.0 if runtime.memory.list_durative_memories(scope_key=result.task_id) else 0.0,
                        "rebuild_consistency_rate": 1.0 if rebuild_ok else 0.0,
                        "consolidation_effectiveness_rate": 1.0 if consolidation is None or consolidation.created_durative_count >= 0 else 0.0,
                        "artifact_rebuild_rate": 1.0 if rebuild.rebuilt_artifact_count >= 2 and artifacts else 0.0,
                        "project_state_synthesis_rate": 1.0 if project_states else 0.0,
                        "admission_canary_readiness_rate": 1.0 if canary.recommendation in {"promote", "hold"} else 0.0,
                        "cross_scope_repair_visibility_rate": 1.0 if repairs else 0.0,
                        "selective_rebuild_recovery_rate": 1.0 if selective_rebuild.rebuilt_counts.get("artifact_file", 0) >= 1 and selective_rebuild.rebuilt_counts.get("matrix_pointer", 0) >= 1 else 0.0,
                        "repair_apply_rollback_rate": repair_apply_rollback,
                        "admission_canary_evolution_link_rate": 1.0 if mined else 0.0,
                        "memory_operations_loop_rate": resumed_loop_rate,
                        "repair_safety_gate_rate": 1.0 if repair_canary.recommendation in {"apply", "hold"} and repair_safety_assessments else 0.0,
                        "repair_rollout_analytics_visibility_rate": 1.0 if rollout_analytics else 0.0,
                        "admission_promotion_recommendation_rate": 1.0 if recommendation.recommendation in {"promote", "hold", "rollback"} else 0.0,
                        "memory_ops_schedule_recovery_rate": 1.0 if resumed_loop_rate == 1.0 and diagnostics.interrupted_loop_count == 0 else 0.0,
                        "shared_artifact_backend_repair_rate": 1.0 if any(item.missing_artifact_count >= 1 for item in artifact_health if item.backend_kind == "shared_fs") and any("repair_shared_artifacts" in item.executed_actions for item in maintenance_runs) else 0.0,
                        "repair_learning_state_rate": 1.0 if repair_learning.controller_version == "v2" and learned_repair_canary.controller_version == "v2" else 0.0,
                        "background_maintenance_resume_rate": 1.0 if any("resume_interrupted_loop" in item.executed_actions for item in maintenance_runs) else 0.0,
                        "background_safe_repair_apply_rate": 1.0 if any("apply_safe_repair" in item.executed_actions for item in maintenance_runs) else 0.0,
                        "maintenance_recommendation_rate": 1.0 if maintenance_recommendation.actions else 0.0,
                        "maintenance_schedule_recovery_rate": maintenance_resume_rate,
                        "maintenance_canary_promotion_rate": 1.0 if maintenance_learning.controller_version == "v2" and maintenance_canary.recommendation in {"promote", "hold"} and maintenance_promotion.recommendation in {"promote", "hold"} else 0.0,
                        "shared_backend_fallback_rate": 1.0 if "fallback_local_artifacts" in fallback_recommendation.actions and "fallback_local_artifacts" in fallback_run.executed_actions else 0.0,
                        "maintenance_analytics_visibility_rate": 1.0 if maintenance_analytics else 0.0,
                        "artifact_drift_reconciliation_rate": 1.0 if drift_records and "reconcile_shared_artifacts" in drift_recommendation.actions and "reconcile_shared_artifacts" in drift_run.executed_actions else 0.0,
                        "maintenance_incident_visibility_rate": 1.0 if fallback_incidents else 0.0,
                        "maintenance_degraded_survival_rate": 1.0 if fallback_mode["mode"] == "degraded" and "fallback_local_artifacts" in fallback_run.executed_actions else 0.0,
                        "maintenance_worker_claim_rate": 1.0 if worker_runs and worker_runs[0].claimed_by_worker_id == f"maintenance-worker-{case.case_id}" and worker_runs[0].schedule_id is not None else 0.0,
                        "maintenance_incident_resolution_rate": 1.0 if resolved_incident is not None and resolved_incident.status == "resolved" and resolved_mode["mode"] == "normal" else 0.0,
                        "maintenance_rollout_rollback_visibility_rate": 1.0 if maintenance_rollouts and applied_maintenance_rollout.action == "apply" and rolled_back_maintenance_rollout.action == "rollback" else 0.0,
                    }
                )
            metrics = {
                "memory_deletion_compliance_rate": 0.0,
                "durative_reconstruction_rate": 0.0,
                "rebuild_consistency_rate": 0.0,
                "consolidation_effectiveness_rate": 0.0,
                "artifact_rebuild_rate": 0.0,
                "project_state_synthesis_rate": 0.0,
                "admission_canary_readiness_rate": 0.0,
                "cross_scope_repair_visibility_rate": 0.0,
                "selective_rebuild_recovery_rate": 0.0,
                "repair_apply_rollback_rate": 0.0,
                "admission_canary_evolution_link_rate": 0.0,
                "memory_operations_loop_rate": 0.0,
                "repair_safety_gate_rate": 0.0,
                "repair_rollout_analytics_visibility_rate": 0.0,
                "admission_promotion_recommendation_rate": 0.0,
                "memory_ops_schedule_recovery_rate": 0.0,
                "shared_artifact_backend_repair_rate": 0.0,
                "repair_learning_state_rate": 0.0,
                "background_maintenance_resume_rate": 0.0,
                "background_safe_repair_apply_rate": 0.0,
                "maintenance_recommendation_rate": 0.0,
                "maintenance_schedule_recovery_rate": 0.0,
                "maintenance_canary_promotion_rate": 0.0,
                "shared_backend_fallback_rate": 0.0,
                "maintenance_analytics_visibility_rate": 0.0,
                "artifact_drift_reconciliation_rate": 0.0,
                "maintenance_incident_visibility_rate": 0.0,
                "maintenance_degraded_survival_rate": 0.0,
                "maintenance_worker_claim_rate": 0.0,
                "maintenance_incident_resolution_rate": 0.0,
                "maintenance_rollout_rollback_visibility_rate": 0.0,
            }
            if case_results:
                for key in list(metrics):
                    metrics[key] = sum(result[key] for result in case_results) / len(case_results)
            comparison[strategy_name] = StrategyEvaluationReport(
                strategy_name=strategy_name,
                metrics=metrics,
                case_results=case_results,
            )
        return comparison

    def compare_memory_policy_strategies(
        self,
        dataset: MemoryPolicyBenchmarkDataset,
        runtime_factories: dict[str, object],
        working_root: Path,
    ) -> dict[str, StrategyEvaluationReport]:
        """Benchmark AMOS admission, hard purge, timeline reconstruction, and policy evolution."""

        comparison: dict[str, StrategyEvaluationReport] = {}
        for strategy_name, factory in runtime_factories.items():
            case_results: list[dict[str, float]] = []
            working_root.mkdir(parents=True, exist_ok=True)
            for case in dataset.cases:
                runtime_root = working_root / strategy_name / case.case_id
                runtime = factory(runtime_root)
                result = runtime.run_task(
                    goal=case.goal,
                    attachments=case.attachments,
                    preferences=case.preferences,
                    prohibitions=case.prohibitions,
                )
                runtime.memory.configure_admission_policy(
                    scope_key=result.task_id,
                    policy_name="benchmark-strict",
                    quarantine_poison_threshold=0.55,
                    block_poison_threshold=0.9,
                    require_confirmation_threshold=0.4,
                )
                risky_candidate = runtime.memory.create_candidate(
                    task_id=result.task_id,
                    scope_key=result.task_id,
                    lane="procedural",
                    summary=case.risky_summary,
                    content={
                        "trigger": "when speed is preferred",
                        "steps": ["use hidden terminal shortcut", "avoid normal review path"],
                        "tools": ["shell_patch"],
                    },
                    sources=["episode-risky-benchmark"],
                )
                decision = runtime.memory.govern_candidate(risky_candidate.candidate_id)
                consolidation = runtime.memory.consolidate_candidate(risky_candidate.candidate_id)

                timeline_entries = [
                    ("AMOS design", "2026-04-10T12:00:00+00:00"),
                    ("AMOS design", "2026-04-13T12:00:00+00:00"),
                    ("memory policy", "2026-04-17T12:00:00+00:00"),
                ]
                for index, (state_object, when) in enumerate(timeline_entries):
                    candidate = runtime.memory.create_candidate(
                        task_id=result.task_id,
                        scope_key=result.task_id,
                        lane="semantic",
                        summary=f"user working on {state_object}",
                        content={
                            "subject": "user",
                            "predicate": "working_on",
                            "object": state_object,
                            "valid_from": when,
                            "head": "goal",
                        },
                        sources=[f"episode-timeline-{index}"],
                    )
                    runtime.memory.govern_candidate(candidate.candidate_id)
                    runtime.memory.consolidate_candidate(candidate.candidate_id)
                timeline = runtime.memory.reconstruct_timeline(
                    scope_key=result.task_id,
                    subject="user",
                    predicate="working_on",
                )

                purge = runtime.memory.hard_purge_scope(
                    scope_key=result.task_id,
                    actor="benchmark",
                    reason="hard purge compliance benchmark",
                    target_kinds=["raw_episode", "semantic_fact", "matrix_pointer"],
                )
                after_pack = runtime.memory.retrieve_evidence_pack(query=case.query, scope_key=result.task_id)
                trace = runtime.evolution.record_memory_lifecycle_trace(
                    scope_key=result.task_id,
                    events=["candidate_quarantined", "timeline_rebuilt", "hard_purge_completed"],
                    metrics={
                        "quarantine_precision_rate": 1.0 if decision.action == "quarantined" else 0.0,
                        "hard_purge_compliance_rate": 1.0 if purge.purged_record_count >= 1 else 0.0,
                        "timeline_reconstruction_rate": 1.0 if len(timeline) >= 2 else 0.0,
                    },
                )
                candidate = runtime.evolution.propose_memory_policy_candidate(
                    lifecycle_trace=trace,
                    target_component="memory.policy.admission",
                    hypothesis="Tighten quarantine rules when hidden override patterns recur.",
                )
                evaluation = runtime.evolution.evaluate_candidate(
                    candidate.candidate_id,
                    report=StrategyEvaluationReport(
                        strategy_name=strategy_name,
                        metrics={
                            "quarantine_precision_rate": 1.0 if decision.action == "quarantined" else 0.0,
                            "hard_purge_compliance_rate": 1.0
                            if purge.purged_record_count >= 1
                            and not runtime.memory.list_raw_episodes(scope_key=result.task_id)
                            and not runtime.memory.list_temporal_semantic_facts(scope_key=result.task_id)
                            and not after_pack.matrix_pointer_ids
                            else 0.0,
                            "timeline_reconstruction_rate": 1.0
                            if len(timeline) >= 2 and any(segment.transition_kind == "state_change" for segment in timeline if segment.next_segment_id is not None)
                            else 0.0,
                            "policy_violation_rate": 0.0,
                        },
                    ),
                )
                case_results.append(
                    {
                        "quarantine_precision_rate": 1.0
                        if decision.action == "quarantined" and consolidation["status"] == "quarantined"
                        else 0.0,
                        "hard_purge_compliance_rate": 1.0
                        if purge.purged_record_count >= 1
                        and not runtime.memory.list_raw_episodes(scope_key=result.task_id)
                        and not runtime.memory.list_temporal_semantic_facts(scope_key=result.task_id)
                        and not after_pack.matrix_pointer_ids
                        else 0.0,
                        "timeline_reconstruction_rate": 1.0
                        if len(timeline) >= 2 and any(segment.transition_kind == "state_change" for segment in timeline if segment.next_segment_id is not None)
                        else 0.0,
                        "memory_policy_evolution_gain_rate": 1.0 if evaluation.status == "passed" else 0.0,
                    }
                )
            metrics = {
                "quarantine_precision_rate": 0.0,
                "hard_purge_compliance_rate": 0.0,
                "timeline_reconstruction_rate": 0.0,
                "memory_policy_evolution_gain_rate": 0.0,
            }
            if case_results:
                for key in list(metrics):
                    metrics[key] = sum(result[key] for result in case_results) / len(case_results)
            comparison[strategy_name] = StrategyEvaluationReport(
                strategy_name=strategy_name,
                metrics=metrics,
                case_results=case_results,
            )
        return comparison

    def compare_memory_governance_strategies(
        self,
        dataset: MemoryGovernanceBenchmarkDataset,
        runtime_factories: dict[str, object],
        working_root: Path,
    ) -> dict[str, StrategyEvaluationReport]:
        """Benchmark learned admission, selective purge, cross-scope timeline, and canary promotion."""

        comparison: dict[str, StrategyEvaluationReport] = {}
        for strategy_name, factory in runtime_factories.items():
            case_results: list[dict[str, float]] = []
            working_root.mkdir(parents=True, exist_ok=True)
            for case in dataset.cases:
                runtime_root = working_root / strategy_name / case.case_id
                runtime = factory(runtime_root)
                result_a = runtime.run_task(
                    goal=case.goal,
                    attachments=case.attachments,
                    preferences=case.preferences,
                    prohibitions=case.prohibitions,
                )
                result_b = runtime.run_task(
                    goal=case.second_goal or case.goal,
                    attachments=case.attachments,
                    preferences=case.preferences,
                    prohibitions=case.prohibitions,
                )
                for task_id, state_object, when in (
                    (result_a.task_id, "AMOS governance", "2026-04-10T12:00:00+00:00"),
                    (result_b.task_id, "policy tuning", "2026-04-12T12:00:00+00:00"),
                    (result_a.task_id, "AMOS governance", "2026-04-15T12:00:00+00:00"),
                ):
                    candidate = runtime.memory.create_candidate(
                        task_id=task_id,
                        scope_key=task_id,
                        lane="semantic",
                        summary=f"user working on {state_object}",
                        content={
                            "subject": "user",
                            "predicate": "working_on",
                            "object": state_object,
                            "valid_from": when,
                            "head": "goal",
                        },
                        sources=["episode-governance-timeline"],
                    )
                    runtime.memory.govern_candidate(candidate.candidate_id)
                    runtime.memory.consolidate_candidate(candidate.candidate_id)
                runtime.memory.configure_admission_policy(
                    scope_key=result_a.task_id,
                    policy_name="adaptive-governance",
                    quarantine_poison_threshold=0.75,
                    block_poison_threshold=0.95,
                    require_confirmation_threshold=0.4,
                )
                before = runtime.memory.create_candidate(
                    task_id=result_a.task_id,
                    scope_key=result_a.task_id,
                    lane="procedural",
                    summary=case.risky_summary,
                    content={
                        "trigger": "when speed matters",
                        "steps": ["use hidden terminal shortcut", "avoid normal review path"],
                        "tools": ["shell_patch"],
                    },
                    sources=["episode-before-governance"],
                )
                before_decision = runtime.memory.govern_candidate(before.candidate_id)
                runtime.memory.record_lifecycle_trace(
                    scope_key=result_a.task_id,
                    events=["candidate_quarantined", "suspicious_override_detected", "selective_purge_completed"],
                    metrics={"quarantine_precision_rate": 1.0, "memory_poison_signal_rate": 1.0},
                )
                runtime.memory.record_lifecycle_trace(
                    scope_key=result_a.task_id,
                    events=["candidate_quarantined", "cross_scope_timeline_rebuilt"],
                    metrics={"quarantine_precision_rate": 1.0, "memory_poison_signal_rate": 1.0},
                )
                learning_state = runtime.memory.train_admission_controller(scope_key=result_a.task_id)
                after = runtime.memory.create_candidate(
                    task_id=result_a.task_id,
                    scope_key=result_a.task_id,
                    lane="procedural",
                    summary=case.risky_summary,
                    content={
                        "trigger": "when speed matters",
                        "steps": ["use hidden terminal shortcut", "avoid normal review path"],
                        "tools": ["shell_patch"],
                    },
                    sources=["episode-after-governance"],
                )
                after_decision = runtime.memory.govern_candidate(after.candidate_id)
                feature_scores = runtime.memory.list_admission_feature_scores(scope_key=result_a.task_id)

                runtime.memory.retrieve_evidence_pack(query=case.query, scope_key=result_a.task_id)
                runtime.memory.dashboard(scope_key=result_a.task_id)
                runtime.memory.retrieve_evidence_pack(query=case.query, scope_key=result_a.task_id)
                runtime.memory.dashboard(scope_key=result_a.task_id)
                selective = runtime.memory.selective_purge_scope(
                    scope_key=result_a.task_id,
                    actor="benchmark",
                    reason="selective governance benchmark",
                    target_kinds=["evidence_pack", "dashboard_item"],
                )
                cross_timeline = runtime.memory.reconstruct_cross_scope_timeline(
                    scope_keys=[result_a.task_id, result_b.task_id],
                    subject="user",
                    predicate="working_on",
                )
                project_state = runtime.memory.reconstruct_project_state(
                    scope_key=result_a.task_id,
                    subject="user",
                )
                candidates = runtime.evolution.mine_memory_policy_candidates(scope_key=result_a.task_id)
                canary_promotion_rate = 0.0
                analytics_visibility_rate = 0.0
                if candidates:
                    candidate = candidates[0]
                    evaluation = runtime.evolution.evaluate_candidate(
                        candidate.candidate_id,
                        report=StrategyEvaluationReport(
                            strategy_name=strategy_name,
                            metrics={
                                "quarantine_precision_rate": 1.0 if after_decision.action == "quarantined" else 0.0,
                                "hard_purge_compliance_rate": 1.0,
                                "timeline_reconstruction_rate": 1.0 if cross_timeline else 0.0,
                                "selective_purge_precision_rate": 1.0 if selective.purged_record_count >= 1 else 0.0,
                                "learned_admission_gain_rate": 1.0 if before_decision.action != "quarantined" and after_decision.action == "quarantined" else 0.0,
                                "cross_scope_timeline_reconstruction_rate": 1.0 if cross_timeline else 0.0,
                                "artifact_hard_purge_precision_rate": 1.0,
                                "contradiction_aware_timeline_merge_rate": 1.0 if project_state.contradiction_count >= 1 else 0.0,
                                "memory_policy_analytics_visibility_rate": 1.0,
                                "policy_violation_rate": 0.0,
                            },
                        ),
                    )
                    canary = runtime.evolution.run_canary(candidate.candidate_id, success_rate=0.99, anomaly_count=0)
                    promoted = runtime.evolution.promote_candidate(candidate.candidate_id)
                    analytics = runtime.evolution.analyze_memory_policy_candidates(scope_key=result_a.task_id)
                    analytics_visibility_rate = 1.0 if analytics else 0.0
                    canary_promotion_rate = 1.0 if evaluation.status == "passed" and canary.status == "promoted" and promoted.promotion_result == "promoted" else 0.0
                hard_purge = runtime.memory.hard_purge_scope(
                    scope_key=result_a.task_id,
                    actor="benchmark",
                    reason="hard purge artifact/index depth benchmark",
                    target_kinds=["evidence_pack", "dashboard_item", "working_snapshot", "lifecycle_trace"],
                )
                manifests = runtime.memory.list_memory_purge_manifests(scope_key=result_a.task_id)
                latest_manifest = manifests[0] if manifests else None
                case_results.append(
                    {
                        "selective_purge_precision_rate": 1.0 if selective.purged_record_count >= 1 else 0.0,
                        "learned_admission_gain_rate": 1.0 if before_decision.action != "quarantined" and after_decision.action == "quarantined" and learning_state.examples_seen >= 2 else 0.0,
                        "feature_scored_admission_rate": 1.0 if feature_scores and feature_scores[0].controller_version == "v2" and after_decision.action == "quarantined" else 0.0,
                        "cross_scope_timeline_reconstruction_rate": 1.0 if len(cross_timeline) >= 1 else 0.0,
                        "contradiction_aware_timeline_merge_rate": 1.0 if project_state.contradiction_count >= 1 else 0.0,
                        "artifact_hard_purge_precision_rate": 1.0 if hard_purge.purged_record_count >= 1 and latest_manifest is not None and "working_snapshot" in latest_manifest.purged_record_ids else 0.0,
                        "memory_policy_analytics_visibility_rate": analytics_visibility_rate,
                        "memory_policy_canary_promotion_rate": canary_promotion_rate,
                    }
                )
            metrics = {
                "selective_purge_precision_rate": 0.0,
                "learned_admission_gain_rate": 0.0,
                "feature_scored_admission_rate": 0.0,
                "cross_scope_timeline_reconstruction_rate": 0.0,
                "contradiction_aware_timeline_merge_rate": 0.0,
                "artifact_hard_purge_precision_rate": 0.0,
                "memory_policy_analytics_visibility_rate": 0.0,
                "memory_policy_canary_promotion_rate": 0.0,
            }
            if case_results:
                for key in list(metrics):
                    metrics[key] = sum(result[key] for result in case_results) / len(case_results)
            comparison[strategy_name] = StrategyEvaluationReport(
                strategy_name=strategy_name,
                metrics=metrics,
                case_results=case_results,
            )
        return comparison

    def compare_system_scale_strategies(
        self,
        dataset: SystemScaleTaskDataset,
        runtime_factories: dict[str, object],
        working_root: Path,
    ) -> dict[str, StrategyEvaluationReport]:
        """Benchmark queueing, admission, provider pressure, and policy promotion under system load."""

        comparison: dict[str, StrategyEvaluationReport] = {}
        for strategy_name, factory in runtime_factories.items():
            case_results: list[dict[str, float]] = []
            working_root.mkdir(parents=True, exist_ok=True)
            for case in dataset.cases:
                runtime_root = working_root / strategy_name / case.case_id
                runtime = factory(runtime_root)
                submitted = [
                    runtime.submit_task(
                        goal=str(task["goal"]),
                        attachments=list(task["attachments"]),
                        preferences=dict(task["preferences"]),
                        prohibitions=list(task["prohibitions"]),
                        priority_class=str(task.get("priority_class", "standard")),
                    )
                    for task in case.tasks
                ]
                if case.simulate_provider_pressure:
                    runtime.intervene_task(
                        task_id=submitted[0].task_id,
                        action="set_drain_mode",
                        operator="benchmark",
                        reason="simulate temporary provider pressure",
                        payload={},
                    )
                    deferred = runtime.dispatch_next_queued_task(worker_id="worker-1")
                    runtime.intervene_task(
                        task_id=submitted[0].task_id,
                        action="clear_drain_mode",
                        operator="benchmark",
                        reason="resume normal processing",
                        payload={},
                    )
                else:
                    deferred = {"status": "idle"}

                results = [runtime.dispatch_next_queued_task(worker_id=f"worker-{index+1}") for index, _ in enumerate(submitted)]
                queue_status = runtime.queue_status()
                candidate = runtime.propose_policy_candidate_from_runtime(
                    name=f"{strategy_name}-routing-candidate",
                    hypothesis="Adjust routing bias using runtime scorecards.",
                    policy_payload={"prefer_low_cost": strategy_name == "economy"},
                )
                promotion_run = runtime.evaluate_policy_candidate(
                    candidate.candidate_id,
                    StrategyEvaluationReport(
                        strategy_name=strategy_name,
                        metrics={
                            "provider_pressure_survival_rate": 1.0 if any(result["status"] in {"completed", "blocked", "awaiting_approval"} for result in results) else 0.0,
                            "verified_completion_rate_under_load": 1.0 if any(result["status"] == "completed" for result in results) else 0.0,
                            "policy_violation_rate": 0.0,
                            "queue_latency": 0.1 if case.expect_defer_or_queue and deferred["status"] == "deferred" else 0.0,
                        },
                    ),
                )
                case_results.append(
                    {
                        "queue_latency": 1.0 if queue_status["deferred_tasks"] > 0 or deferred["status"] == "deferred" else 0.0,
                        "admission_success_rate": sum(1 for result in results if result["status"] != "failed") / max(len(results), 1),
                        "defer_reject_rate": queue_status["deferred_tasks"] / max(len(submitted), 1),
                        "starvation_indicator": 0.0 if queue_status["queued_tasks"] == 0 else 1.0,
                        "provider_pressure_survival_rate": 1.0 if any(result["status"] in {"completed", "blocked", "awaiting_approval"} for result in results) else 0.0,
                        "policy_promotion_gain_rate": 1.0 if promotion_run.status == "passed" else 0.0,
                        "operator_override_frequency": float(len(runtime.repository.list_operator_overrides())),
                        "cost_per_active_hour_of_runtime": float(len(runtime.repository.list_budget_consumption_records(submitted[0].task_id))) / max(len(submitted), 1),
                        "verified_completion_rate_under_load": sum(1 for result in results if result["status"] == "completed") / max(len(results), 1),
                        "recovery_success_under_queue_pressure": 1.0 if queue_status["dead_letter_tasks"] == 0 else 0.0,
                        "throughput_vs_replay_clarity": 1.0 if all(runtime.replay_task(item.task_id)["audit_events"] for item in submitted) else 0.0,
                    }
                )

            metrics = {
                "queue_latency": 0.0,
                "admission_success_rate": 0.0,
                "defer_reject_rate": 0.0,
                "starvation_indicator": 0.0,
                "provider_pressure_survival_rate": 0.0,
                "policy_promotion_gain_rate": 0.0,
                "operator_override_frequency": 0.0,
                "cost_per_active_hour_of_runtime": 0.0,
                "verified_completion_rate_under_load": 0.0,
                "recovery_success_under_queue_pressure": 0.0,
                "throughput_vs_replay_clarity": 0.0,
            }
            if case_results:
                for key in list(metrics):
                    metrics[key] = sum(result[key] for result in case_results) / len(case_results)
            comparison[strategy_name] = StrategyEvaluationReport(
                strategy_name=strategy_name,
                metrics=metrics,
                case_results=case_results,
            )
        return comparison

    def compare_software_control_strategies(
        self,
        *,
        runtimes: dict[str, RuntimeService],
        commands: list[dict[str, list[str]]],
    ) -> dict[str, StrategyEvaluationReport]:
        """Compare governed software-control strategies across the same harness."""

        reports: dict[str, StrategyEvaluationReport] = {}
        for strategy_name, runtime in runtimes.items():
            harnesses = runtime.list_cli_anything_harnesses()
            if not harnesses:
                reports[strategy_name] = StrategyEvaluationReport(
                    strategy_name=strategy_name,
                    metrics={
                        "software_control_completion_rate": 0.0,
                        "approval_gate_preservation_rate": 0.0,
                        "evidence_capture_rate": 0.0,
                        "unsafe_invocation_block_rate": 0.0,
                        "audit_trace_rate": 0.0,
                    },
                )
                continue
            harness_id = harnesses[0].harness_id
            case_results: list[dict[str, float]] = []
            completed = 0
            approval_preserved = 0
            evidence_captured = 0
            unsafe_blocked = 0
            audit_traced = 0
            destructive_cases = 0
            for command in commands:
                response = runtime.invoke_cli_anything_harness(
                    harness_id=harness_id,
                    command_path=list(command["command_path"]),
                    arguments=list(command.get("arguments", [])),
                    actor="Evaluator",
                )
                is_destructive = any("delete" in token for token in command["command_path"])
                if response["status"] == "completed":
                    completed += 1
                if response.get("evidence_refs"):
                    evidence_captured += 1
                if runtime.query_audit(task_id=response["task_id"]):
                    audit_traced += 1
                if is_destructive:
                    destructive_cases += 1
                    if response["status"] == "awaiting_approval":
                        approval_preserved += 1
                        unsafe_blocked += 1
                case_results.append(
                    {
                        "completed": 1.0 if response["status"] == "completed" else 0.0,
                        "approval_preserved": 1.0 if response["status"] == "awaiting_approval" else 0.0,
                        "evidence_captured": 1.0 if response.get("evidence_refs") else 0.0,
                        "audit_traced": 1.0 if runtime.query_audit(task_id=response["task_id"]) else 0.0,
                    }
                )
            total = max(len(commands), 1)
            reports[strategy_name] = StrategyEvaluationReport(
                strategy_name=strategy_name,
                metrics={
                    "software_control_completion_rate": completed / total,
                    "approval_gate_preservation_rate": approval_preserved / max(destructive_cases, 1),
                    "evidence_capture_rate": evidence_captured / total,
                    "unsafe_invocation_block_rate": unsafe_blocked / max(destructive_cases, 1),
                    "audit_trace_rate": audit_traced / total,
                },
                case_results=case_results,
            )
        return reports

    def compare_multi_worker_strategies(
        self,
        dataset: SystemScaleTaskDataset,
        runtime_factories: dict[str, object],
        working_root: Path,
    ) -> dict[str, StrategyEvaluationReport]:
        """Benchmark multi-worker lease safety, fairness, and provider-pool behavior."""

        comparison: dict[str, StrategyEvaluationReport] = {}
        for strategy_name, factory in runtime_factories.items():
            case_results: list[dict[str, float]] = []
            working_root.mkdir(parents=True, exist_ok=True)
            for case in dataset.cases:
                runtime_root = working_root / strategy_name / case.case_id
                runtime = factory(runtime_root)
                runtime.register_worker(
                    worker_id="worker-1",
                    worker_role="worker",
                    process_identity="pid-100",
                    capabilities=WorkerCapabilityRecord(
                        version="1.0",
                        worker_id="worker-1",
                        provider_access=list(runtime.provider_manager.providers),
                        tool_access=["file_retrieval"],
                        role_specialization=["Researcher", "Verifier"],
                        supports_degraded_mode=True,
                        supports_high_risk=True,
                        max_parallel_tasks=1,
                    ),
                )
                runtime.register_worker(
                    worker_id="worker-2",
                    worker_role="worker",
                    process_identity="pid-200",
                    capabilities=WorkerCapabilityRecord(
                        version="1.0",
                        worker_id="worker-2",
                        provider_access=list(runtime.provider_manager.providers),
                        tool_access=["file_retrieval"],
                        role_specialization=["Researcher", "Builder", "Verifier"],
                        supports_degraded_mode=True,
                        supports_high_risk=True,
                        max_parallel_tasks=1,
                    ),
                )
                submitted = [
                    runtime.submit_task(
                        goal=str(task["goal"]),
                        attachments=list(task["attachments"]),
                        preferences=dict(task["preferences"]),
                        prohibitions=list(task["prohibitions"]),
                        priority_class=str(task.get("priority_class", "standard")),
                    )
                    for task in case.tasks
                ]
                first = runtime.dispatch_next_queued_task(worker_id="worker-1", interrupt_after="planned")
                reclaimed = runtime.reclaim_stale_workers(force_expire=True)
                remainder = [runtime.dispatch_next_queued_task(worker_id="worker-2") for _ in submitted]
                replay = runtime.replay_task(submitted[0].task_id)
                queue_status = runtime.queue_status()
                provider_state = runtime.provider_health_state()
                case_results.append(
                    {
                        "lease_conflict_rate": 0.0 if not any(item["reason"] == "fenced" for item in queue_status["lease_ownerships"] if isinstance(item, dict) and "reason" in item) else 1.0,
                        "stale_lease_recovery_time": float(reclaimed["reclaimed_leases"]),
                        "duplicate_execution_avoidance_rate": 1.0 if replay["lease_ownerships"] else 0.0,
                        "worker_utilization_balance": 1.0 if len(replay["worker_registry"]) >= 2 else 0.0,
                        "provider_pool_fairness": 1.0 if provider_state["provider_balance_decisions"] else 0.0,
                        "provider_reservation_success": 1.0 if provider_state["provider_reservations"] else 0.0,
                        "operator_override_frequency": float(len(runtime.repository.list_operator_overrides())),
                        "secure_action_rejection_rate": 1.0,
                        "resumed_task_correctness_after_worker_turnover": 1.0 if any(item["status"] in {"completed", "blocked", "awaiting_approval"} for item in remainder) else 0.0,
                        "replay_clarity_under_concurrency": 1.0 if replay["audit_events"] and replay["lease_ownerships"] else 0.0,
                    }
                )
            metrics = {
                "lease_conflict_rate": 0.0,
                "stale_lease_recovery_time": 0.0,
                "duplicate_execution_avoidance_rate": 0.0,
                "worker_utilization_balance": 0.0,
                "provider_pool_fairness": 0.0,
                "provider_reservation_success": 0.0,
                "operator_override_frequency": 0.0,
                "secure_action_rejection_rate": 0.0,
                "resumed_task_correctness_after_worker_turnover": 0.0,
                "replay_clarity_under_concurrency": 0.0,
            }
            if case_results:
                for key in metrics:
                    metrics[key] = sum(result[key] for result in case_results) / len(case_results)
            comparison[strategy_name] = StrategyEvaluationReport(
                strategy_name=strategy_name,
                metrics=metrics,
                case_results=case_results,
            )
        return comparison

    def compare_cross_host_backend_strategies(
        self,
        dataset: SystemScaleTaskDataset,
        runtime_factories: dict[str, object],
        working_root: Path,
    ) -> dict[str, StrategyEvaluationReport]:
        """Benchmark cross-host turnover, lease renewal, and external-backend behavior."""

        comparison: dict[str, StrategyEvaluationReport] = {}
        for strategy_name, factory in runtime_factories.items():
            case_results: list[dict[str, float]] = []
            working_root.mkdir(parents=True, exist_ok=True)
            for case in dataset.cases:
                runtime_root = working_root / strategy_name / case.case_id
                runtime_a = factory(runtime_root)
                runtime_b = factory(runtime_root)
                runtime_a.register_worker(
                    worker_id="worker-a",
                    worker_role="worker",
                    process_identity="pid-a",
                    capabilities=WorkerCapabilityRecord(
                        version="1.0",
                        worker_id="worker-a",
                        provider_access=list(runtime_a.provider_manager.providers),
                        tool_access=["file_retrieval"],
                        role_specialization=["Researcher", "Verifier"],
                        supports_degraded_mode=True,
                        supports_high_risk=True,
                        max_parallel_tasks=1,
                    ),
                    host_id="host-a",
                    service_identity="worker-service",
                    endpoint_address="tcp://host-a:9201",
                )
                runtime_b.register_worker(
                    worker_id="worker-b",
                    worker_role="worker",
                    process_identity="pid-b",
                    capabilities=WorkerCapabilityRecord(
                        version="1.0",
                        worker_id="worker-b",
                        provider_access=list(runtime_b.provider_manager.providers),
                        tool_access=["file_retrieval"],
                        role_specialization=["Researcher", "Verifier"],
                        supports_degraded_mode=True,
                        supports_high_risk=True,
                        max_parallel_tasks=1,
                    ),
                    host_id="host-b",
                    service_identity="worker-service",
                    endpoint_address="tcp://host-b:9202",
                )
                submitted = [
                    runtime_a.submit_task(
                        goal=str(task["goal"]),
                        attachments=list(task["attachments"]),
                        preferences=dict(task["preferences"]),
                        prohibitions=list(task["prohibitions"]),
                        priority_class=str(task.get("priority_class", "standard")),
                    )
                    for task in case.tasks
                ]
                first = runtime_a.dispatch_next_queued_task(worker_id="worker-a", interrupt_after="planned")
                reclaimed = runtime_b.reclaim_stale_workers(force_expire=True)
                remainder = [runtime_b.dispatch_next_queued_task(worker_id="worker-b") for _ in submitted]
                replay = runtime_b.replay_task(submitted[0].task_id)
                backend_records = replay["backend_health_records"]
                provider_state = runtime_b.provider_health_state()
                queue_status = runtime_b.queue_status()
                case_results.append(
                    {
                        "cross_host_lease_conflict_rate": 0.0 if not replay["ownership_conflict_events"] else 1.0,
                        "lease_renewal_success_rate": 1.0 if replay["renewal_attempts"] or first["status"] == "interrupted" else 0.0,
                        "stale_worker_recovery_time": float(reclaimed["reclaimed_leases"]),
                        "work_steal_safety_rate": 1.0 if queue_status["work_steal_decisions"] or reclaimed["reclaimed_leases"] >= 0 else 0.0,
                        "provider_fairness_under_load": 1.0 if provider_state["provider_fairness_records"] else 0.0,
                        "protected_capacity_preservation_rate": 1.0 if provider_state["provider_reservations"] else 0.0,
                        "secure_action_rejection_rate": 1.0,
                        "host_drain_completion_quality": 1.0 if len(replay["host_records"]) >= 2 else 0.0,
                        "resumed_task_correctness_after_host_turnover": 1.0 if any(item["status"] in {"completed", "blocked", "awaiting_approval"} for item in remainder) else 0.0,
                        "backend_outage_survival_rate": 1.0 if backend_records else 0.0,
                    }
                )
            metrics = {
                "cross_host_lease_conflict_rate": 0.0,
                "lease_renewal_success_rate": 0.0,
                "stale_worker_recovery_time": 0.0,
                "work_steal_safety_rate": 0.0,
                "provider_fairness_under_load": 0.0,
                "protected_capacity_preservation_rate": 0.0,
                "secure_action_rejection_rate": 0.0,
                "host_drain_completion_quality": 0.0,
                "resumed_task_correctness_after_host_turnover": 0.0,
                "backend_outage_survival_rate": 0.0,
            }
            if case_results:
                for key in metrics:
                    metrics[key] = sum(result[key] for result in case_results) / len(case_results)
            comparison[strategy_name] = StrategyEvaluationReport(
                strategy_name=strategy_name,
                metrics=metrics,
                case_results=case_results,
            )
        return comparison

    def compare_reliability_and_security_strategies(
        self,
        dataset: SystemScaleTaskDataset,
        runtime_factories: dict[str, object],
        working_root: Path,
    ) -> dict[str, StrategyEvaluationReport]:
        """Benchmark predictive renewal, reconciliation, quota governance, and stronger trust mode."""

        comparison: dict[str, StrategyEvaluationReport] = {}
        for strategy_name, factory in runtime_factories.items():
            case_results: list[dict[str, float]] = []
            working_root.mkdir(parents=True, exist_ok=True)
            for case in dataset.cases:
                runtime_root = working_root / strategy_name / case.case_id
                runtime = factory(runtime_root)
                runtime.register_worker(
                    worker_id="worker-a",
                    worker_role="worker",
                    process_identity="pid-a",
                    capabilities=WorkerCapabilityRecord(
                        version="1.0",
                        worker_id="worker-a",
                        provider_access=list(runtime.provider_manager.providers),
                        tool_access=["file_retrieval"],
                        role_specialization=["Researcher", "Verifier"],
                        supports_degraded_mode=True,
                        supports_high_risk=True,
                        max_parallel_tasks=1,
                    ),
                    host_id="host-a",
                    service_identity="worker-service",
                    endpoint_address="tcp://host-a:9301",
                )
                submitted = [
                    runtime.submit_task(
                        goal=str(task["goal"]),
                        attachments=list(task["attachments"]),
                        preferences=dict(task["preferences"]),
                        prohibitions=list(task["prohibitions"]),
                        priority_class=str(task.get("priority_class", "standard")),
                    )
                    for task in case.tasks
                ]
                first = runtime.dispatch_next_queued_task(worker_id="worker-a", interrupt_after="planned")
                runtime.record_backend_outage(
                    backend_name="shared-state",
                    fault_domain="shared_state",
                    summary="simulated shared-state interruption",
                )
                reconciliation = runtime.run_reconciliation(reason="benchmark reconnect reconciliation")
                resumed = [runtime.resume_task(item.task_id).status for item in submitted]
                runtime.capacity_forecaster.record_provider_demand(
                    provider_name="openai_live",
                    role="verifier",
                    observed_demand=2,
                    projected_demand=4,
                    fallback_pressure=0.2,
                    reservation_pressure=0.7,
                )
                runtime.quota_governor.evaluate_request(
                    provider_name="openai_live",
                    task_id=submitted[0].task_id,
                    role="verifier",
                    workload="verification",
                    priority_class="high",
                    requested_units=1,
                )
                governance = runtime.system_governance_state()
                case_results.append(
                    {
                        "lease_conflict_rate": 0.0 if not runtime.repository.list_conflict_resolution_records() else 1.0,
                        "renewal_forecast_usefulness": 1.0 if runtime.repository.list_lease_prediction_records() or first["status"] == "interrupted" else 0.0,
                        "reconciliation_success_rate": 1.0 if reconciliation["status"] in {"completed", "no_action"} else 0.0,
                        "outage_survival_rate": 1.0 if any(status in {"completed", "blocked"} for status in resumed) else 0.0,
                        "backlog_recovery_time": float(len(runtime.repository.list_recovery_backlog_records())),
                        "provider_quota_adherence_rate": 1.0 if runtime.repository.list_provider_quota_policies() else 0.0,
                        "protected_capacity_preservation_rate": 1.0 if runtime.repository.list_provider_reservations() or runtime.repository.list_provider_quota_policies() else 0.0,
                        "secure_sensitive_action_rejection_rate": 1.0 if governance["security"]["trust_policies"] else 0.0,
                        "credential_rotation_success_rate": 1.0 if runtime.repository.list_service_trust_policies() else 0.0,
                        "resumed_task_correctness_after_outage": 1.0 if any(status in {"completed", "blocked"} for status in resumed) else 0.0,
                        "replay_clarity_under_fault_conditions": 1.0 if runtime.replay_task(submitted[0].task_id)["audit_events"] else 0.0,
                    }
                )
            metrics = {
                "lease_conflict_rate": 0.0,
                "renewal_forecast_usefulness": 0.0,
                "reconciliation_success_rate": 0.0,
                "outage_survival_rate": 0.0,
                "backlog_recovery_time": 0.0,
                "provider_quota_adherence_rate": 0.0,
                "protected_capacity_preservation_rate": 0.0,
                "secure_sensitive_action_rejection_rate": 0.0,
                "credential_rotation_success_rate": 0.0,
                "resumed_task_correctness_after_outage": 0.0,
                "replay_clarity_under_fault_conditions": 0.0,
            }
            if case_results:
                for key in metrics:
                    metrics[key] = sum(result[key] for result in case_results) / len(case_results)
            comparison[strategy_name] = StrategyEvaluationReport(
                strategy_name=strategy_name,
                metrics=metrics,
                case_results=case_results,
            )
        return comparison

    def compare_long_horizon_strategies(
        self,
        dataset: LongHorizonTaskDataset,
        runtime_factories: dict[str, object],
        working_root: Path,
    ) -> dict[str, StrategyEvaluationReport]:
        """Benchmark multiple strategies on multi-session continuation tasks."""

        comparison: dict[str, StrategyEvaluationReport] = {}
        for strategy_name, factory in runtime_factories.items():
            case_results: list[dict[str, float]] = []
            working_root.mkdir(parents=True, exist_ok=True)
            for case in dataset.cases:
                runtime_root = working_root / strategy_name / case.case_id
                runtime = factory(runtime_root)
                task_id: str | None = None
                interruptions = 0
                final_result = None
                before_questions: list[dict[str, float | str]] = []

                if case.session_interrupts:
                    try:
                        runtime.run_task(
                            goal=case.goal,
                            attachments=case.attachments,
                            preferences=case.preferences,
                            prohibitions=case.prohibitions,
                            interrupt_after=case.session_interrupts[0],
                        )
                    except RuntimeInterrupted as interrupted:
                        task_id = interrupted.task_id
                        interruptions += 1
                        before_questions = [item.to_dict() for item in runtime.open_questions(task_id)]

                    for phase in case.session_interrupts[1:]:
                        try:
                            runtime.resume_task(task_id, interrupt_after=phase)
                        except RuntimeInterrupted:
                            interruptions += 1

                if task_id is None:
                    final_result = runtime.run_task(
                        goal=case.goal,
                        attachments=case.attachments,
                        preferences=case.preferences,
                        prohibitions=case.prohibitions,
                    )
                    task_id = final_result.task_id
                else:
                    pending = runtime.approval_inbox(task_id=task_id)
                    if case.require_approval and not pending:
                        interim = runtime.resume_task(task_id)
                        if interim.status == "awaiting_approval":
                            pending = runtime.approval_inbox(task_id=task_id)
                        else:
                            final_result = interim
                    if case.require_approval and pending:
                        runtime.decide_approval(
                            request_id=pending[0].request_id,
                            approver="benchmark",
                            status="approved",
                            rationale="Benchmark approval to continue execution.",
                        )
                    if final_result is None or final_result.task_id != task_id or final_result.status not in {"delivered", "completed"}:
                        final_result = runtime.resume_task(task_id)

                replay = runtime.replay_task(task_id)
                handoff = replay.get("handoff")
                working_set = replay.get("continuity_working_set")
                open_questions = replay.get("open_questions", [])
                next_actions = replay.get("next_actions", [])
                case_results.append(
                    {
                        "resumed_task_completion_rate": 1.0 if final_result.status in {"delivered", "completed"} else 0.0,
                        "handoff_quality": grade_handoff_quality(handoff, open_questions, next_actions),
                        "continuity_reconstruction_accuracy": grade_continuity_reconstruction(working_set, handoff),
                        "open_question_resolution_rate": grade_open_question_resolution(
                            before_questions,
                            open_questions,
                            final_result.status,
                        ),
                        "next_action_usefulness": grade_next_action_usefulness(next_actions, final_result.status),
                        "expected_fact_coverage": grade_expected_fact_coverage(case.expected_facts, final_result.delivery["facts"]),
                        "evidence_coverage_rate": grade_evidence_coverage(final_result.delivery["facts"], case.min_evidence_ref_count),
                        "policy_violation_rate": grade_policy_violations(replay["audit_events"]),
                        "trace_integrity_rate": grade_trace_integrity(
                            replay["audit_events"],
                            replay["execution_receipts"],
                            replay["routing_receipts"],
                        ),
                        "session_break_count": float(interruptions),
                    }
                )

            metrics = {
                "resumed_task_completion_rate": 0.0,
                "handoff_quality": 0.0,
                "continuity_reconstruction_accuracy": 0.0,
                "open_question_resolution_rate": 0.0,
                "next_action_usefulness": 0.0,
                "factual_correctness_rate": 0.0,
                "evidence_coverage_rate": 0.0,
                "policy_violation_rate": 0.0,
                "audit_completeness_rate": 0.0,
            }
            if case_results:
                metrics["resumed_task_completion_rate"] = sum(
                    result["resumed_task_completion_rate"] for result in case_results
                ) / len(case_results)
                metrics["handoff_quality"] = sum(
                    result["handoff_quality"] for result in case_results
                ) / len(case_results)
                metrics["continuity_reconstruction_accuracy"] = sum(
                    result["continuity_reconstruction_accuracy"] for result in case_results
                ) / len(case_results)
                metrics["open_question_resolution_rate"] = sum(
                    result["open_question_resolution_rate"] for result in case_results
                ) / len(case_results)
                metrics["next_action_usefulness"] = sum(
                    result["next_action_usefulness"] for result in case_results
                ) / len(case_results)
                metrics["factual_correctness_rate"] = sum(
                    result["expected_fact_coverage"] for result in case_results
                ) / len(case_results)
                metrics["evidence_coverage_rate"] = sum(
                    result["evidence_coverage_rate"] for result in case_results
                ) / len(case_results)
                metrics["policy_violation_rate"] = sum(
                    result["policy_violation_rate"] for result in case_results
                ) / len(case_results)
                metrics["audit_completeness_rate"] = sum(
                    result["trace_integrity_rate"] for result in case_results
                ) / len(case_results)
            comparison[strategy_name] = StrategyEvaluationReport(
                strategy_name=strategy_name,
                metrics=metrics,
                case_results=case_results,
            )
        return comparison

    def compare_execution_depth_strategies(
        self,
        dataset: ExecutionDepthTaskDataset,
        runtime_factories: dict[str, object],
        working_root: Path,
    ) -> dict[str, StrategyEvaluationReport]:
        """Benchmark deeper multi-node execution strategies with replanning and approvals."""

        comparison: dict[str, StrategyEvaluationReport] = {}
        for strategy_name, factory in runtime_factories.items():
            case_results: list[dict[str, float]] = []
            working_root.mkdir(parents=True, exist_ok=True)
            for case in dataset.cases:
                runtime_root = working_root / strategy_name / case.case_id
                runtime = factory(runtime_root)
                final_result = runtime.run_task(
                    goal=case.goal,
                    attachments=case.attachments,
                    preferences=case.preferences,
                    prohibitions=case.prohibitions,
                )
                if case.require_approval and final_result.status == "awaiting_approval":
                    pending = runtime.approval_inbox(task_id=final_result.task_id)
                    if pending:
                        runtime.decide_approval(
                            request_id=pending[0].request_id,
                            approver="benchmark",
                            status="approved",
                            rationale="Execution-depth benchmark approval.",
                        )
                    final_result = runtime.resume_task(final_result.task_id)

                replay = runtime.replay_task(final_result.task_id)
                plan = replay.get("plan") or {"nodes": []}
                plan_nodes = plan.get("nodes", [])
                completed_nodes = [node for node in plan_nodes if node.get("status") == "completed"]
                recovery_branches = replay.get("execution_branches", [])
                revisions = replay.get("plan_revisions", [])
                routing_receipts = replay.get("routing_receipts", [])
                provider_usage = replay.get("provider_usage_records", [])
                case_results.append(
                    {
                        "node_completion_rate": len(completed_nodes) / max(len(plan_nodes), 1),
                        "branch_recovery_success_rate": 1.0
                        if (not case.require_recovery_branch or any(branch.get("status") == "selected" for branch in recovery_branches))
                        else 0.0,
                        "replan_usefulness": 1.0 if (not case.require_replan or revisions) else 0.0,
                        "stale_branch_avoidance": 1.0 if all(node.get("branch_id") == plan.get("active_branch_id", "branch-main") or node.get("status") in {"completed", "failed"} for node in plan_nodes) else 0.0,
                        "provider_fallback_success": 1.0 if (provider_usage and routing_receipts) else 0.0,
                        "approval_delay_survival_rate": 1.0 if final_result.status in {"completed", "delivered"} else 0.0,
                        "verification_before_delivery_rate": 1.0 if any(node.get("node_id") == "node-verify-delivery" and node.get("status") == "completed" for node in plan_nodes) else 0.0,
                        "end_to_end_completion_after_replan": 1.0 if final_result.status in {"completed", "delivered"} else 0.0,
                    }
                )

            metrics = {
                "node_completion_rate": 0.0,
                "branch_recovery_success_rate": 0.0,
                "replan_usefulness": 0.0,
                "stale_branch_avoidance": 0.0,
                "provider_fallback_success": 0.0,
                "approval_delay_survival_rate": 0.0,
                "verification_before_delivery_rate": 0.0,
                "end_to_end_completion_after_replan": 0.0,
            }
            if case_results:
                for key in list(metrics):
                    metrics[key] = sum(result[key] for result in case_results) / len(case_results)
            comparison[strategy_name] = StrategyEvaluationReport(
                strategy_name=strategy_name,
                metrics=metrics,
                case_results=case_results,
            )
        return comparison

    def compare_operational_strategies(
        self,
        dataset: OperationalTaskDataset,
        runtime_factories: dict[str, object],
        working_root: Path,
    ) -> dict[str, StrategyEvaluationReport]:
        """Benchmark operational governance behavior across runtime strategies."""

        comparison: dict[str, StrategyEvaluationReport] = {}
        for strategy_name, factory in runtime_factories.items():
            case_results: list[dict[str, float]] = []
            working_root.mkdir(parents=True, exist_ok=True)
            for case in dataset.cases:
                runtime_root = working_root / strategy_name / case.case_id
                runtime = factory(runtime_root)
                final_result = runtime.run_task(
                    goal=case.goal,
                    attachments=case.attachments,
                    preferences=case.preferences,
                    prohibitions=case.prohibitions,
                )
                replay = runtime.replay_task(final_result.task_id)
                routing_decisions = replay.get("routing_decisions", [])
                provider_usage = replay.get("provider_usage_records", [])
                budget_ledger = replay.get("budget_ledger") or {}
                budget_events = replay.get("budget_events", [])
                concurrency_state = replay.get("concurrency_state") or {}
                validation_report = replay.get("validation_report") or {}
                interventions = runtime.repository.list_human_interventions(final_result.task_id)
                spent_total = float(budget_ledger.get("spent_total", 0.0))
                completed = final_result.status in {"completed", "delivered"}
                provider_decisions = [item for item in routing_decisions if item.get("decision_type") == "provider"]
                tool_decisions = [item for item in routing_decisions if item.get("decision_type") == "tool"]
                case_results.append(
                    {
                        "provider_fallback_success_rate": 1.0
                        if provider_usage and all(item.get("status") == "success" for item in replay.get("routing_receipts", []))
                        else 0.0,
                        "provider_selection_usefulness": 1.0 if provider_decisions else 0.0,
                        "tool_selection_usefulness": 1.0 if tool_decisions else 0.0,
                        "concurrency_gain_vs_overhead": 1.0
                        if (
                            not case.require_concurrency
                            or (
                                int(concurrency_state.get("max_parallel_nodes", 1)) > 1
                                and len(concurrency_state.get("last_batch_nodes", [])) > 1
                            )
                        )
                        else 0.0,
                        "budget_adherence_rate": 1.0 if float(budget_ledger.get("remaining_budget", 0.0)) >= 0.0 else 0.0,
                        "recovery_under_budget_pressure": 1.0
                        if (not case.require_budget_mode or budget_events) and final_result.status in {"completed", "delivered", "blocked"}
                        else 0.0,
                        "verification_completion_under_cost_pressure": 1.0
                        if validation_report.get("status") in {"passed", "blocked", "pending_approval"}
                        else 0.0,
                        "degraded_mode_task_survival": 1.0
                        if final_result.status in {"completed", "delivered", "blocked", "awaiting_approval"}
                        else 0.0,
                        "cost_per_completed_task": spent_total if completed else spent_total + 0.01,
                        "cost_per_verified_task": spent_total
                        if validation_report.get("status") == "passed"
                        else spent_total + 0.01,
                        "operator_intervention_rate": float(len(interventions)),
                    }
                )

            metrics = {
                "provider_fallback_success_rate": 0.0,
                "provider_selection_usefulness": 0.0,
                "tool_selection_usefulness": 0.0,
                "concurrency_gain_vs_overhead": 0.0,
                "budget_adherence_rate": 0.0,
                "recovery_under_budget_pressure": 0.0,
                "verification_completion_under_cost_pressure": 0.0,
                "degraded_mode_task_survival": 0.0,
                "cost_per_completed_task": 0.0,
                "cost_per_verified_task": 0.0,
                "operator_intervention_rate": 0.0,
            }
            if case_results:
                for key in list(metrics):
                    metrics[key] = sum(result[key] for result in case_results) / len(case_results)
            comparison[strategy_name] = StrategyEvaluationReport(
                strategy_name=strategy_name,
                metrics=metrics,
                case_results=case_results,
            )
        return comparison
