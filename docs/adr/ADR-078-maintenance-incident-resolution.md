# ADR-078: Maintenance Incident Resolution

## Status

Accepted

## Context

Milestone 21 could emit maintenance incidents and degraded mode, but it did not yet provide a clear operator-visible resolution path.

## Decision

We add explicit incident resolution for maintenance incidents. Resolved incidents keep their audit lineage and move out of the active degraded-state calculation.

## Consequences

- degraded mode can clear cleanly after backend recovery
- incident handling becomes lifecycle-aware instead of edge-triggered only
- operator action remains explicit and reviewable
