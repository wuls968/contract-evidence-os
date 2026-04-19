# Milestone 9 Implementation Plan

## Goal

Harden the runtime for cross-host reliability by adding a stronger durable shared-state path, predictive lease handling, reconciliation after outage, forecast-aware provider quota governance, and a stronger production trust mode.

## Planned Shape

- Keep SQLite as the local reference repository and Redis as fast coordination.
- Add PostgreSQL as an explicit durable shared-state option through the current abstractions.
- Add typed reliability, quota, and trust records that remain replayable and operator-visible.
- Use a hybrid path:
  - Redis for fast leases and queue pressure.
  - PostgreSQL for durable shared runtime metadata when configured.
  - SQLite for full task, evidence, audit, checkpoint, and replay history.

## Implementation Steps

1. Add typed models and repository persistence for reliability, quota, trust, and shared-state descriptors.
2. Add shared-state backend abstractions with SQLite and PostgreSQL implementations.
3. Add predictive lease and reconciliation helpers.
4. Add provider demand forecasting and quota governance.
5. Add HMAC trust mode for service-to-service sensitive actions.
6. Wire the runtime, operator service, config, and deployment assets through those new seams.
7. Add benchmark coverage, runbooks, ADRs, and examples.

