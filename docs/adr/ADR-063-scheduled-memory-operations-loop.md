# ADR-063: Scheduled Memory Operations Loop

## Status

Accepted

## Context

Milestone 17 introduced a joined memory operations loop, but it still behaved like a one-shot primitive instead of an operator-grade fabric.

## Decision

Add:

- `MemoryOperationsLoopSchedule`
- `MemoryOperationsLoopRecoveryRecord`
- `MemoryOperationsDiagnosticRecord`

The loop can now be scheduled, interrupted after a phase, resumed later, and summarized through diagnostics.

## Consequences

- AMOS repair becomes closer to a continuous operational loop
- interruption recovery stays typed and replayable
- diagnostics expose the health of the repair fabric without adding a new service boundary
