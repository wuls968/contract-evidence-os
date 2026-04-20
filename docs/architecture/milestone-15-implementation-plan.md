# Milestone 15 Implementation Plan

**Goal:** Deepen AMOS into a stronger memory-governance runtime with broader purge semantics, feature-scored write admission, contradiction-aware project-state reconstruction, and persistent policy analytics.

**Scope**

- Extend purge behavior from core memory rows into derived artifact and index layers.
- Turn trace-informed admission into a feature-scored controller that emits auditable per-candidate receipts.
- Reconstruct contradiction-aware timelines and operator-visible project-state snapshots.
- Persist policy analytics so canary and rollback outcomes stay visible after later cleanup.

**Key Changes**

- Added typed purge manifests and admission feature-score records.
- Added project-state snapshots derived from contradiction-aware timelines.
- Added memory-policy analytics records tied to canary, promotion, and rollback outcomes.
- Extended operator and remote control-plane surfaces for project-state and purge manifest visibility.
- Expanded governance benchmarks to cover hard-purge artifact depth, feature scoring, contradiction merge quality, and analytics visibility.

**Verification Target**

- New Milestone 15 unit, integration, and evaluation tests pass.
- Full suite remains green.
