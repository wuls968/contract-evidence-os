"""Governed evolution pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.evals.models import StrategyEvaluationReport
from contract_evidence_os.evolution.models import (
    CanaryRun,
    EvaluationRun,
    EvolutionCandidate,
    MemoryLifecycleTrace,
    MemoryPolicyAnalyticsRecord,
    MemoryPolicyMiningRun,
)
from contract_evidence_os.memory.models import SkillCapsule
from contract_evidence_os.storage.repository import SQLiteRepository


@dataclass
class EvolutionEngine:
    """Track candidate generation, evaluation, canarying, and promotion."""

    repository: SQLiteRepository | None = None
    candidates: dict[str, EvolutionCandidate] = field(default_factory=dict)
    evaluations: dict[str, EvaluationRun] = field(default_factory=dict)
    canaries: dict[str, CanaryRun] = field(default_factory=dict)
    distilled_skills: dict[str, SkillCapsule] = field(default_factory=dict)
    memory_lifecycle_traces: dict[str, MemoryLifecycleTrace] = field(default_factory=dict)
    memory_policy_mining_runs: dict[str, MemoryPolicyMiningRun] = field(default_factory=dict)
    memory_policy_analytics: dict[str, MemoryPolicyAnalyticsRecord] = field(default_factory=dict)

    def propose_candidate(
        self,
        candidate_type: str,
        source_traces: list[str],
        target_component: str,
        hypothesis: str,
    ) -> EvolutionCandidate:
        candidate = EvolutionCandidate(
            version="1.0",
            candidate_id=f"candidate-{uuid4().hex[:10]}",
            candidate_type=candidate_type,
            source_traces=source_traces,
            target_component=target_component,
            hypothesis=hypothesis,
            expected_benefit="improve verified execution quality",
            evaluation_suite=["offline-core", "regression-core", "safety-boundaries"],
            canary_scope="limited",
            rollback_plan="restore previous candidate state",
            promotion_result="pending",
        )
        self.candidates[candidate.candidate_id] = candidate
        if self.repository is not None:
            self.repository.save_evolution_candidate(candidate)
        return candidate

    def evaluate_candidate(
        self,
        candidate_id: str,
        regression_failures: int | None = None,
        gain: float | None = None,
        report: StrategyEvaluationReport | None = None,
    ) -> EvaluationRun:
        now = utc_now()
        candidate = self.candidates.get(candidate_id)
        if candidate is None and self.repository is not None:
            candidate = self.repository.load_evolution_candidate(candidate_id)
            self.candidates[candidate_id] = candidate
        if report is not None:
            factual = float(report.metrics.get("factual_correctness_rate", 0.0))
            evidence = float(report.metrics.get("evidence_coverage_rate", 0.0))
            policy_metric = float(report.metrics.get("policy_violation_rate", 1.0))
            policy_safety = policy_metric if policy_metric > 0.5 else 1.0 - policy_metric
            gain = factual + evidence + policy_safety - 2.0
            regression_failures = 0 if report.metrics.get("evidence_coverage_rate", 0.0) >= 0.95 else 1
            if candidate is not None and candidate.target_component.startswith("continuity."):
                continuity_ok = (
                    float(report.metrics.get("resumed_task_completion_rate", 0.0)) >= 1.0
                    and float(report.metrics.get("handoff_quality", 0.0)) >= 0.4
                    and float(report.metrics.get("continuity_reconstruction_accuracy", 0.0)) >= 0.7
                    and float(report.metrics.get("open_question_resolution_rate", 0.0)) >= 0.5
                )
                if not continuity_ok:
                    regression_failures = max(1, 0 if regression_failures is None else regression_failures)
            if candidate is not None and (
                candidate.candidate_type == "memory_policy" or candidate.target_component.startswith("memory.policy.")
            ):
                quarantine = float(report.metrics.get("quarantine_precision_rate", 0.0))
                purge = float(report.metrics.get("hard_purge_compliance_rate", 0.0))
                timeline = float(report.metrics.get("timeline_reconstruction_rate", 0.0))
                selective_purge_present = "selective_purge_precision_rate" in report.metrics
                learned_admission_present = "learned_admission_gain_rate" in report.metrics
                cross_scope_present = "cross_scope_timeline_reconstruction_rate" in report.metrics
                hard_purge_artifact_present = "artifact_hard_purge_precision_rate" in report.metrics
                contradiction_merge_present = "contradiction_aware_timeline_merge_rate" in report.metrics
                policy_analytics_present = "memory_policy_analytics_visibility_rate" in report.metrics
                selective_purge = float(report.metrics.get("selective_purge_precision_rate", 0.0))
                learned_admission = float(report.metrics.get("learned_admission_gain_rate", 0.0))
                cross_scope_timeline = float(report.metrics.get("cross_scope_timeline_reconstruction_rate", timeline))
                hard_purge_artifact = float(report.metrics.get("artifact_hard_purge_precision_rate", purge))
                contradiction_merge = float(report.metrics.get("contradiction_aware_timeline_merge_rate", timeline))
                policy_analytics = float(report.metrics.get("memory_policy_analytics_visibility_rate", 0.0))
                if (
                    selective_purge_present
                    or learned_admission_present
                    or cross_scope_present
                    or hard_purge_artifact_present
                    or contradiction_merge_present
                    or policy_analytics_present
                ):
                    gain = (
                        quarantine
                        + purge
                        + timeline
                        + selective_purge
                        + learned_admission
                        + cross_scope_timeline
                        + hard_purge_artifact
                        + contradiction_merge
                        + policy_analytics
                        - 4.5
                    )
                    memory_policy_ok = (
                        quarantine >= 0.8
                        and purge >= 0.8
                        and timeline >= 0.8
                        and (not selective_purge_present or selective_purge >= 0.8)
                        and (not learned_admission_present or learned_admission >= 0.5)
                        and (not cross_scope_present or cross_scope_timeline >= 0.8)
                        and (not hard_purge_artifact_present or hard_purge_artifact >= 0.8)
                        and (not contradiction_merge_present or contradiction_merge >= 0.8)
                        and (not policy_analytics_present or policy_analytics >= 0.8)
                        and float(report.metrics.get("policy_violation_rate", 1.0)) <= 0.05
                    )
                else:
                    gain = quarantine + purge + timeline - 1.5
                    memory_policy_ok = (
                        quarantine >= 0.8
                        and purge >= 0.8
                        and timeline >= 0.8
                        and float(report.metrics.get("policy_violation_rate", 1.0)) <= 0.05
                    )
                if not memory_policy_ok:
                    regression_failures = max(1, 0 if regression_failures is None else regression_failures)
                else:
                    regression_failures = 0
        regression_failures = 0 if regression_failures is None else regression_failures
        gain = 0.0 if gain is None else gain
        run = EvaluationRun(
            version="1.0",
            run_id=f"eval-{uuid4().hex[:10]}",
            candidate_id=candidate_id,
            suite_name="offline-core",
            status="passed" if regression_failures == 0 and gain > 0 else "failed",
            metrics={"regression_failures": regression_failures, "gain": gain},
            started_at=now,
            completed_at=utc_now(),
        )
        self.evaluations[candidate_id] = run
        if self.repository is not None:
            self.repository.save_evaluation_run(run)
        return run

    def analyze_memory_policy_candidates(self, *, scope_key: str) -> list[MemoryPolicyAnalyticsRecord]:
        existing_records: list[MemoryPolicyAnalyticsRecord] = []
        if self.repository is not None:
            existing_records = self.repository.list_memory_policy_analytics_records(scope_key=scope_key)
            for record in existing_records:
                self.memory_policy_analytics[record.analytics_id] = record
        existing_by_candidate = {record.candidate_id: record for record in existing_records}
        traces = [
            trace for trace in self.memory_lifecycle_traces.values() if trace.scope_key == scope_key
        ]
        if not traces and self.repository is not None:
            traces = self.repository.list_memory_lifecycle_traces(scope_key=scope_key)
            for trace in traces:
                self.memory_lifecycle_traces[trace.trace_id] = trace
        if not traces and existing_records:
            return sorted(existing_records, key=lambda item: item.created_at, reverse=True)
        source_trace_ids = [trace.trace_id for trace in traces]
        candidates = [
            candidate
            for candidate in self.candidates.values()
            if candidate.candidate_type == "memory_policy"
            and any(trace_id in source_trace_ids for trace_id in candidate.source_traces)
        ]
        if not candidates and self.repository is not None:
            candidates = [
                candidate
                for candidate in self.repository.list_evolution_candidates()
                if candidate.candidate_type == "memory_policy"
                and any(trace_id in source_trace_ids for trace_id in candidate.source_traces)
            ]
            for candidate in candidates:
                self.candidates[candidate.candidate_id] = candidate
        analytics: list[MemoryPolicyAnalyticsRecord] = []
        for candidate in candidates:
            evaluation = self.evaluations.get(candidate.candidate_id)
            if evaluation is None and self.repository is not None:
                runs = self.repository.list_evaluation_runs(candidate.candidate_id)
                evaluation = None if not runs else runs[-1]
                if evaluation is not None:
                    self.evaluations[candidate.candidate_id] = evaluation
            canary = self.canaries.get(candidate.candidate_id)
            if canary is None and self.repository is not None:
                runs = self.repository.list_canary_runs(candidate.candidate_id)
                canary = None if not runs else runs[-1]
                if canary is not None:
                    self.canaries[candidate.candidate_id] = canary
            recommendation = "hold"
            rollback_risk = 0.0
            if canary is not None and canary.status == "rolled_back":
                recommendation = "rollback"
                rollback_risk = min(
                    1.0,
                    float(canary.metrics.get("anomaly_count", 0)) / 4.0
                    + max(0.0, 1.0 - float(canary.metrics.get("success_rate", 0.0))),
                )
            elif evaluation is not None and evaluation.status != "passed":
                recommendation = "iterate"
                rollback_risk = min(1.0, float(evaluation.metrics.get("regression_failures", 0)) / 2.0)
            elif candidate.promotion_result == "promoted":
                recommendation = "promote"
            elif canary is not None and canary.status == "promoted":
                recommendation = "promote"
            elif evaluation is not None and evaluation.status == "passed":
                recommendation = "canary"
            rationale = (
                "Candidate rolled back because canary anomalies exceeded the safe threshold."
                if recommendation == "rollback"
                else "Candidate is ready for promotion."
                if recommendation == "promote"
                else "Candidate passed offline evaluation and is ready for canary validation."
                if recommendation == "canary"
                else "Candidate needs another policy iteration before rollout."
            )
            existing = existing_by_candidate.get(candidate.candidate_id)
            if (
                existing is not None
                and existing.recommendation == recommendation
                and existing.evaluation_status == (None if evaluation is None else evaluation.status)
                and existing.canary_status == (None if canary is None else canary.status)
                and existing.promotion_state == candidate.promotion_result
            ):
                analytics.append(existing)
                continue
            record = MemoryPolicyAnalyticsRecord(
                version="1.0",
                analytics_id=f"memory-policy-analytics-{uuid4().hex[:10]}",
                scope_key=scope_key,
                candidate_id=candidate.candidate_id,
                recommendation=recommendation,
                supporting_trace_ids=list(candidate.source_traces),
                evaluation_status=None if evaluation is None else evaluation.status,
                canary_status=None if canary is None else canary.status,
                promotion_state=candidate.promotion_result,
                rollback_risk=rollback_risk,
                rationale=rationale,
                created_at=utc_now(),
            )
            self.memory_policy_analytics[record.analytics_id] = record
            analytics.append(record)
            if self.repository is not None:
                self.repository.save_memory_policy_analytics_record(record)
        return sorted(analytics, key=lambda item: item.created_at, reverse=True)

    def _persist_memory_policy_analytics_for_candidate(self, candidate: EvolutionCandidate) -> None:
        if candidate.candidate_type != "memory_policy":
            return
        trace_scopes = {
            trace.scope_key
            for trace_id in candidate.source_traces
            for trace in [self.memory_lifecycle_traces.get(trace_id)]
            if trace is not None
        }
        if not trace_scopes and self.repository is not None:
            for scope_key in {
                record.scope_key
                for record in self.repository.list_memory_lifecycle_traces()
                if record.trace_id in candidate.source_traces
            }:
                trace_scopes.add(scope_key)
        for scope_key in trace_scopes:
            self.analyze_memory_policy_candidates(scope_key=scope_key)

    def record_memory_lifecycle_trace(
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
        self.memory_lifecycle_traces[trace.trace_id] = trace
        if self.repository is not None:
            self.repository.save_memory_lifecycle_trace(trace)
        return trace

    def mine_memory_policy_candidates(
        self,
        *,
        scope_key: str,
        admission_canary_runs: list[object] | None = None,
        promotion_recommendations: list[object] | None = None,
    ) -> list[EvolutionCandidate]:
        traces = [
            trace for trace in self.memory_lifecycle_traces.values() if trace.scope_key == scope_key
        ]
        if not traces and self.repository is not None:
            traces = self.repository.list_memory_lifecycle_traces(scope_key=scope_key)
            for trace in traces:
                self.memory_lifecycle_traces[trace.trace_id] = trace
        if admission_canary_runs is None and self.repository is not None:
            admission_canary_runs = self.repository.list_memory_admission_canary_runs(scope_key=scope_key)
        admission_canary_runs = [] if admission_canary_runs is None else list(admission_canary_runs)
        if promotion_recommendations is None and self.repository is not None:
            promotion_recommendations = self.repository.list_memory_admission_promotion_recommendations(scope_key=scope_key)
        promotion_recommendations = [] if promotion_recommendations is None else list(promotion_recommendations)
        suspicious_events = sum(
            1
            for trace in traces
            for event in trace.events
            if event in {"candidate_quarantined", "suspicious_override_detected", "selective_purge_completed", "cross_scope_timeline_rebuilt"}
        )
        promote_canaries = [
            run
            for run in admission_canary_runs
            if getattr(run, "recommendation", "") == "promote"
            and float(getattr(run, "metrics", {}).get("high_risk_override_count", 0.0)) >= 1.0
        ]
        strong_recommendations = [
            record
            for record in promotion_recommendations
            if getattr(record, "recommendation", "") == "promote" and float(getattr(record, "confidence", 0.0)) >= 0.5
        ]
        if suspicious_events < 2 and not promote_canaries and not strong_recommendations:
            return []
        if not traces:
            traces = [
                self.record_memory_lifecycle_trace(
                    scope_key=scope_key,
                    events=["admission_canary_promote"],
                    metrics={"memory_canary_override_gain": float(len(promote_canaries))},
                )
            ]
        candidate = self.propose_memory_policy_candidate(
            lifecycle_trace=traces[0],
            target_component="memory.policy.admission",
            hypothesis="Tighten admission sensitivity from memory-canary evidence and preserve selective purge for repeated override-shaped traces.",
        )
        candidate.evaluation_suite = [
            "offline-core",
            "memory-lifecycle",
            "memory-governance",
            "regression-core",
            "safety-boundaries",
        ]
        mining_run = MemoryPolicyMiningRun(
            version="1.0",
            run_id=f"memory-policy-mining-{uuid4().hex[:10]}",
            scope_key=scope_key,
            trace_ids=[trace.trace_id for trace in traces],
            proposed_candidate_ids=[candidate.candidate_id],
            rationale="Repeated quarantine traces and admission canary deltas justify a tighter memory governance candidate.",
            created_at=utc_now(),
            source_canary_run_ids=[run.run_id for run in admission_canary_runs],
            source_recommendation_ids=[record.recommendation_id for record in promotion_recommendations],
        )
        self.memory_policy_mining_runs[mining_run.run_id] = mining_run
        if self.repository is not None:
            self.repository.save_evolution_candidate(candidate)
            self.repository.save_memory_policy_mining_run(mining_run)
        return [candidate]

    def propose_memory_policy_candidate(
        self,
        *,
        lifecycle_trace: MemoryLifecycleTrace,
        target_component: str,
        hypothesis: str,
    ) -> EvolutionCandidate:
        candidate = self.propose_candidate(
            candidate_type="memory_policy",
            source_traces=[lifecycle_trace.trace_id],
            target_component=target_component,
            hypothesis=hypothesis,
        )
        candidate.evaluation_suite = [
            "offline-core",
            "memory-lifecycle",
            "regression-core",
            "safety-boundaries",
        ]
        candidate.expected_benefit = "improve memory admission, purge compliance, and timeline recovery quality"
        if self.repository is not None:
            self.repository.save_evolution_candidate(candidate)
        return candidate

    def propose_continuity_candidate(
        self,
        source_traces: list[str],
        target_component: str,
        hypothesis: str,
    ) -> EvolutionCandidate:
        """Create a continuity-focused candidate that must pass long-horizon evals."""

        candidate = self.propose_candidate(
            candidate_type="continuity_heuristic",
            source_traces=source_traces,
            target_component=target_component,
            hypothesis=hypothesis,
        )
        candidate.evaluation_suite = [
            "offline-core",
            "long-horizon-continuity",
            "regression-core",
            "safety-boundaries",
        ]
        if self.repository is not None:
            self.repository.save_evolution_candidate(candidate)
        return candidate

    def mine_long_horizon_patterns(self, trace_bundle: dict[str, object]) -> dict[str, object]:
        """Extract continuity-relevant motifs from a full task lifecycle bundle."""

        open_questions = trace_bundle.get("open_questions", [])
        telemetry = trace_bundle.get("telemetry", [])
        replay = trace_bundle.get("replay", {})
        task = replay.get("task", {}) if isinstance(replay, dict) else {}
        return {
            "session_boundaries": sum(
                1 for item in telemetry if item.get("event_type") in {"session_boundary", "task_resumed"}
            ),
            "handoff_present": trace_bundle.get("handoff") is not None,
            "open_question_count": len(open_questions),
            "final_status": task.get("status"),
        }

    def run_canary(self, candidate_id: str, success_rate: float, anomaly_count: int) -> CanaryRun:
        now = utc_now()
        run = CanaryRun(
            version="1.0",
            run_id=f"canary-{uuid4().hex[:10]}",
            candidate_id=candidate_id,
            scope="limited",
            status="promoted" if success_rate >= 0.95 and anomaly_count == 0 else "rolled_back",
            metrics={"success_rate": success_rate, "anomaly_count": anomaly_count},
            started_at=now,
            completed_at=utc_now(),
        )
        self.canaries[candidate_id] = run
        if self.repository is not None:
            self.repository.save_canary_run(run)
        return run

    def promote_candidate(self, candidate_id: str) -> EvolutionCandidate:
        candidate = self.candidates.get(candidate_id)
        if candidate is None and self.repository is not None:
            candidate = self.repository.load_evolution_candidate(candidate_id)
            self.candidates[candidate_id] = candidate
        if candidate is None:
            raise KeyError(candidate_id)
        evaluation = self.evaluations.get(candidate_id)
        canary = self.canaries.get(candidate_id)
        if evaluation and canary and evaluation.status == "passed" and canary.status == "promoted":
            candidate.promotion_result = "promoted"
        else:
            candidate.promotion_result = "rolled_back"
        if self.repository is not None:
            self.repository.save_evolution_candidate(candidate)
        self._persist_memory_policy_analytics_for_candidate(candidate)
        return candidate

    def rollback_candidate(self, candidate_id: str) -> EvolutionCandidate:
        candidate = self.candidates[candidate_id]
        candidate.promotion_result = "rolled_back"
        if self.repository is not None:
            self.repository.save_evolution_candidate(candidate)
        self._persist_memory_policy_analytics_for_candidate(candidate)
        return candidate

    def mine_patterns(self, traces: list[dict[str, object]]) -> dict[str, object]:
        """Extract a simple repeated tool sequence motif from traces."""

        sequence = [str(trace.get("event_type", "unknown")) for trace in traces]
        return {
            "sequence": sequence,
            "trace_count": len(traces),
            "high_yield": "tool_invocation" in sequence and "delivery" in sequence,
        }

    def distill_skill_capsule(self, name: str, traces: list[dict[str, object]]) -> SkillCapsule:
        """Convert successful traces into a reusable procedural capsule."""

        capsule = SkillCapsule(
            version="1.0",
            skill_id=f"skill-{uuid4().hex[:10]}",
            name=name,
            triggering_conditions=["successful verified task"],
            preferred_plan_pattern=[str(trace.get("event_type", "unknown")) for trace in traces],
            tool_sequence=[
                str(tool_ref)
                for trace in traces
                for tool_ref in trace.get("tool_refs", [])
            ],
            validation_pattern=["shadow_verification"],
            failure_signals=["verification_failure", "permission_denial"],
            memory_write_policy="promote_after_eval",
            test_cases=["tests/integration/test_vertical_slice.py"],
            promotion_status="candidate",
            regression_risk="moderate",
        )
        self.distilled_skills[capsule.skill_id] = capsule
        if self.repository is not None:
            self.repository.save_skill_capsule(capsule)
        return capsule
