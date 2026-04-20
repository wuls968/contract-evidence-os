from datetime import UTC, datetime, timedelta
from pathlib import Path

from contract_evidence_os.evals.models import StrategyEvaluationReport
from contract_evidence_os.runtime.policy_registry import PolicyRegistryManager, PolicyScope
from contract_evidence_os.runtime.provider_health import ProviderAvailabilityPolicy, ProviderHealthManager
from contract_evidence_os.storage.repository import SQLiteRepository


def _now() -> datetime:
    return datetime(2026, 4, 17, 0, 0, tzinfo=UTC)


def test_provider_health_tracks_rate_limit_pressure_and_circuit_breaker_recovery(tmp_path: Path) -> None:
    repo = SQLiteRepository(tmp_path / "ceos.sqlite3")
    manager = ProviderHealthManager(repository=repo)
    repo.save_provider_availability_policy(
        ProviderAvailabilityPolicy(
            version="1.0",
            policy_id="provider-policy-001",
            provider_name="anthropic_live",
            failure_threshold=2,
            cooldown_seconds=1,
            rate_limit_window_seconds=60,
            max_requests_per_window=1,
            created_at=_now(),
        )
    )

    assert manager.try_acquire_capacity("anthropic_live", now=_now())
    assert not manager.try_acquire_capacity("anthropic_live", now=_now() + timedelta(seconds=1))

    manager.record_failure("anthropic_live", error_code="rate_limited", latency_ms=1200.0, at=_now() + timedelta(seconds=2))
    manager.record_failure("anthropic_live", error_code="timeout", latency_ms=1300.0, at=_now() + timedelta(seconds=3))
    snapshot = manager.snapshot(["anthropic_live"], now=_now() + timedelta(seconds=3))
    assert snapshot.records[0].circuit_state == "open"

    manager.force_half_open_probe("anthropic_live", at=_now() + timedelta(seconds=5))
    probe_snapshot = manager.snapshot(["anthropic_live"], now=_now() + timedelta(seconds=5))
    assert probe_snapshot.records[0].circuit_state == "half_open"

    manager.record_success("anthropic_live", latency_ms=140.0, structured_output_ok=True, at=_now() + timedelta(seconds=6))
    recovered = manager.snapshot(["anthropic_live"], now=_now() + timedelta(seconds=6))
    assert recovered.records[0].circuit_state == "closed"


def test_policy_registry_promotes_and_rolls_back_eval_gated_candidate_from_scorecard_traces(tmp_path: Path) -> None:
    repo = SQLiteRepository(tmp_path / "ceos.sqlite3")
    registry = PolicyRegistryManager(repository=repo)
    scope = PolicyScope(
        version="1.0",
        scope_id="policy-scope-001",
        scope_type="routing",
        target_component="provider_selection",
        constraints=["no_policy_boundary_violation"],
        created_at=_now(),
    )
    baseline = registry.register_policy_version(
        name="routing-default",
        scope=scope,
        policy_payload={"prefer_low_cost": False, "prefer_reliable_tools": True},
        summary="Baseline routing policy.",
    )
    evidence = registry.build_evidence_bundle(
        scope=scope,
        source_refs=["provider_scorecard:anthropic_live", "routing_decision:routing-001"],
        summary="Anthropic is cheaper and survives provider pressure with acceptable quality.",
    )
    candidate = registry.propose_candidate_from_evidence(
        name="routing-low-cost-pressure",
        scope=scope,
        base_version_id=baseline.version_id,
        policy_payload={"prefer_low_cost": True, "prefer_reliable_tools": True},
        evidence_bundle=evidence,
        hypothesis="Bias toward lower-cost provider under system pressure.",
    )

    report = StrategyEvaluationReport(
        strategy_name="candidate",
        metrics={
            "provider_pressure_survival_rate": 1.0,
            "verified_completion_rate_under_load": 1.0,
            "policy_violation_rate": 0.0,
            "queue_latency": 0.1,
        },
    )
    promotion_run = registry.evaluate_candidate(candidate.candidate_id, report=report)
    assert promotion_run.status == "passed"

    promoted = registry.promote_candidate(candidate.candidate_id)
    assert promoted.status == "promoted"

    rollback = registry.rollback_scope(scope.scope_id, reason="operator requested rollback")
    assert rollback.scope_id == scope.scope_id
    assert rollback.rollback_reason == "operator requested rollback"


def test_provider_health_snapshot_marks_rate_limited_provider_state(tmp_path: Path) -> None:
    repo = SQLiteRepository(tmp_path / "ceos.sqlite3")
    manager = ProviderHealthManager(repository=repo)
    repo.save_provider_availability_policy(
        ProviderAvailabilityPolicy(
            version="1.0",
            policy_id="provider-policy-001",
            provider_name="anthropic_live",
            failure_threshold=3,
            cooldown_seconds=5,
            rate_limit_window_seconds=60,
            max_requests_per_window=1,
            created_at=_now(),
        )
    )
    assert manager.try_acquire_capacity("anthropic_live", now=_now())
    assert not manager.try_acquire_capacity("anthropic_live", now=_now() + timedelta(seconds=1))
    snapshot = manager.snapshot(["anthropic_live"], now=_now() + timedelta(seconds=1))
    assert snapshot.records[0].availability_state == "rate_limited"
