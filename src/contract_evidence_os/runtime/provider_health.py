"""Provider health, cooldown, rate-limit, and circuit-breaker orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from contract_evidence_os.base import SchemaModel, utc_now


@dataclass
class ProviderHealthRecord(SchemaModel):
    """Aggregated provider health record used for routing and operations."""

    version: str
    provider_name: str
    circuit_state: str
    recent_failures: int
    recent_successes: int
    structured_output_reliability: float
    fallback_frequency: float
    average_latency_ms: float
    rate_limit_pressure: float
    availability_state: str
    operator_disabled: bool = False
    last_error_code: str = ""
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderHealthSnapshot(SchemaModel):
    """Snapshot of health across one or more providers."""

    version: str
    snapshot_id: str
    records: list[ProviderHealthRecord]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class RateLimitState(SchemaModel):
    """Current request-window accounting for a provider."""

    version: str
    provider_name: str
    window_started_at: datetime
    request_count: int
    max_requests: int
    window_seconds: int
    limited_until: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderCooldownWindow(SchemaModel):
    """Cooldown window for circuit-breaker and backoff behavior."""

    version: str
    provider_name: str
    state: str
    opened_at: datetime
    cooldown_until: datetime
    reopened_count: int = 0

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderDegradationEvent(SchemaModel):
    """Operator-visible degradation, cooldown, or recovery event."""

    version: str
    event_id: str
    provider_name: str
    event_type: str
    summary: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderAvailabilityPolicy(SchemaModel):
    """Availability policy for failures, cooldown, and rate limits."""

    version: str
    policy_id: str
    provider_name: str
    failure_threshold: int
    cooldown_seconds: int
    rate_limit_window_seconds: int
    max_requests_per_window: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


class ProviderHealthManager:
    """Track provider health and enforce lightweight rate-limit orchestration."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    def try_acquire_capacity(self, provider_name: str, *, now: datetime | None = None) -> bool:
        now = utc_now() if now is None else now
        policy = self.repository.load_provider_availability_policy(provider_name)
        if policy is None:
            return True
        cooldown = self.repository.load_provider_cooldown_window(provider_name)
        if cooldown is not None and cooldown.cooldown_until > now and cooldown.state in {"open", "cooldown"}:
            return False
        state = self.repository.load_rate_limit_state(provider_name)
        if state is None or state.window_started_at + timedelta(seconds=state.window_seconds) <= now:
            state = RateLimitState(
                version="1.0",
                provider_name=provider_name,
                window_started_at=now,
                request_count=0,
                max_requests=policy.max_requests_per_window,
                window_seconds=policy.rate_limit_window_seconds,
            )
        if state.limited_until is not None and state.limited_until > now:
            return False
        if state.request_count >= state.max_requests:
            state.limited_until = now + timedelta(seconds=policy.cooldown_seconds)
            self.repository.save_rate_limit_state(state)
            self.repository.save_provider_degradation_event(
                ProviderDegradationEvent(
                    version="1.0",
                    event_id=f"provider-degradation-{uuid4().hex[:10]}",
                    provider_name=provider_name,
                    event_type="rate_limit",
                    summary=f"{provider_name} exceeded its request window.",
                    created_at=now,
                )
            )
            return False
        state.request_count += 1
        self.repository.save_rate_limit_state(state)
        return True

    def record_failure(
        self,
        provider_name: str,
        *,
        error_code: str,
        latency_ms: float,
        at: datetime | None = None,
    ) -> ProviderHealthRecord:
        at = utc_now() if at is None else at
        policy = self.repository.load_provider_availability_policy(provider_name) or ProviderAvailabilityPolicy(
            version="1.0",
            policy_id=f"provider-policy-{provider_name}",
            provider_name=provider_name,
            failure_threshold=3,
            cooldown_seconds=30,
            rate_limit_window_seconds=60,
            max_requests_per_window=60,
        )
        record = self.repository.load_provider_health_record(provider_name) or ProviderHealthRecord(
            version="1.0",
            provider_name=provider_name,
            circuit_state="closed",
            recent_failures=0,
            recent_successes=0,
            structured_output_reliability=1.0,
            fallback_frequency=0.0,
            average_latency_ms=0.0,
            rate_limit_pressure=0.0,
            availability_state="available",
        )
        record.recent_failures += 1
        record.average_latency_ms = self._average(record.average_latency_ms, latency_ms, record.recent_failures + record.recent_successes)
        record.last_error_code = error_code
        record.rate_limit_pressure = min(record.rate_limit_pressure + (0.5 if error_code == "rate_limited" else 0.2), 1.0)
        if record.recent_failures >= policy.failure_threshold:
            record.circuit_state = "open"
            record.availability_state = "degraded"
            cooldown = ProviderCooldownWindow(
                version="1.0",
                provider_name=provider_name,
                state="open",
                opened_at=at,
                cooldown_until=at + timedelta(seconds=policy.cooldown_seconds),
                reopened_count=(self.repository.load_provider_cooldown_window(provider_name) or ProviderCooldownWindow(version="1.0", provider_name=provider_name, state="closed", opened_at=at, cooldown_until=at)).reopened_count + 1,
            )
            self.repository.save_provider_cooldown_window(cooldown)
            self.repository.save_provider_degradation_event(
                ProviderDegradationEvent(
                    version="1.0",
                    event_id=f"provider-degradation-{uuid4().hex[:10]}",
                    provider_name=provider_name,
                    event_type="circuit_opened",
                    summary=f"{provider_name} opened its circuit after repeated failures.",
                    created_at=at,
                )
            )
        record.updated_at = at
        self.repository.save_provider_health_record(record)
        return record

    def record_success(
        self,
        provider_name: str,
        *,
        latency_ms: float,
        structured_output_ok: bool,
        at: datetime | None = None,
    ) -> ProviderHealthRecord:
        at = utc_now() if at is None else at
        record = self.repository.load_provider_health_record(provider_name) or ProviderHealthRecord(
            version="1.0",
            provider_name=provider_name,
            circuit_state="closed",
            recent_failures=0,
            recent_successes=0,
            structured_output_reliability=1.0,
            fallback_frequency=0.0,
            average_latency_ms=0.0,
            rate_limit_pressure=0.0,
            availability_state="available",
        )
        total = record.recent_failures + record.recent_successes + 1
        record.recent_successes += 1
        record.structured_output_reliability = self._average(
            record.structured_output_reliability,
            1.0 if structured_output_ok else 0.0,
            total,
        )
        record.average_latency_ms = self._average(record.average_latency_ms, latency_ms, total)
        record.rate_limit_pressure = max(record.rate_limit_pressure - 0.2, 0.0)
        record.circuit_state = "closed"
        record.availability_state = "available"
        record.updated_at = at
        self.repository.save_provider_health_record(record)
        cooldown = self.repository.load_provider_cooldown_window(provider_name)
        if cooldown is not None:
            cooldown.state = "closed"
            cooldown.cooldown_until = at
            self.repository.save_provider_cooldown_window(cooldown)
        self.repository.save_provider_degradation_event(
            ProviderDegradationEvent(
                version="1.0",
                event_id=f"provider-degradation-{uuid4().hex[:10]}",
                provider_name=provider_name,
                event_type="provider_recovered",
                summary=f"{provider_name} recovered and closed its circuit.",
                created_at=at,
            )
        )
        return record

    def force_half_open_probe(self, provider_name: str, *, at: datetime | None = None) -> None:
        at = utc_now() if at is None else at
        cooldown = self.repository.load_provider_cooldown_window(provider_name)
        if cooldown is None:
            cooldown = ProviderCooldownWindow(
                version="1.0",
                provider_name=provider_name,
                state="half_open",
                opened_at=at,
                cooldown_until=at,
            )
        cooldown.state = "half_open"
        cooldown.cooldown_until = at
        self.repository.save_provider_cooldown_window(cooldown)
        record = self.repository.load_provider_health_record(provider_name)
        if record is not None:
            record.circuit_state = "half_open"
            record.availability_state = "degraded"
            record.updated_at = at
            self.repository.save_provider_health_record(record)

    def snapshot(self, provider_names: list[str], *, now: datetime | None = None) -> ProviderHealthSnapshot:
        now = utc_now() if now is None else now
        records: list[ProviderHealthRecord] = []
        for provider_name in provider_names:
            record = self.repository.load_provider_health_record(provider_name)
            if record is None:
                record = ProviderHealthRecord(
                    version="1.0",
                    provider_name=provider_name,
                    circuit_state="closed",
                    recent_failures=0,
                    recent_successes=0,
                    structured_output_reliability=1.0,
                    fallback_frequency=0.0,
                    average_latency_ms=0.0,
                    rate_limit_pressure=0.0,
                    availability_state="available",
                    updated_at=now,
                )
                self.repository.save_provider_health_record(record)
            cooldown = self.repository.load_provider_cooldown_window(provider_name)
            rate_state = self.repository.load_rate_limit_state(provider_name)
            if cooldown is not None and cooldown.state == "open" and cooldown.cooldown_until <= now:
                record.circuit_state = "half_open"
                record.availability_state = "degraded"
            if rate_state is not None and rate_state.limited_until is not None and rate_state.limited_until > now:
                record.availability_state = "rate_limited"
            records.append(record)
        return ProviderHealthSnapshot(
            version="1.0",
            snapshot_id=f"provider-health-snapshot-{uuid4().hex[:10]}",
            records=records,
            created_at=now,
        )

    def _average(self, previous: float, new_value: float, total: int) -> float:
        total = max(total, 1)
        return ((previous * (total - 1)) + new_value) / total
