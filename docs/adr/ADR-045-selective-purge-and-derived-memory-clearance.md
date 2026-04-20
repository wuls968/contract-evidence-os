# ADR-045: Selective Purge for Derived Memory Clearance

## Status

Accepted

## Context

By Milestone 13 AMOS could tombstone or hard-purge memory scopes.
What it still lacked was a middle path:

- clear derived retrieval/index artifacts
- retain durable semantic or raw evidence when appropriate
- avoid overusing hard purge for every cleanup request

## Decision

We add selective purge runs that physically remove chosen derived memory kinds such as:

- evidence packs
- dashboard items
- write candidates
- admission decisions
- governance decisions

This creates a governed cleanup path between tombstone-based forgetting and full hard purge.

## Consequences

Positive:

- operators can clean derived state without erasing durable evidence
- risky memory-control artifacts can be removed precisely
- AMOS cleanup becomes more expressive and auditable

Tradeoff:

- selective purge increases record-type mapping complexity
- cache invalidation must still respect repository authority
