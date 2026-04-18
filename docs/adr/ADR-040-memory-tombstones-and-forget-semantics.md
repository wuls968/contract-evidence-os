# ADR-040: Memory Tombstones and Forget Semantics

## Status

Accepted

## Context

AMOS must support forgetting without losing auditability.
A direct destructive delete across all derived memory artifacts would make replay and governance harder to reason about.

## Decision

The runtime uses memory tombstones as the first operational forgetting layer.

Each tombstone records:

- scope
- target kind
- target id
- actor
- reason
- deletion time

Retrieval, dashboards, and lifecycle rebuilds treat tombstoned memory as unavailable.

## Consequences

Positive:

- operator-visible forgetting
- replay-safe semantics
- explicit deletion lineage

Tradeoff:

- underlying persisted source records may still exist physically until a future hard-purge workflow is added
- lifecycle logic must consistently honor tombstones
