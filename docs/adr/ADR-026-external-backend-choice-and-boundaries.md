# ADR-026: External Backend Choice and Boundaries

## Decision

Adopt Redis as the first real external backend for Milestone 8 queueing and coordination, while keeping SQLite as the reference local backend and durable replay store.

## Rationale

- Cross-host queue dispatch and lease renewal need shared low-latency state.
- Redis fits the current typed backend seams without forcing a broader platform rewrite.
- SQLite remains the source of durable audit, evidence, contract, and recovery history.

## Boundaries

- Externalized in Milestone 8:
  - queue visibility and ready-item ordering,
  - live lease state,
  - worker/host heartbeats,
  - cross-host lease fencing support,
  - provider-pool shared pressure hints.
- Still SQLite-first:
  - contracts,
  - plans and plan revisions,
  - evidence,
  - audit events,
  - checkpoints,
  - governed policy and evolution history.

## Tradeoffs

- Redis improves coordination realism but adds another operational dependency.
- Replay remains clear because Redis is not treated as the only source of truth for historical lineage.
- This is intentionally not a generic pluggable scheduler stack; it is a narrow externalization around the existing agent OS semantics.

