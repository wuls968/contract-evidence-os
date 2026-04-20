# Operator API v1 User Manual

This is the practical API guide for people who want to operate Contract-Evidence OS over HTTP.

It is not a replacement for the schema snapshot.

Use this manual when you want:

- the quickest way to authenticate and call the API
- route groups explained in plain English
- example `curl` commands
- guidance on which routes to use first
- a stable mental model for GET inspection versus POST execution

For the concise canonical route list, see [operator-v1.md](operator-v1.md).

## 1. Base URL And Authentication

The stable API prefix is:

- `/v1`

Most local examples assume:

- `http://127.0.0.1:8080`

The API uses bearer-token authentication through `CEOS_OPERATOR_TOKEN`.

Example:

```bash
export CEOS_BASE_URL="http://127.0.0.1:8080"
export CEOS_OPERATOR_TOKEN="your-token"
```

Then:

```bash
curl \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  "$CEOS_BASE_URL/v1/reports/system"
```

## 2. The Most Useful Route Groups

Think of the API as seven practical groups:

1. service and health
2. task and memory inspection
3. collaboration and concurrency
4. strategy and policy evolution
5. software control
6. usage and reports
7. browser-console-adjacent auth and config routes

The fastest way to learn what the server exposes is still:

```bash
curl \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  "$CEOS_BASE_URL/v1/service/api-contract"
```

## 3. Service, Health, And Reports

Start here when bringing up a runtime or debugging a system-level issue.

Most useful routes:

- `GET /v1/service/api-contract`
- `GET /v1/service/startup-validation`
- `GET /v1/reports/system`
- `GET /v1/reports/metrics`
- `GET /v1/reports/metrics/history`
- `GET /v1/reports/maintenance`
- `GET /v1/reports/software-control`
- `GET /v1/health/live`
- `GET /v1/health/ready`

Examples:

```bash
curl -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  "$CEOS_BASE_URL/v1/service/startup-validation"

curl -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  "$CEOS_BASE_URL/v1/reports/metrics"
```

## 4. Task And Memory Inspection

Use task and memory routes when you are diagnosing one specific unit of work.

Common routes:

- `GET /v1/tasks/{task_id}/status`
- `GET /v1/tasks/{task_id}/memory`
- `GET /v1/tasks/{task_id}/memory/kernel`
- `GET /v1/tasks/{task_id}/memory/timeline`
- `GET /v1/tasks/{task_id}/memory/project-state`
- `GET /v1/tasks/{task_id}/memory/policy`
- `GET /v1/tasks/{task_id}/memory/scopes`
- `POST /v1/tasks/{task_id}/memory/scopes`
- `POST /v1/tasks/{task_id}/memory/scopes/promote`
- `POST /v1/tasks/{task_id}/memory/scopes/summary`

Examples:

```bash
curl -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  "$CEOS_BASE_URL/v1/tasks/task-123/memory/kernel"

curl -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  "$CEOS_BASE_URL/v1/tasks/task-123/memory/scopes"
```

Create a scoped memory record:

```bash
curl -X POST \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "actor_user_id": "operator-1",
    "kind": "decision_memory",
    "audience_scope": "task_shared",
    "content": {
      "summary": "Use evidence branch B as the main merge candidate."
    }
  }' \
  "$CEOS_BASE_URL/v1/tasks/task-123/memory/scopes"
```

Generate a handoff summary:

```bash
curl -X POST \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "actor_user_id": "operator-1",
    "summary_kind": "handoff_summary"
  }' \
  "$CEOS_BASE_URL/v1/tasks/task-123/memory/scopes/summary"
```

## 5. Collaboration And Same-Task Concurrency

These routes matter when more than one person is working around the same task.

Common routes:

- `GET /v1/tasks/{task_id}/collaboration`
- `POST /v1/tasks/{task_id}/collaboration`
- `GET /v1/tasks/{task_id}/leases`
- `POST /v1/tasks/{task_id}/leases`
- `GET /v1/tasks/{task_id}/branches`
- `POST /v1/tasks/{task_id}/branches`
- `POST /v1/tasks/{task_id}/handoff`

Inspect collaboration:

```bash
curl -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  "$CEOS_BASE_URL/v1/tasks/task-123/collaboration"
```

Assign owner, reviewer, operators, watchers, and approval assignee:

```bash
curl -X POST \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "owner_user_id": "operator-1",
    "reviewer_user_id": "reviewer-1",
    "operator_user_ids": ["operator-1", "operator-2"],
    "watcher_user_ids": ["viewer-1"],
    "approval_assignee_user_id": "reviewer-1"
  }' \
  "$CEOS_BASE_URL/v1/tasks/task-123/collaboration"
```

Acquire a lease:

```bash
curl -X POST \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "actor_user_id": "operator-1",
    "phase": "verification"
  }' \
  "$CEOS_BASE_URL/v1/tasks/task-123/leases"
```

Create a branch:

```bash
curl -X POST \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "actor_user_id": "operator-2",
    "label": "parallel-evidence-branch",
    "purpose": "Compare alternative evidence path."
  }' \
  "$CEOS_BASE_URL/v1/tasks/task-123/branches"
```

Open a handoff:

```bash
curl -X POST \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "from_user_id": "operator-1",
    "to_user_id": "operator-2",
    "reason": "Shift handoff after evidence collection."
  }' \
  "$CEOS_BASE_URL/v1/tasks/task-123/handoff"
```

## 6. Strategy And Policy Evolution

Use strategy routes when you want governed improvement instead of hidden heuristic drift.

Common routes:

- `GET /v1/strategy/overview?scope_key={task_id}`
- `POST /v1/strategy/feedback`
- `POST /v1/strategy/candidates`
- `POST /v1/strategy/candidates/{candidate_id}/evaluate`
- `POST /v1/strategy/candidates/{candidate_id}/canary`
- `POST /v1/strategy/candidates/{candidate_id}/promote`

Inspect strategy posture:

```bash
curl -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  "$CEOS_BASE_URL/v1/strategy/overview?scope_key=task-123"
```

Record feedback:

```bash
curl -X POST \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scope_key": "task-123",
    "strategy_family": "tool_selection_policy",
    "signal_kind": "review_feedback",
    "value": 0.8,
    "notes": "Evidence yield was strong and replay was stable."
  }' \
  "$CEOS_BASE_URL/v1/strategy/feedback"
```

Create a candidate:

```bash
curl -X POST \
  -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "scope_key": "task-123",
    "strategy_family": "provider_routing_policy",
    "proposed_by_user_id": "operator-1",
    "label": "prefer-balanced-over-economy-under-review"
  }' \
  "$CEOS_BASE_URL/v1/strategy/candidates"
```

Evaluate, canary, and promote only after you have enough evidence and review posture.

## 7. Software Control Fabric

Use these routes when the runtime is operating governed harnesses or software procedures.

Common routes:

- `GET /v1/software/harnesses`
- `GET /v1/software/harnesses/{harness_id}/manifest`
- `GET /v1/software/harnesses/{harness_id}/report`
- `GET /v1/software/action-receipts`
- `GET /v1/software/failure-clusters`
- `GET /v1/software/recovery-hints`
- `POST /v1/software/harnesses/{harness_id}/macros/{macro_id}/invoke`

Examples:

```bash
curl -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  "$CEOS_BASE_URL/v1/software/harnesses"

curl -H "Authorization: Bearer $CEOS_OPERATOR_TOKEN" \
  "$CEOS_BASE_URL/v1/software/action-receipts"
```

## 8. Maintenance And Resident Runtime Surfaces

Use maintenance routes when you need to understand daemon, incidents, worker state, or recommendations.

Common routes:

- `GET /v1/tasks/{task_id}/memory/maintenance-mode`
- `GET /v1/tasks/{task_id}/memory/maintenance-workers`
- `GET /v1/tasks/{task_id}/memory/maintenance-daemon`
- `POST /v1/tasks/{task_id}/memory/maintenance-workers/daemon`
- `GET /v1/reports/maintenance`

## 9. Browser-Console-Adjacent Auth And Config Routes

The browser console uses additional auth, config, usage, and UI routes outside `/v1`.

Common families:

- `/auth/*`
- `/config/*`
- `/usage/*`
- `/ui/*`
- `/events/stream`

If you are integrating as an operator or automation client, prefer `/v1` first.

## 10. How To Think About GET Versus POST

In this runtime, the simplest safe rule is:

- `GET` means inspect trusted state
- `POST` means create or change governed state

Use `GET` for:

- reports
- health
- task status
- memory inspection
- collaboration state
- strategy posture

Use `POST` for:

- collaboration updates
- lease acquisition
- branch creation
- handoff creation
- scoped memory write
- summary generation
- strategy feedback and candidate lifecycle
- maintenance daemon actions

## 11. Error Handling And Calling Conventions

Recommended client habits:

- always send bearer auth explicitly
- keep `task_id` and `scope_key` stable in your own integration layer
- use `GET` inspection before `POST` execution for sensitive flows
- prefer one small, explicit POST over large ambiguous state mutation

When a POST feels risky:

1. inspect the task first
2. inspect collaboration and review posture
3. inspect strategy or memory state if relevant
4. then perform the action

## 12. Suggested First API Session

If you are trying the API for the first time, do this:

1. `GET /v1/service/api-contract`
2. `GET /v1/reports/system`
3. `GET /v1/tasks/{task_id}/status`
4. `GET /v1/tasks/{task_id}/memory/scopes`
5. `GET /v1/tasks/{task_id}/collaboration`
6. `GET /v1/strategy/overview?scope_key={task_id}`
7. one small `POST`, such as creating a branch or generating a handoff summary

## 13. Related Docs

- [Operator API v1 route list](operator-v1.md)
- [Complete User Guide](../manual/user-guide.md)
- [Getting Started](../manual/getting-started.md)
- [Small-Team Best Practices Runbook](../runbooks/small-team-best-practices.md)
