# ADR-022: Multi-Worker Lease Ownership and Fencing

## Decision

Introduce explicit `LeaseOwnershipRecord` and `DispatchOwnershipRecord` entities with fencing tokens and epochs. Queue leases still exist, but ownership authority now comes from the coordination layer.

## Why

The runtime must prevent stale workers from completing or acknowledging work after ownership has been re-assigned.

## Consequences

- Lease completion checks now validate the current fence.
- Reclaimed workers can no longer silently finish old leases.
- Replay remains clear because ownership history is persisted instead of overwritten.
