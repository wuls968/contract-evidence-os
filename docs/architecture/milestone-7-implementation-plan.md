# Milestone 7 Implementation Plan

## Goal

Add controlled multi-worker scaling, externalizable coordination boundaries, provider-pool balancing, and scoped control-plane security without breaking the contract/evidence/audit core.

## Execution Order

1. Add failing tests for queue/storage backend contracts, worker fencing, provider-pool balancing, scoped auth, and multi-worker evals.
2. Introduce typed queue-backend, coordination, provider-pool, and auth models plus migration `008_multi_worker_coordination_and_secure_control_plane`.
3. Wire SQLite reference backends through the runtime while preserving the existing repository path.
4. Harden the remote control plane with principal-scoped auth and replay protection.
5. Add explicit worker/dispatcher/maintenance entrypoints and local multi-role deployment assets.
6. Verify with targeted slices first, then the full suite.

## Design Notes

- Queue selection stays in the existing queue manager; lease ownership and fencing move into a coordination layer.
- SQLite remains the reference backend, but the runtime now speaks to clearer queue/coordination/auth/provider-pool seams.
- Provider balancing is intentionally conservative and reservation-aware rather than throughput-maximizing.
