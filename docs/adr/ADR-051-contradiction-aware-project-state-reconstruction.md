# ADR-051: Contradiction-Aware Project-State Reconstruction

## Status

Accepted

## Context

AMOS timelines could reconstruct sequences of semantic facts, but resumed states and contradiction-driven returns were not distinguished from ordinary state changes.

## Decision

Timeline reconstruction now records:

- contradicted supporting facts
- merge reasons
- resumed-prior-state markers

AMOS also persists `MemoryProjectStateSnapshot` records that summarize the active reconstructed state and contradiction count for a scope/subject pair.

## Consequences

- Operators can inspect current project state without losing the contradiction lineage that produced it.
- Timeline reconstruction is now stronger for long-running work that revisits prior goals.
- This stays source-grounded: project-state snapshots derive from timeline segments and semantic facts rather than replacing them.
