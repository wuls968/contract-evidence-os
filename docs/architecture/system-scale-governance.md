# System-Scale Governance

Milestone 6 extends governance from per-task control into system-wide execution reasoning.

## Core loop

1. The queue captures submitted and resumed work as persisted `QueueItem` records.
2. Admission evaluates work against capacity, provider health, approval backlog, budget pressure, continuity fragility, and current global mode.
3. Dispatch creates a lease and hands the task to the existing contract/evidence runtime.
4. Provider health and routing scorecards feed back into future routing and future admissions.
5. Policy candidates are mined from these traces and only promoted through evaluation.

## Global modes

- `normal`
- `provider_pressure`
- `cost_pressure`
- `recovery_pressure`
- `drain`
- `maintenance`

These modes do not replace task-local execution modes. They constrain admission and routing from above.

## Fairness strategy

- Recovery and stale-resume work receives priority bonuses.
- Background eval work is the first class to defer under budget or approval pressure.
- Drain and maintenance modes prefer safe delay over new dispatch.

This is intentional bias, not perfect fairness. The goal is starvation avoidance for meaningful work, not equal treatment of all work classes.

## Replay and audit

Queue decisions, provider degradation, policy promotions, and operator overrides are persisted so system pressure behavior can be replayed instead of guessed from logs.
