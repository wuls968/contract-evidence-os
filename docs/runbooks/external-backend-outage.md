# External Backend Outage

## Trigger

Redis-backed queue or coordination health turns unavailable or unstable.

## Immediate actions

1. Confirm backend health from the operator surface and inspect backend descriptors and health records.
2. Put the runtime into a degraded or drain-compatible mode if lease safety is uncertain.
3. Pause non-critical queue intake and preserve recovery and verification reservations.
4. Avoid manual lease reassignment until backend connectivity and fencing state are understood.

## Recovery

1. Restore backend connectivity.
2. Re-run backend health checks.
3. Reclaim stale leases only after heartbeat and fencing state are coherent again.
4. Resume queued work from checkpoints and handoff packets.

## Audit expectations

- backend outage/degradation records,
- governance mode changes,
- lease reclaim or defer decisions,
- operator overrides used during the incident.

