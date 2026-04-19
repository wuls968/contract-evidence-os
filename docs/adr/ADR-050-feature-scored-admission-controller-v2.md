# ADR-050: Feature-Scored Admission Controller V2

## Status

Accepted

## Context

Milestone 14 added trace-informed threshold tuning, but the write controller still mostly acted on coarse poison, privacy, and contradiction scores. That made borderline unsafe procedural memories too opaque.

## Decision

AMOS admission now emits a typed `MemoryAdmissionFeatureScore` for every governed candidate. The controller combines:

- instruction override signals
- hidden tool override signals
- destructive action signals
- privacy signals
- contradiction signals
- single-source weakness

These features are weighted by the current learned admission state and recorded as an auditable receipt.

## Consequences

- Operators can see why a candidate was quarantined, not just that it was.
- Memory-policy evolution can learn from concrete feature distributions instead of only outcome counts.
- The controller remains explicit and auditable rather than becoming an opaque neural gate.
