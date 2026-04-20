# ADR-062: Admission Promotion Recommendations

## Status

Accepted

## Context

Admission canaries existed, and memory-policy mining existed, but the bridge between them was still weak.

## Decision

Add `MemoryAdmissionPromotionRecommendation` and let `EvolutionEngine.mine_memory_policy_candidates(...)` consume promotion recommendations in addition to lifecycle traces and canary runs.

## Consequences

- admission canaries can produce an explicit recommendation instead of an implicit hint
- evolution mining keeps its governed shape while gaining a clearer source of evidence
- operator surfaces can inspect promotion readiness directly
