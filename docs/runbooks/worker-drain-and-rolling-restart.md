# Runbook: Worker Drain and Rolling Restart

1. Put the target worker into drain mode.
2. Wait for active leases to complete or reclaim them if the worker is stale.
3. Restart the worker process.
4. Register and heartbeat the worker again.
5. Re-enable normal dispatch once the worker is healthy.
