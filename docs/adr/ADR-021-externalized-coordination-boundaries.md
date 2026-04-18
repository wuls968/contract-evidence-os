# ADR-021: Externalized Queue, Storage, and Coordination Boundaries

## Decision

Add typed queue and coordination backends around the existing SQLite repository rather than letting multi-worker logic call SQLite tables directly from all runtime paths.

## Why

Milestone 7 needs stronger process boundaries, lease ownership, and future externalization without rewriting the runtime into a generic workflow engine.

## Consequences

- SQLite remains the reference implementation.
- Queue, coordination, and auth logic are now easier to contract-test and replace incrementally.
