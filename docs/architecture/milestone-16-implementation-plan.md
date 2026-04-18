# Milestone 16 Implementation Plan

**Goal:** Deepen AMOS into an operator-grade memory operations layer with external artifact/index cleanup, consolidation 2.0 synthesis, admission-controller canaries, and cross-scope contradiction repair.

**Scope**

- Extend AMOS memory operations from in-database state into registered filesystem artifacts and generated memory indexes.
- Upgrade sleep-time consolidation to synthesize project-state snapshots and contradiction counts.
- Add a canary path for the learned admission controller.
- Add cross-scope contradiction repair records and operator-visible repair surfaces.

**Key Changes**

- Added `MemoryArtifactRecord`, `MemoryAdmissionCanaryRun`, and `MemoryContradictionRepairRecord`.
- Rebuild now materializes JSON memory indexes as governed artifacts.
- Hard purge can now physically remove registered artifact files.
- Consolidation now synthesizes project-state snapshots and tracks contradiction merge counts.
- Operator and remote service now expose artifact inventory, admission canary results, and cross-scope repair recommendations.

**Verification Target**

- Milestone 16 unit, integration, and evaluation tests pass.
- Full regression remains green.
