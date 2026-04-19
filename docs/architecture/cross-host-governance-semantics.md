# Cross-Host Governance Semantics

Milestone 8 extends governance from multi-process safety into cross-host coordination without changing the system's contract-first identity.

## Core rule

Contract, evidence, approvals, and audit remain the authority for what may happen. Cross-host coordination only decides which worker currently owns the right to act.

## Distributed pressure model

- Admission decides whether work may become active.
- Queue and coordination decide which host and worker may lease it.
- Provider-pool balancing decides whether shared model capacity is safe to consume.
- Security policy decides whether operators and services may intervene.

## Safety invariants

- A stale owner must not keep acting after fencing is lost.
- Steals and reclaims must preserve plan, evidence, and audit lineage.
- Recovery and verification capacity may preempt low-value background work.
- Sensitive control-plane actions must be scoped, replay-protected, and auditable.

## Replay principle

Cross-host execution must still be explainable from persisted records:

- queue and lease events,
- worker and host heartbeats,
- renewal attempts and conflicts,
- provider balance and reservation decisions,
- auth and control-plane request records,
- audit, checkpoint, handoff, and evidence history.

