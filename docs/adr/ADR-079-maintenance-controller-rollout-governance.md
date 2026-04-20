# ADR-079: Maintenance Controller Rollout Governance

## Status

Accepted

## Context

Milestone 21 could produce maintenance promotion recommendations, but it did not yet have an operator-visible apply/rollback path that changed the active controller version.

## Decision

We add:

- `MemoryMaintenanceControllerState`
- `MemoryMaintenanceRolloutRecord`
- apply and rollback flows for maintenance controller promotions

`recommend_memory_maintenance(...)` now uses the active controller state to decide whether the learned controller is actually live.

## Consequences

- promotion recommendations now have real runtime effect
- rollback is explicit and auditable
- learned maintenance policy stays governed instead of auto-promoted
