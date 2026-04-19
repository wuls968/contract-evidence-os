# ADR-057: Selective Rebuild And Partial Repair

## Status

Accepted

## Context

AMOS already supported full rebuild and purge paths, but operational recovery still lacked a smaller repair path when only specific layers were damaged.

## Decision

Add `MemorySelectiveRebuildRun` and `selective_rebuild_scope(...)` so the runtime can rebuild only the affected layers:

- `matrix_pointer`
- `dashboard_item`
- `project_state_snapshot`
- `artifact_file`

## Consequences

- partial damage no longer requires a full rebuild
- operator surfaces can request narrow repair with explicit target kinds
- replay remains clear because repair runs are persisted as first-class records
