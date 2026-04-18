# ADR-067 Background Memory Maintenance Orchestration

## Status

Accepted

## Context

AMOS already had schedulable operations loops and interruption recovery, but it still behaved like a set of callable maintenance tools rather than an auditable background fabric.

## Decision

We add explicit `MemoryMaintenanceRecommendation` and `MemoryMaintenanceRun` records. Background maintenance now:

- reads diagnostics
- turns them into explicit recommended actions
- resumes interrupted loops
- repairs shared artifacts when needed
- evaluates repair backlog and applies safe repairs

## Consequences

- maintenance becomes operator-visible and replayable
- diagnostics are no longer dead-end observations
- the system still avoids becoming a generic workflow engine because actions stay narrow and AMOS-specific

