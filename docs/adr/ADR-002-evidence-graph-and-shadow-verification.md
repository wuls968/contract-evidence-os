# ADR-002: Evidence Graph and Shadow Verification

## Decision

All material claims and delivery packets must be grounded in an evidence graph and checked
by a shadow verification lane.

## Rationale

Verification must be a co-equal lane, not a post-hoc note. The evidence graph enables
contradiction handling, citation, and replay.

## Alternatives Rejected

- Single-lane execution with confidence scoring only
- Logging claims without graph structure

## Tradeoffs

This increases bookkeeping cost but creates explainable, reviewable execution trails.
