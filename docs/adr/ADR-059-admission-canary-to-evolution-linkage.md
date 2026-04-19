# ADR-059: Admission Canary To Evolution Linkage

## Status

Accepted

## Context

AMOS already had admission canaries and memory-policy mining, but they were adjacent systems rather than a closed governed loop.

## Decision

Extend `EvolutionEngine.mine_memory_policy_candidates(...)` so admission-canary runs can participate in candidate mining. The mining run now records `source_canary_run_ids`.

## Consequences

- admission canaries can justify a governed memory-policy candidate
- the linkage is auditable instead of implicit
- promotion still requires the existing eval and canary gates
