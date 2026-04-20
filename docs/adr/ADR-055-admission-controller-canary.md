# ADR-055: Admission Controller Canary

## Status

Accepted

## Context

The learned admission controller v2 could produce feature-scored write decisions, but there was no narrow canary path to compare baseline and upgraded behavior before broader rollout.

## Decision

AMOS now supports `MemoryAdmissionCanaryRun`, which compares:

- baseline threshold-only admission behavior
- feature-scored controller behavior

The canary records quarantine deltas, high-risk override catches, and a rollout recommendation.

## Consequences

- Admission policy rollout now has a memory-local canary step.
- Operators can see whether v2 is catching meaningful risky writes rather than only changing thresholds.
- This remains explicit and auditable instead of silently switching controllers.
