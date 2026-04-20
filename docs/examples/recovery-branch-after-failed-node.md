# Recovery Branch After Failed Node

Scenario:
- A research or verification node fails.
- The recovery engine classifies the incident as recoverable.
- The planner inserts a recovery node and activates a new branch.
- Downstream nodes are rebased onto the recovery branch.

Expected artifacts:
- `PlanRevision`
- `ExecutionBranch`
- replay output including both revision and selected branch
- continuity state that references the active branch only
