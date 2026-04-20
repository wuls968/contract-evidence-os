# Milestone 6 Implementation Plan

Milestone 6 turns the current runtime into a deployment-grade, system-scale execution core without changing its contract/evidence/audit/recovery identity.

## Goals

- add persistent queueing with leases, admission control, retries, dead-letter handling, and queue-aware resume
- introduce provider health, rate-limit, cooldown, and circuit-breaker orchestration
- add trace-based, eval-gated policy registry and promotion flows for routing, admission, budget, and concurrency policies
- harden service behavior for liveness/readiness, drain mode, restart recovery, and idempotent operator actions
- expose system-scale governance state through operator APIs and reports

## Implementation Order

1. Add failing tests for queue persistence, lease/retry/dead-letter flows, admission control, provider health/rate-limit orchestration, adaptive policy promotion, operator overrides, and system-scale benchmarks.
2. Add typed models and migration `007_system_scale_operations_and_policy_registry`.
3. Implement queueing and admission control with persisted queue items, leases, dispatch records, capacity snapshots, and load-shedding decisions.
4. Implement provider health and rate-limit orchestration, then bind health-aware filtering into runtime routing and dispatch.
5. Add adaptive policy registry, candidate mining from scorecards/traces, eval-gated promotion, and rollback.
6. Harden service roles, drain/restart behavior, readiness checks, and idempotent operator actions.
7. Extend remote operator surfaces for queue, provider health, policy registry, and global governance reports.
8. Add system-scale evals, ADRs, runbooks, and examples, then run the full suite.

## Boundaries

- no generic orchestration framework rewrite
- no UI-heavy expansion
- no bypass of contract compilation, evidence binding, verification, audit, recovery, or governed evolution
- keep queueing, admission, and orchestration typed, replayable, and operator-visible
