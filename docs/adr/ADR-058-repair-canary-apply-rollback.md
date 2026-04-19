# ADR-058: Repair Canary Apply Rollback

## Status

Accepted

## Context

Cross-scope contradiction repair previously stopped at recommendation time. Operators could see a repair suggestion but not safely canary, apply, or rollback it.

## Decision

Add:

- `MemoryRepairCanaryRun`
- `MemoryRepairActionRun`
- `run_contradiction_repair_canary(...)`
- `apply_contradiction_repair(...)`
- `rollback_contradiction_repair(...)`

Apply promotes the most recent conflicting fact to active state and supersedes older conflicting facts. Rollback restores prior fact statuses from the persisted apply record.

## Consequences

- contradiction repair becomes operational instead of advisory-only
- rollback remains source-grounded and replayable
- project-state reconstruction can reflect repair outcomes without silently rewriting history
