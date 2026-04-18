# ADR-035: Outage Reconciliation Engine

## Decision

Model outage repair as an explicit reconciliation run with backlog records and typed outage objects, instead of treating restart recovery as a one-off queue cleanup action.

## Why

Hybrid backends and cross-host leases create cases where some records are visible and others are delayed or missing. Recovery needs a durable repair trail.

## Consequences

- Backend outages can be tracked separately from provider or host incidents.
- Operators can see what is waiting for reconciliation.
- Policy evolution can learn from successful and unsuccessful repair runs.

