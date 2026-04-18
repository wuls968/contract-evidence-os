# ADR-068 Maintenance Recommendation Loop

## Status

Accepted

## Context

Milestone 18 had diagnostics, repair safety, rollout analytics, and scheduled loops, but the pieces were not yet closed into one operator-grade loop.

## Decision

Milestone 19 closes the loop as:

`diagnostics -> maintenance recommendation -> background maintenance run -> repair/apply/resume -> analytics`

The system records both the recommendation layer and the execution layer so operators can inspect why maintenance was proposed and what was actually done.

## Consequences

- better auditability for automatic maintenance behavior
- easier canary/promotion analysis later because recommendation history is retained
- simpler operator debugging when a maintenance run did not take the expected action

