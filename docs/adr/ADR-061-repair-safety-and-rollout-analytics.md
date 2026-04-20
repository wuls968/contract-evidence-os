# ADR-061: Repair Safety And Rollout Analytics

## Status

Accepted

## Context

AMOS already supported contradiction repair canaries plus apply and rollback, but it lacked a typed safety gate and typed rollout analytics around those actions.

## Decision

Add:

- `MemoryRepairSafetyAssessment`
- `MemoryRepairRolloutAnalyticsRecord`

Repair canaries now persist a safety assessment before recommendation. Apply and rollback both emit rollout analytics records.

## Consequences

- operators can see why a repair was allowed or held
- repair actions become easier to audit and benchmark
- later milestones can learn from repair outcomes without parsing raw traces
