# ADR-066 Repair Learning State And Canary Scoring

## Status

Accepted

## Context

Cross-scope contradiction repair already had a static safety heuristic, but that made repair canaries blind to prior hold and rollback signals.

## Decision

We introduce `MemoryRepairLearningState` as a small, auditable learning layer. It is trained from prior safety assessments and rollout analytics, then applied as a learned risk penalty and threshold adjustment when the next repair canary is scored.

## Consequences

- repair canaries now expose controller version and learned penalty
- safety behavior can become more conservative without hiding the underlying base score
- this remains explicit and inspectable rather than becoming a black-box planner

