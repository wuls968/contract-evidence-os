# Runbook: Stale Worker Recovery

1. Inspect worker state through the control plane.
2. Confirm the worker heartbeat is stale.
3. Reclaim stale workers and recover queued leases.
4. Verify reclaimed leases return to the queue safely.
5. Resume dispatch on healthy workers only.
