# ADR-005: Crash-Resumable and Idempotent Runtime

## Decision

Runtime execution is now checkpointed into SQLite after stable transitions, and resume logic
reconstructs state from persisted contracts, plan nodes, evidence, receipts, and the latest
checkpoint instead of trusting in-memory state.

## Rationale

Durability must survive process interruption. Persisted node status plus execution receipts
provides a simple idempotence boundary: if a node already produced a successful durable
receipt, resume can skip rerunning it.

## Alternatives Rejected

- Re-execute the whole plan on resume: wastes budget and breaks idempotence
- Serialize the whole runtime object graph: brittle and hard to evolve
- Resume from audit only with no checkpoints: too lossy for stable recovery

## Tradeoffs

Checkpoint payloads are intentionally coarse-grained. This is enough for the current
vertical slice while leaving room for more granular resumability later.
