# ADR-017: Persistent Queueing And Admission Control

## Decision

Introduce a SQLite-backed queue and admission layer with persisted `QueueItem`, `QueueLease`, `AdmissionDecision`, `DispatchRecord`, policy records, and capacity snapshots. The runtime dispatches work through queue leases instead of assuming immediate direct execution.

## Rationale

Milestone 6 requires multi-task system behavior without turning the runtime into a generic orchestration framework. A small persisted queue keeps the contract/evidence/audit core intact while adding durable dispatch, retries, dead-letter handling, and operator-visible admission reasoning.

## Alternatives Rejected

- In-memory queue: simpler, but not restart-safe or replayable.
- External broker first: adds operational weight too early and weakens local audit clarity.

## Tradeoffs

- SQLite queueing is intentionally conservative in throughput.
- Admission remains policy-driven and understandable, but not yet optimized for very large fleets.

## Consequences

- Queue state, admission decisions, and dispatch history are now first-class replayable records.
- Resume/recovery flows can route through the same queue path as new work.
