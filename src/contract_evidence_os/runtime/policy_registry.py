"""Adaptive policy registry and eval-gated promotion pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from contract_evidence_os.base import SchemaModel, utc_now
from contract_evidence_os.evals.models import StrategyEvaluationReport


@dataclass
class PolicyScope(SchemaModel):
    """Scope boundary for one family of policies."""

    version: str
    scope_id: str
    scope_type: str
    target_component: str
    constraints: list[str]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class PolicyVersion(SchemaModel):
    """Active or historical policy version."""

    version: str
    version_id: str
    name: str
    scope_id: str
    status: str
    policy_payload: dict[str, Any]
    summary: str
    supersedes_version_id: str = ""
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class PolicyEvidenceBundle(SchemaModel):
    """Evidence bundle supporting a policy proposal or evaluation."""

    version: str
    bundle_id: str
    scope_id: str
    source_refs: list[str]
    summary: str
    metrics: dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class PolicyCandidate(SchemaModel):
    """Candidate policy derived from operational traces or scorecards."""

    version: str
    candidate_id: str
    name: str
    scope_id: str
    base_version_id: str
    policy_payload: dict[str, Any]
    evidence_bundle_id: str
    hypothesis: str
    status: str = "candidate"
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class PolicyPromotionRun(SchemaModel):
    """Eval-gated promotion decision for a policy candidate."""

    version: str
    run_id: str
    candidate_id: str
    status: str
    gain: float
    regressions: int
    summary: str
    report_metrics: dict[str, float]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class PolicyRollbackRecord(SchemaModel):
    """Rollback of an active policy scope to a previous version."""

    version: str
    rollback_id: str
    scope_id: str
    previous_version_id: str
    restored_version_id: str
    rollback_reason: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


class PolicyRegistryManager:
    """Manage policy versions, candidates, promotion runs, and rollbacks."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def register_policy_version(
        self,
        *,
        name: str,
        scope: PolicyScope,
        policy_payload: dict[str, Any],
        summary: str,
        supersedes_version_id: str = "",
    ) -> PolicyVersion:
        self.repository.save_policy_scope(scope)
        for version in self.repository.list_policy_versions(scope.scope_id):
            if version.status == "active":
                version.status = "superseded"
                self.repository.save_policy_version(version)
        version = PolicyVersion(
            version="1.0",
            version_id=f"policy-version-{uuid4().hex[:10]}",
            name=name,
            scope_id=scope.scope_id,
            status="active",
            policy_payload=policy_payload,
            summary=summary,
            supersedes_version_id=supersedes_version_id,
        )
        self.repository.save_policy_version(version)
        return version

    def build_evidence_bundle(
        self,
        *,
        scope: PolicyScope,
        source_refs: list[str],
        summary: str,
        metrics: dict[str, float] | None = None,
    ) -> PolicyEvidenceBundle:
        self.repository.save_policy_scope(scope)
        bundle = PolicyEvidenceBundle(
            version="1.0",
            bundle_id=f"policy-evidence-{uuid4().hex[:10]}",
            scope_id=scope.scope_id,
            source_refs=source_refs,
            summary=summary,
            metrics={} if metrics is None else metrics,
        )
        self.repository.save_policy_evidence_bundle(bundle)
        return bundle

    def propose_candidate_from_evidence(
        self,
        *,
        name: str,
        scope: PolicyScope,
        base_version_id: str,
        policy_payload: dict[str, Any],
        evidence_bundle: PolicyEvidenceBundle,
        hypothesis: str,
    ) -> PolicyCandidate:
        candidate = PolicyCandidate(
            version="1.0",
            candidate_id=f"policy-candidate-{uuid4().hex[:10]}",
            name=name,
            scope_id=scope.scope_id,
            base_version_id=base_version_id,
            policy_payload=policy_payload,
            evidence_bundle_id=evidence_bundle.bundle_id,
            hypothesis=hypothesis,
        )
        self.repository.save_policy_candidate(candidate)
        return candidate

    def evaluate_candidate(
        self,
        candidate_id: str,
        *,
        report: StrategyEvaluationReport,
    ) -> PolicyPromotionRun:
        gain = (
            float(report.metrics.get("provider_pressure_survival_rate", 0.0))
            + float(report.metrics.get("verified_completion_rate_under_load", 0.0))
            + (1.0 - float(report.metrics.get("policy_violation_rate", 0.0)))
            - float(report.metrics.get("queue_latency", 0.0))
        )
        regressions = 0 if float(report.metrics.get("policy_violation_rate", 0.0)) <= 0.0 else 1
        run = PolicyPromotionRun(
            version="1.0",
            run_id=f"policy-promotion-run-{uuid4().hex[:10]}",
            candidate_id=candidate_id,
            status="passed" if gain > 1.5 and regressions == 0 else "failed",
            gain=gain,
            regressions=regressions,
            summary="policy candidate evaluation completed",
            report_metrics={key: float(value) for key, value in report.metrics.items()},
        )
        self.repository.save_policy_promotion_run(run)
        candidate = self.repository.load_policy_candidate(candidate_id)
        candidate.status = "evaluated" if run.status == "passed" else "rejected"
        self.repository.save_policy_candidate(candidate)
        return run

    def promote_candidate(self, candidate_id: str) -> PolicyPromotionRun:
        candidate = self.repository.load_policy_candidate(candidate_id)
        latest_run = self.repository.latest_policy_promotion_run(candidate_id)
        if latest_run is None or latest_run.status != "passed":
            raise ValueError(f"candidate {candidate_id} has not passed evaluation")
        scope = self.repository.load_policy_scope(candidate.scope_id)
        version = self.register_policy_version(
            name=candidate.name,
            scope=scope,
            policy_payload=candidate.policy_payload,
            summary=candidate.hypothesis,
            supersedes_version_id=candidate.base_version_id,
        )
        candidate.status = "promoted"
        self.repository.save_policy_candidate(candidate)
        latest_run.status = "promoted"
        latest_run.summary = f"promoted as {version.version_id}"
        self.repository.save_policy_promotion_run(latest_run)
        return latest_run

    def rollback_scope(self, scope_id: str, *, reason: str) -> PolicyRollbackRecord:
        versions = self.repository.list_policy_versions(scope_id)
        active = next((version for version in versions if version.status == "active"), None)
        previous = next((version for version in versions if version.status in {"superseded", "rolled_back"}), None)
        if active is None or previous is None:
            raise ValueError(f"scope {scope_id} does not have enough history to roll back")
        active.status = "rolled_back"
        previous.status = "active"
        self.repository.save_policy_version(active)
        self.repository.save_policy_version(previous)
        rollback = PolicyRollbackRecord(
            version="1.0",
            rollback_id=f"policy-rollback-{uuid4().hex[:10]}",
            scope_id=scope_id,
            previous_version_id=active.version_id,
            restored_version_id=previous.version_id,
            rollback_reason=reason,
        )
        self.repository.save_policy_rollback_record(rollback)
        return rollback
