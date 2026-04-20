# ADR-046: Trace-Informed Admission Learning

## Status

Accepted

## Context

AMOS admission in Milestone 13 was still policy-threshold-driven.
That made it safe, but it could not adapt after repeated poisoning-shaped events or repeated successful quarantines.

## Decision

We add a typed admission learning state that:

- reads lifecycle traces for suspicious override and purge patterns
- computes conservative sensitivity boosts
- recommends updated quarantine thresholds
- preserves explicit block thresholds and operator visibility

This is intentionally not a black-box classifier.

## Consequences

Positive:

- AMOS can become stricter after repeated poisoning-shaped traces
- learned behavior remains inspectable and persistent
- admission changes stay compatible with eval-gated policy evolution

Tradeoff:

- learning is still heuristic and local to a scope
- threshold tuning must remain conservative to avoid overblocking
