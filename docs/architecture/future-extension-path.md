# Future Extension Path

The repository is no longer in the early “vertical slice” phase. The near-future work should preserve the current public shape:

- a stable runtime OS
- a unified AMOS memory kernel
- a governed software control fabric
- a long-running, auditable maintenance layer

## Current Center

The project now revolves around a single lifecycle instead of disconnected milestone features:

`raw ledger -> candidate extraction -> admission -> semantic/procedural/matrix persistence -> retrieval/evidence pack -> consolidation -> repair -> purge/rebuild -> analytics/evolution`

That lifecycle is the memory kernel and should remain the organizing abstraction for future work.

## Near-Term

- deepen the `memory kernel` public contract instead of introducing more milestone-shaped one-off views
- extend operator API v1 snapshot/testing discipline so CLI, HTTP, docs, and JSON surfaces stay aligned
- harden software control manifests, replay semantics, and failure-pattern reporting for local-first desktop use
- improve observability and metrics around maintenance, incidents, repair backlog, and software control risk distribution

## Mid-Term

- push AMOS consolidation and repair toward stronger contradiction-aware project-state and timeline reconstruction
- deepen software control memory so per-app procedures, failure modes, and recovery hints become easier to reuse safely
- add richer maintenance lease/stale-reclaim semantics while still keeping maintenance separate from the main runtime scheduler
- extend shared artifact and index repair beyond the current local/shared-fs mirror model

## Long-Term

- keep AMOS auditable even if future learned controllers are introduced
- preserve contract/evidence/audit identity while evolving maintenance, rollout, and software control automation
- continue improving runtime/provider/maintenance governance without collapsing into a generic distributed workflow platform

## Non-Goals

- no black-box neural memory as the primary truth source
- no unconstrained GUI automation fabric
- no replacement of the core contract/evidence/audit pipeline with generic task orchestration abstractions
