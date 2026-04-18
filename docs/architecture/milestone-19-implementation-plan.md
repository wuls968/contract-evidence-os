# Milestone 19 Implementation Plan

Milestone 19 deepens AMOS from a repair-capable memory system into a more continuous, operator-visible memory maintenance fabric.

Primary goals:

- add a shared artifact/index backend path that can be diagnosed and repaired without weakening auditability
- introduce a learned repair-safety state so contradiction-repair canaries are not purely static
- convert diagnostics into explicit maintenance recommendations
- make background maintenance runs auditable through typed recommendation and execution records

Implementation shape:

1. Extend memory models with repair-learning, artifact-backend health/repair, and maintenance recommendation/run records.
2. Persist those records through the existing runtime-state repository path.
3. Extend `MemoryMatrix` with:
   - shared artifact mirroring
   - shared artifact backend repair
   - repair-controller training
   - maintenance recommendation generation
   - background maintenance execution
4. Surface the new controls through runtime, operator, remote service, and evaluation harnesses.
5. Keep the architecture source-grounded: maintenance actions still work through evidence-backed AMOS layers instead of bypassing them.

No schema migration was required for Milestone 19 because the repository already stores these runtime records through the generic runtime-state table family.
