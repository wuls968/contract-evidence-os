# ADR-011 Multi-Node Execution And Replanning

## Status
Accepted

## Decision
The runtime now executes a persisted `PlanGraph` through a small scheduler with explicit node categories, ready-queue selection, plan revisions, and recovery branches.

## Rationale
- The original vertical slice proved the contract/evidence/audit model but remained too shallow for operational work.
- Milestone 4 needed deeper execution without losing replayability or branch lineage.
- Recovery had to preserve the failed path in history instead of mutating the plan in place and hiding the failure.

## Consequences
- Plans are persisted as the current active graph, while revisions and branches are stored as first-class history.
- Recovery creates a new active branch and a `PlanRevision` record rather than silently retrying.
- Scheduler state is durable, branch-aware, and continuity-friendly.

## Alternatives Rejected
- Free-form retry loops inside node handlers.
- Parallel worker orchestration without plan revision records.
- Replacing the graph with a generic workflow engine.
