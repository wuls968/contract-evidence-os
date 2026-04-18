# ADR-056: Cross-Scope Contradiction Repair

## Status

Accepted

## Context

AMOS could reconstruct cross-scope timelines, but it did not yet emit a dedicated repair recommendation when active semantic state across scopes disagreed.

## Decision

AMOS now persists `MemoryContradictionRepairRecord` entries when cross-scope active state conflicts are detected for the same subject/predicate pair. The current policy recommends the most recent active state while preserving prior conflicting facts as evidence.

## Consequences

- Operators can inspect contradiction repair recommendations directly.
- Cross-scope memory reasoning now has an explicit repair artifact instead of being only implicit in timelines.
- The repair remains advisory and source-grounded.
