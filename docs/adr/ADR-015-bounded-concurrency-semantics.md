# ADR-015: Bounded Concurrency Semantics

## Status
Accepted

## Context
The runtime already supported multi-node plans, but concurrency was intentionally shallow. Milestone 5 requires real parallel execution for independent nodes without losing replayability or audit integrity.

## Decision
We introduced bounded concurrency at the scheduler layer:
- only ready nodes are eligible,
- approval-gated or high-risk paths remain serialized,
- concurrency is grouped by compatible role and node category,
- concurrency state is persisted as a first-class record,
- every concurrent batch still produces ordinary receipts, checkpoints, and audit events.

## Rationale
- Independent evidence gathering is the safest place to add concurrency first.
- Batching by compatible node shape keeps replay understandable.
- Persisted concurrency state preserves operator visibility across sessions.

## Alternatives Rejected
- Unbounded worker pools.
- Generic DAG executor semantics that obscure contract and branch context.
- Parallel verification and approval execution by default.

## Tradeoffs
- Concurrency is intentionally conservative.
- Some theoretically parallel nodes still run serially to preserve governance clarity.

## Future Implications
- Additional concurrency should be introduced by node category and replay safety, not by raw throughput goals.
