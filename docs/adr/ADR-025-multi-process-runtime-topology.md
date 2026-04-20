# ADR-025: Multi-Process Runtime Topology

## Decision

Keep one package, but make runtime roles explicit: control plane, dispatcher, worker, and maintenance.

## Why

The system needs realistic multi-process operation without premature microservice sprawl.

## Consequences

- Local stacks can run multiple workers against the same SQLite-backed runtime.
- Role-specific startup paths and runbooks now exist.
- Scaling stays understandable and operator-visible.
