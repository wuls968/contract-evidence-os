# ADR-028: Controlled Work Stealing

## Decision

Allow work stealing only through typed coordination policies and only when the prior owner is stale, draining, or explicitly steal-eligible.

## Guardrails

- Steals require a fresh fencing token.
- The prior owner state is recorded.
- Steals preserve queue, lease, branch, and audit lineage.
- Recovery-critical and verification-reserved work is protected from opportunistic steals.

## Why

Milestone 8 needs stronger cross-host recovery under pressure, but not at the cost of turning the runtime into a throughput-first distributed scheduler.

## Result

The runtime gains a conservative escape hatch for stuck work while keeping ownership reasoning understandable in replay and incident review.

