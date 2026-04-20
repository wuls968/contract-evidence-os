# Plan Revision And Branch Semantics

Milestone 4 treats replanning as a graph revision, not as an in-place retry.

## Core Rules

- The repository stores one active `PlanGraph` per task.
- Each recovery rewrite emits a `PlanRevision`.
- Each recovery path is represented by an `ExecutionBranch`.
- The scheduler executes only nodes on the active branch.
- Rejected branches remain queryable through audit, replay, and branch history.

## Recovery Flow

1. A node fails with a recoverable execution incident.
2. The planner rewrites the failed node into a recovery node on a new branch.
3. Downstream nodes are rebased onto that branch.
4. The runtime persists:
   - revised plan
   - plan revision record
   - execution branch record
   - scheduler state transition
5. Continuity and replay surfaces keep both the failed path and the selected recovery path visible.

## Why This Matters

This keeps the system contract-first and audit-native. We can explain not only what happened, but which branch was attempted, which branch won, and why delivery was allowed to continue.
