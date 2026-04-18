# ADR-075: Background Maintenance Runtime Surfaces

## Status

Accepted

## Context

Operator-grade maintenance requires more than internal bookkeeping. Schedules, recoveries, incidents, drift, and degraded mode all need first-class surfaces.

## Decision

We expose:

- maintenance schedules and due-run execution
- interrupted maintenance recovery and resume
- maintenance canary and promotion views
- maintenance drift, incidents, and mode endpoints
- analytics and policy state through runtime, operator API, and remote operator service

## Consequences

- remote operators can inspect maintenance health without reading storage directly
- maintenance behavior stays aligned with the rest of the contract/evidence/audit runtime
