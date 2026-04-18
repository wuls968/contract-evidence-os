# Stale Worker Recovery Across Hosts

## Trigger

A worker heartbeat expires while another host still has capacity to continue the task.

## Procedure

1. Confirm the worker is stale rather than only slow.
2. Review active leases, last renewal attempts, and the current fencing token.
3. Reclaim the lease through the coordination backend.
4. Requeue or transfer the work only through the typed reclaim/steal path.
5. Resume from the latest checkpoint and handoff packet on a healthy host.

## Safety checks

- no competing valid fence remains,
- active approvals and budget state were carried forward,
- branch and evidence lineage remain intact,
- the old worker is quarantined or draining before it can act again.

