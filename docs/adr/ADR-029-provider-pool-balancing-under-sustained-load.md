# ADR-029: Provider-Pool Balancing Under Sustained Load

## Decision

Extend provider balancing from per-request routing into cross-host pool management with fairness, reservation, and sustained-pressure signals.

## Why

Once multiple workers and hosts compete for the same live providers, immediate health checks are no longer enough. The runtime needs to preserve recovery and verification capacity under load.

## Consequences

- Provider reservations can protect verification, recovery, and high-risk work.
- Fairness records make monopolization visible.
- Non-critical work can be deferred with operator-visible reasons.
- Balance decisions remain subordinate to contract risk, approvals, and budget policy.

