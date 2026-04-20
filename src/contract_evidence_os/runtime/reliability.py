"""Cross-host reliability, prediction, and reconciliation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import uuid4

from contract_evidence_os.base import SchemaModel, utc_now


@dataclass
class FaultDomain(SchemaModel):
    version: str
    fault_domain_id: str
    domain_type: str
    scope: str
    status: str
    description: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class FaultDomainEvent(SchemaModel):
    version: str
    event_id: str
    fault_domain_id: str
    event_type: str
    summary: str
    severity: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ReliabilityIncident(SchemaModel):
    version: str
    incident_id: str
    fault_domain: str
    task_id: str
    incident_type: str
    severity: str
    status: str
    summary: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ReliabilityRecoveryPlan(SchemaModel):
    version: str
    plan_id: str
    incident_id: str
    recommended_action: str
    steps: list[str]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ConflictResolutionRecord(SchemaModel):
    version: str
    resolution_id: str
    lease_id: str
    stale_worker_id: str
    active_worker_id: str
    status: str
    reason: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class RuntimeDegradationRecord(SchemaModel):
    version: str
    record_id: str
    mode_name: str
    fault_domain: str
    reason: str
    status: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class LeasePredictionRecord(SchemaModel):
    version: str
    prediction_id: str
    lease_id: str
    worker_id: str
    host_id: str
    seconds_remaining: float
    renewal_latency_ms: float
    host_pressure: float
    provider_pressure: float
    criticality: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class LeaseRenewalForecast(SchemaModel):
    version: str
    forecast_id: str
    lease_id: str
    predicted_expiry_at: datetime
    recommended_action: str
    confidence: float
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class RenewalRiskScore(SchemaModel):
    version: str
    score_id: str
    lease_id: str
    risk_level: str
    score: float
    dominant_factors: list[str]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class LeaseSafetyMargin(SchemaModel):
    version: str
    margin_id: str
    lease_id: str
    recommended_margin_seconds: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class LeasePressureSignal(SchemaModel):
    version: str
    signal_id: str
    lease_id: str
    queue_pressure: float
    host_pressure: float
    provider_pressure: float
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class BackendOutageRecord(SchemaModel):
    version: str
    outage_id: str
    backend_name: str
    fault_domain: str
    summary: str
    status: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderOutageRecord(SchemaModel):
    version: str
    outage_id: str
    provider_name: str
    summary: str
    status: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class NetworkPartitionRecord(SchemaModel):
    version: str
    partition_id: str
    boundary: str
    summary: str
    status: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ReconciliationRun(SchemaModel):
    version: str
    run_id: str
    reason: str
    status: str
    repaired_records: int
    unresolved_records: int
    created_at: datetime = field(default_factory=utc_now)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class RecoveryBacklogRecord(SchemaModel):
    version: str
    backlog_id: str
    pending_reconciliation: int
    pending_conflicts: int
    pending_outages: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


class ReliabilityManager:
    """Predict renewal risk, quarantine conflicts, and reconcile shared-state drift."""

    def __init__(
        self,
        *,
        repository: Any,
        shared_state: Any | None = None,
        now_factory: Callable[[], datetime] = utc_now,
    ) -> None:
        self.repository = repository
        self.shared_state = shared_state
        self.now_factory = now_factory

    def predict_lease_renewal(
        self,
        *,
        lease_id: str,
        worker_id: str,
        host_id: str,
        seconds_remaining: float,
        renewal_latency_ms: float,
        host_pressure: float,
        provider_pressure: float,
        criticality: str,
    ) -> dict[str, SchemaModel]:
        now = self.now_factory()
        prediction = LeasePredictionRecord(
            version="1.0",
            prediction_id=f"lease-prediction-{uuid4().hex[:10]}",
            lease_id=lease_id,
            worker_id=worker_id,
            host_id=host_id,
            seconds_remaining=seconds_remaining,
            renewal_latency_ms=renewal_latency_ms,
            host_pressure=host_pressure,
            provider_pressure=provider_pressure,
            criticality=criticality,
            created_at=now,
        )
        margin_seconds = max(5, int(renewal_latency_ms / 200.0) + int(host_pressure * 10) + (3 if criticality in {"verification", "recovery"} else 0))
        pressure = LeasePressureSignal(
            version="1.0",
            signal_id=f"lease-pressure-{uuid4().hex[:10]}",
            lease_id=lease_id,
            queue_pressure=min(1.0, max(host_pressure, provider_pressure)),
            host_pressure=host_pressure,
            provider_pressure=provider_pressure,
            created_at=now,
        )
        score_value = min(
            1.0,
            (renewal_latency_ms / 1200.0)
            + (0.35 if seconds_remaining <= margin_seconds else 0.0)
            + (host_pressure * 0.3)
            + (provider_pressure * 0.2)
            + (0.15 if criticality in {"verification", "recovery"} else 0.0),
        )
        risk_level = "high" if score_value >= 0.8 else "medium" if score_value >= 0.45 else "low"
        risk = RenewalRiskScore(
            version="1.0",
            score_id=f"renewal-risk-{uuid4().hex[:10]}",
            lease_id=lease_id,
            risk_level=risk_level,
            score=score_value,
            dominant_factors=[
                factor
                for factor, enabled in {
                    "latency": renewal_latency_ms >= 500.0,
                    "low_time_remaining": seconds_remaining <= margin_seconds,
                    "host_pressure": host_pressure >= 0.5,
                    "provider_pressure": provider_pressure >= 0.5,
                    "criticality": criticality in {"verification", "recovery"},
                }.items()
                if enabled
            ],
            created_at=now,
        )
        safety = LeaseSafetyMargin(
            version="1.0",
            margin_id=f"lease-margin-{uuid4().hex[:10]}",
            lease_id=lease_id,
            recommended_margin_seconds=margin_seconds,
            created_at=now,
        )
        forecast = LeaseRenewalForecast(
            version="1.0",
            forecast_id=f"lease-renewal-forecast-{uuid4().hex[:10]}",
            lease_id=lease_id,
            predicted_expiry_at=now + timedelta(seconds=max(1, int(seconds_remaining - margin_seconds))),
            recommended_action="quarantine_if_conflict" if risk_level == "high" else "renew_now" if risk_level == "medium" else "renew_normally",
            confidence=max(0.25, 1.0 - abs(0.5 - score_value)),
            created_at=now,
        )
        self.repository.save_lease_prediction_record(prediction)
        self.repository.save_lease_renewal_forecast_record(forecast)
        self.repository.save_renewal_risk_score(risk)
        self.repository.save_lease_safety_margin(safety)
        self.repository.save_lease_pressure_signal(pressure)
        self._mirror("lease_prediction", prediction.prediction_id, lease_id, prediction)
        self._mirror("lease_renewal_forecast", forecast.forecast_id, lease_id, forecast)
        return {
            "prediction": prediction,
            "forecast": forecast,
            "risk": risk,
            "safety_margin": safety,
            "pressure": pressure,
        }

    def quarantine_conflict(
        self,
        *,
        lease_id: str,
        task_id: str,
        stale_worker_id: str,
        active_worker_id: str,
        reason: str,
    ) -> ReliabilityIncident:
        now = self.now_factory()
        incident = ReliabilityIncident(
            version="1.0",
            incident_id=f"reliability-incident-{uuid4().hex[:10]}",
            fault_domain="queue_lease_coordination",
            task_id=task_id,
            incident_type="ownership_conflict",
            severity="critical" if "stale owner" in reason else "high",
            status="open",
            summary=reason,
            created_at=now,
        )
        resolution = ConflictResolutionRecord(
            version="1.0",
            resolution_id=f"conflict-resolution-{uuid4().hex[:10]}",
            lease_id=lease_id,
            stale_worker_id=stale_worker_id,
            active_worker_id=active_worker_id,
            status="quarantined",
            reason=reason,
            created_at=now,
        )
        recovery = ReliabilityRecoveryPlan(
            version="1.0",
            plan_id=f"reliability-recovery-{uuid4().hex[:10]}",
            incident_id=incident.incident_id,
            recommended_action="reconcile lease ownership and resume from latest checkpoint",
            steps=[
                "reject stale-owner actions using current fencing token",
                "preserve incident bundle and ownership lineage",
                "resume from latest checkpoint on active owner",
            ],
            created_at=now,
        )
        degradation = RuntimeDegradationRecord(
            version="1.0",
            record_id=f"runtime-degradation-{uuid4().hex[:10]}",
            mode_name="reliability_quarantine",
            fault_domain="queue_lease_coordination",
            reason=reason,
            status="active",
            created_at=now,
        )
        self.repository.save_reliability_incident(incident)
        self.repository.save_conflict_resolution_record(resolution)
        self.repository.save_reliability_recovery_plan(recovery)
        self.repository.save_runtime_degradation_record(degradation)
        self._mirror("reliability_incident", incident.incident_id, task_id, incident)
        return incident

    def record_backend_outage(self, *, backend_name: str, fault_domain: str, summary: str) -> BackendOutageRecord:
        now = self.now_factory()
        record = BackendOutageRecord(
            version="1.0",
            outage_id=f"backend-outage-{uuid4().hex[:10]}",
            backend_name=backend_name,
            fault_domain=fault_domain,
            summary=summary,
            status="open",
            created_at=now,
        )
        self.repository.save_backend_outage_record(record)
        self.repository.save_fault_domain_event(
            FaultDomainEvent(
                version="1.0",
                event_id=f"fault-domain-event-{uuid4().hex[:10]}",
                fault_domain_id=fault_domain,
                event_type="backend_outage",
                summary=summary,
                severity="high",
                created_at=now,
            )
        )
        self._mirror("backend_outage", record.outage_id, backend_name, record)
        return record

    def run_reconciliation(self, *, reason: str) -> ReconciliationRun:
        now = self.now_factory()
        repaired = 0
        unresolved = 0
        notes: list[str] = []
        active_ownerships = self.repository.list_lease_ownerships(statuses=["active"])
        for ownership in active_ownerships:
            lease = self.repository.get_queue_lease(ownership.lease_id)
            if lease is None:
                unresolved += 1
                notes.append(f"missing_queue_lease:{ownership.lease_id}")
                continue
            if lease.fencing_token != ownership.fencing_token:
                repaired += 1
                notes.append(f"fencing_drift:{ownership.lease_id}")
        conflicts = len(self.repository.list_ownership_conflict_events())
        backlog = RecoveryBacklogRecord(
            version="1.0",
            backlog_id=f"recovery-backlog-{uuid4().hex[:10]}",
            pending_reconciliation=unresolved,
            pending_conflicts=conflicts,
            pending_outages=len([item for item in self.repository.list_backend_outage_records() if item.status == "open"]),
            created_at=now,
        )
        run = ReconciliationRun(
            version="1.0",
            run_id=f"reconciliation-run-{uuid4().hex[:10]}",
            reason=reason,
            status="completed" if repaired or unresolved or conflicts else "no_action",
            repaired_records=repaired,
            unresolved_records=unresolved,
            created_at=now,
            notes=notes,
        )
        self.repository.save_recovery_backlog_record(backlog)
        self.repository.save_reconciliation_run(run)
        self._mirror("reconciliation_run", run.run_id, "runtime", run)
        return run

    def _mirror(self, record_type: str, record_id: str, scope_key: str, model: SchemaModel) -> None:
        if self.shared_state is None:
            return
        self.shared_state.upsert_record(
            record_type=record_type,
            record_id=record_id,
            scope_key=scope_key,
            payload=model.to_dict(),
        )
