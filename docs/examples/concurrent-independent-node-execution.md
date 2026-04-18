# Concurrent Independent Node Execution

When a plan contains multiple independent research nodes:

- both nodes must be ready,
- both must satisfy permissions,
- neither may be approval-gated,
- execution mode must allow parallelism,
- concurrency caps must permit the batch.

The scheduler then executes the batch together, persists concurrency state, and still emits ordinary receipts and checkpoints so recovery and replay remain understandable.
