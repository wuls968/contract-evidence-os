# ADR-054: Consolidation V2 And Project-State Synthesis

## Status

Accepted

## Context

Sleep-time consolidation already produced durative records and pointer deduplication, but it did not summarize whether contradiction-heavy state reconstruction was improving operator understanding.

## Decision

Sleep-time consolidation now also:

- synthesizes project-state snapshots
- counts contradiction merges
- persists those counts in `MemoryConsolidationRun`

This keeps project-state synthesis tied to the same source-grounded semantic timeline rather than introducing a separate opaque state layer.

## Consequences

- Operators can treat consolidation as a richer synthesis pass rather than only a deduplication job.
- Project-state snapshots become a first-class output of consolidation.
- Contradiction intensity can now be tracked over time.
