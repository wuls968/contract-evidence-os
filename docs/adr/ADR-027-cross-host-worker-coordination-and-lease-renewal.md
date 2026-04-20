# ADR-027: Cross-Host Worker Coordination and Lease Renewal

## Decision

Represent host identity, worker identity, lease renewal attempts, expiry forecasts, and ownership conflicts as typed persisted records, with renewal handled through the coordination backend instead of implicit in-process timers alone.

## Why

Cross-host operation introduces uncertainty from network delay, host pressure, and process restart. Lease safety has to remain reconstructable and fenceable.

## Consequences

- Workers heartbeat with both host and process identity.
- Lease renewal decisions produce durable records instead of silent timestamps only.
- Stale-worker reclamation is explicit and auditable.
- Resume after host loss stays tied to checkpoints and handoff state rather than transcript replay.

