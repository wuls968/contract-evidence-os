# ADR-018: Provider Health And Rate-Limit Orchestration

## Decision

Add a provider health subsystem with persisted health records, rate-limit state, cooldown windows, degradation events, and availability policies. Runtime routing now consults provider health before selecting or dispatching a live provider call.

## Rationale

Multi-provider support at system scale needs more than adapter-level retries. The runtime must understand saturation, repeated failures, cooldown, and operator disablement in a way that remains auditable and visible to operators.

## Alternatives Rejected

- Pure request-local retries without persistent health state.
- Provider-specific hidden cooldown logic outside the runtime.

## Tradeoffs

- Health state is intentionally approximate and window-based rather than fully predictive.
- Circuit-breaker behavior is conservative to protect verification-critical execution.

## Consequences

- Routing can degrade gracefully under provider pressure.
- Operators can inspect rate-limit and cooldown state directly.
