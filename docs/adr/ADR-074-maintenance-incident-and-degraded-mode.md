# ADR-074: Maintenance Incident And Degraded Mode

## Status

Accepted

## Context

Milestone 21 needs a practical degraded-mode signal for long-running memory maintenance. Falling back from shared artifacts to local rebuilds is operationally meaningful and should not be silent.

## Decision

We add `MemoryMaintenanceIncidentRecord` and `maintenance_mode(...)`. When shared maintenance cannot use the shared backend and falls back to local artifacts, AMOS records an active maintenance incident and reports the scope as `degraded`.

## Consequences

- background maintenance failures become operator-visible incidents
- degraded mode is scoped and auditable
- fallback remains safe because it preserves local source-grounded artifacts instead of guessing state
