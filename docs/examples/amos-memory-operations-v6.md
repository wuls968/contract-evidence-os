# AMOS Memory Operations V6

Milestone 19 extends AMOS with background maintenance and shared artifact repair.

## Example Flow

1. A task scope builds local and shared memory indexes.
2. One shared index file disappears.
3. `artifact_backend_health(scope_key=...)` records the missing shared artifact.
4. `recommend_memory_maintenance(scope_key=...)` emits `repair_shared_artifacts`.
5. `run_background_memory_maintenance(...)` repairs the shared mirror and persists a maintenance run.

## Repair Learning Example

1. Cross-scope contradiction repair canary runs once with controller version `v1`.
2. Repair assessments and rollout analytics are mined into `MemoryRepairLearningState`.
3. The next canary runs with controller version `v2` and reports a learned risk penalty.

## Operator Surface

The remote operator service now exposes:

- artifact backend health
- maintenance recommendations
- background maintenance execution

This keeps maintenance behavior visible without bypassing the existing AMOS evidence and audit layers.
