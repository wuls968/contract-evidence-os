"""Forecast-aware provider capacity and quota governance."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

from contract_evidence_os.base import SchemaModel, utc_now


@dataclass
class ProviderDemandForecast(SchemaModel):
    version: str
    forecast_id: str
    provider_name: str
    role: str
    observed_demand: int
    projected_demand: int
    fallback_pressure: float
    reservation_pressure: float
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderCapacityForecast(SchemaModel):
    version: str
    forecast_id: str
    provider_name: str
    available_units: int
    projected_shortfall: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderQuotaPolicy(SchemaModel):
    version: str
    policy_id: str
    provider_name: str
    per_role_quota: dict[str, int]
    protected_reservations: dict[str, int]
    low_priority_cap: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ReservationForecast(SchemaModel):
    version: str
    forecast_id: str
    provider_name: str
    reservation_type: str
    reserved_units: int
    projected_needed: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class CapacityTrendRecord(SchemaModel):
    version: str
    trend_id: str
    provider_name: str
    utilization_ratio: float
    demand_delta: float
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class QuotaExhaustionRisk(SchemaModel):
    version: str
    risk_id: str
    provider_name: str
    risk_level: str
    projected_exhaustion_minutes: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class QuotaGovernanceDecision(SchemaModel):
    version: str
    decision_id: str
    provider_name: str
    task_id: str
    role: str
    workload: str
    priority_class: str
    requested_units: int
    allowed: bool
    reason: str
    applied_reservation_protection: bool
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


class ProviderCapacityForecaster:
    """Persist simple, auditable provider demand and shortfall forecasts."""

    def __init__(self, *, repository: Any, shared_state: Any | None = None, now_factory: Callable[[], datetime] = utc_now) -> None:
        self.repository = repository
        self.shared_state = shared_state
        self.now_factory = now_factory

    def record_provider_demand(
        self,
        *,
        provider_name: str,
        role: str,
        observed_demand: int,
        projected_demand: int,
        fallback_pressure: float,
        reservation_pressure: float,
    ) -> ProviderDemandForecast:
        now = self.now_factory()
        forecast = ProviderDemandForecast(
            version="1.0",
            forecast_id=f"provider-demand-{uuid4().hex[:10]}",
            provider_name=provider_name,
            role=role,
            observed_demand=observed_demand,
            projected_demand=max(observed_demand, projected_demand),
            fallback_pressure=fallback_pressure,
            reservation_pressure=reservation_pressure,
            created_at=now,
        )
        capacity = next((item for item in self.repository.list_provider_capacity_records() if item.provider_name == provider_name), None)
        available = 0 if capacity is None else capacity.max_parallel
        shortfall = max(0, forecast.projected_demand - available)
        capacity_forecast = ProviderCapacityForecast(
            version="1.0",
            forecast_id=f"provider-capacity-{uuid4().hex[:10]}",
            provider_name=provider_name,
            available_units=available,
            projected_shortfall=shortfall,
            created_at=now,
        )
        reservation = ReservationForecast(
            version="1.0",
            forecast_id=f"reservation-forecast-{uuid4().hex[:10]}",
            provider_name=provider_name,
            reservation_type="verification",
            reserved_units=0 if capacity is None else capacity.reservation_slots.get("verification", 0),
            projected_needed=max(1, int(round(forecast.reservation_pressure * max(forecast.projected_demand, 1)))),
            created_at=now,
        )
        trend = CapacityTrendRecord(
            version="1.0",
            trend_id=f"capacity-trend-{uuid4().hex[:10]}",
            provider_name=provider_name,
            utilization_ratio=0.0 if available <= 0 else min(1.0, forecast.projected_demand / max(available, 1)),
            demand_delta=float(forecast.projected_demand - forecast.observed_demand),
            created_at=now,
        )
        risk = QuotaExhaustionRisk(
            version="1.0",
            risk_id=f"quota-risk-{uuid4().hex[:10]}",
            provider_name=provider_name,
            risk_level="high" if shortfall > 0 else "medium" if forecast.reservation_pressure >= 0.6 else "low",
            projected_exhaustion_minutes=15 if shortfall > 0 else 60,
            created_at=now,
        )
        self.repository.save_provider_demand_forecast(forecast)
        self.repository.save_provider_capacity_forecast(capacity_forecast)
        self.repository.save_reservation_forecast(reservation)
        self.repository.save_capacity_trend_record(trend)
        self.repository.save_quota_exhaustion_risk(risk)
        if self.shared_state is not None:
            self.shared_state.upsert_record(
                record_type="provider_demand_forecast",
                record_id=forecast.forecast_id,
                scope_key=provider_name,
                payload=forecast.to_dict(),
            )
        return forecast


class ProviderQuotaGovernor:
    """Evaluate provider requests against auditable quota policies."""

    def __init__(self, *, repository: Any, shared_state: Any | None = None, now_factory: Callable[[], datetime] = utc_now) -> None:
        self.repository = repository
        self.shared_state = shared_state
        self.now_factory = now_factory

    def set_quota_policy(
        self,
        *,
        provider_name: str,
        per_role_quota: dict[str, int],
        protected_reservations: dict[str, int],
        low_priority_cap: int,
    ) -> ProviderQuotaPolicy:
        policy = ProviderQuotaPolicy(
            version="1.0",
            policy_id=f"provider-quota-{provider_name}",
            provider_name=provider_name,
            per_role_quota=per_role_quota,
            protected_reservations=protected_reservations,
            low_priority_cap=low_priority_cap,
            created_at=self.now_factory(),
        )
        self.repository.save_provider_quota_policy(policy)
        if self.shared_state is not None:
            self.shared_state.upsert_record(
                record_type="provider_quota_policy",
                record_id=policy.policy_id,
                scope_key=provider_name,
                payload=policy.to_dict(),
            )
        return policy

    def evaluate_request(
        self,
        *,
        provider_name: str,
        task_id: str,
        role: str,
        workload: str,
        priority_class: str,
        requested_units: int,
    ) -> QuotaGovernanceDecision:
        now = self.now_factory()
        policy = self.repository.load_provider_quota_policy(provider_name)
        active_reservations = [item for item in self.repository.list_provider_reservations(provider_name) if item.status == "active"]
        forecasts = self.repository.list_provider_demand_forecasts(provider_name)
        projected_demand = forecasts[0].projected_demand if forecasts else len(active_reservations)
        role_quota = 999 if policy is None else policy.per_role_quota.get(role, max(policy.per_role_quota.values(), default=999))
        protected = 0 if policy is None else policy.protected_reservations.get("verification" if workload == "verification" else workload, 0)
        used_for_role = len([item for item in active_reservations if item.reservation_type == workload or item.worker_id == role])
        low_priority_block = priority_class in {"background", "standard"} and policy is not None and requested_units > policy.low_priority_cap
        reservation_protection = workload in {"verification", "recovery"} and protected > 0
        allowed = reservation_protection or (not low_priority_block and (used_for_role + requested_units) <= max(role_quota, requested_units) and projected_demand <= max(role_quota + protected, requested_units))
        decision = QuotaGovernanceDecision(
            version="1.0",
            decision_id=f"quota-decision-{uuid4().hex[:10]}",
            provider_name=provider_name,
            task_id=task_id,
            role=role,
            workload=workload,
            priority_class=priority_class,
            requested_units=requested_units,
            allowed=allowed,
            reason="protected reservation" if reservation_protection else "quota available" if allowed else "quota pressure or low-priority cap exceeded",
            applied_reservation_protection=reservation_protection,
            created_at=now,
        )
        self.repository.save_quota_governance_decision(decision)
        if self.shared_state is not None:
            self.shared_state.upsert_record(
                record_type="quota_decision",
                record_id=decision.decision_id,
                scope_key=provider_name,
                payload=decision.to_dict(),
            )
        return decision
