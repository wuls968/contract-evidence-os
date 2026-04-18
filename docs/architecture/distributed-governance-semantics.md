# Distributed Governance Semantics

Milestone 7 extends governance across workers, leases, providers, and the control plane.

## Core ideas

- A queue item is not enough; dispatch authority also needs a fenceable owner.
- A provider is not just available or unavailable; it is part of a shared pool under worker demand.
- A remote operator action is not trusted just because it has a token; it needs identity, scope, and replay-safe intent.

## Execution hierarchy

1. Contract and plan still define what is allowed.
2. Queue admission decides whether work may enter execution.
3. Coordination decides which worker currently owns the lease.
4. Provider-pool balancing decides whether shared model capacity is safe to consume.
5. Control-plane auth decides whether an operator is allowed to intervene.

## Replay principle

Distributed behavior must remain reconstructable from persisted records:

- lease ownership history,
- worker heartbeats,
- provider balance decisions,
- auth events and request records,
- operator overrides,
- normal audit and evidence traces.
