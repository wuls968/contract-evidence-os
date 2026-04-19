# Rolling Restart Under Shared Durable State

## Goal

Restart hosts or roles while preserving queue, lease, shared-state, and checkpoint integrity.

## Procedure

1. Drain affected host or workers.
2. Avoid new leases on the draining side.
3. Let in-flight work finish or reclaim it safely.
4. Restart the role.
5. Re-register, reconcile, and resume queued work.

