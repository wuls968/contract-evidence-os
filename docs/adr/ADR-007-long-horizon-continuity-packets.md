# ADR-007: Long-Horizon Continuity Packets

## Decision

Introduce persisted `HandoffPacket`, `OpenQuestion`, `NextAction`, `ContextCompaction`, `PromptBudgetAllocation`, `WorkspaceSnapshot`, and `ContinuityWorkingSet` records and generate them at durable task boundaries.

## Rationale

The runtime must survive multi-session execution without replaying raw transcript history into each new execution window. Typed continuity objects preserve contract, plan, evidence, and operator state in a way that remains queryable and compact.

## Alternatives Rejected

- Raw transcript replay: too noisy and not operationally stable.
- Single free-form summary blob: easier to write but too hard to query, validate, or role-shape.

## Tradeoffs

- More persistence records per task.
- Additional runtime bookkeeping at checkpoints.

## Consequences

Resume paths now reconstruct a role-shaped working set from durable continuity artifacts instead of reading the whole task trail.

