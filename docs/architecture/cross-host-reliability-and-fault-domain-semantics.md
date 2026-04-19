# Cross-Host Reliability and Fault-Domain Semantics

Milestone 9 makes reliability a first-class system concern without changing the system’s contract/evidence identity.

## Fault domains

The runtime now reasons about failures by domain:

- worker process
- host
- shared-state backend
- queue and lease coordination
- provider pool
- network path
- control plane and trust layer

## Reliability principle

The system should prefer explicit degradation, quarantine, or reconciliation over silent continuation whenever ownership, shared-state visibility, or trust boundaries are ambiguous.

## Durable state split

- SQLite: full replay, evidence, contracts, checkpoints, audit lineage
- Redis: fast queue and coordination pressure
- PostgreSQL: optional durable shared-state mirror for cross-host coordination metadata, trust records, quota state, and reconciliation history

## Recovery principle

Recovery should preserve:

- current contract constraints
- evidence lineage
- active approvals
- checkpoint and handoff continuity
- lease ownership history
- operator-visible incident reasoning

