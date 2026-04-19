# Operator API v1

`operator api v1` is the stable public HTTP contract for the repository’s operator-facing surfaces.

Base prefix: `/v1`

## Core routes

### Service and reports

- `GET /v1/service/api-contract`
- `GET /v1/service/startup-validation`
- `GET /v1/reports/system`
- `GET /v1/reports/metrics`
- `GET /v1/reports/metrics/history`
- `GET /v1/reports/maintenance`
- `GET /v1/reports/software-control`
- `GET /metrics`
- `GET /v1/health/live`
- `GET /v1/health/ready`

### Task and memory

- `GET /v1/tasks/{task_id}/status`
- `GET /v1/tasks/{task_id}/memory`
- `GET /v1/tasks/{task_id}/memory/kernel`
- `GET /v1/tasks/{task_id}/memory/timeline`
- `GET /v1/tasks/{task_id}/memory/project-state`
- `GET /v1/tasks/{task_id}/memory/policy`
- `GET /v1/tasks/{task_id}/memory/maintenance-mode`
- `GET /v1/tasks/{task_id}/memory/maintenance-workers`
- `GET /v1/tasks/{task_id}/memory/maintenance-daemon`
- `POST /v1/tasks/{task_id}/memory/maintenance-workers/daemon`

### Software control fabric

- `GET /v1/software/harnesses`
- `GET /v1/software/harnesses/{harness_id}/manifest`
- `GET /v1/software/harnesses/{harness_id}/report`
- `GET /v1/software/failure-clusters`
- `GET /v1/software/recovery-hints`
- `GET /v1/software/action-receipts`
- `POST /v1/software/harnesses/{harness_id}/macros/{macro_id}/invoke`
- `GET /v1/software/bridge`

## Response conventions

- responses are JSON
- all public AMOS views are source-grounded and stable enough for snapshot testing
- historical non-versioned routes may still exist as compatibility aliases, but this document only treats `/v1` as canonical

## CLI parity

The `ceos` CLI mirrors the same public story:

- `system-report`
- `metrics-report`
- `maintenance-report`
- `service-health`
- `api-contract`
- `memory-kernel-state`
- `memory-evidence-pack`
- `memory-timeline`
- `memory-project-state`
- `memory-policy-state`
- `memory-maintenance-mode`
- `memory-maintenance-workers`
- `software-harnesses`
- `software-harness-manifest`
- `software-action-receipts`
- `software-control-report`

`ceos-maintenance` is the resident maintenance daemon entrypoint. It supports `--daemon`, `--once`, `--poll-interval-seconds`, `--heartbeat-seconds`, `--lease-seconds`, and `--max-cycles`.

## Stability notes

- `0.9.0` is the first baseline where README, CLI, docs, tests, and HTTP contract are intentionally aligned around a single operator API v1 story.
- Future expansions should add versioned routes instead of silently mutating existing public shapes.
