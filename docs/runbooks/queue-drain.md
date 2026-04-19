# Runbook: Queue Drain

Use drain mode before planned restart or migration work.

1. Call `POST /system/governance` with `action=set_drain_mode`.
2. Confirm `GET /system/governance` shows `global_execution_mode=drain`.
3. Dispatch no new work except explicit recovery or operator-approved actions.
4. Call `POST /service/shutdown` to recover stale leases and checkpoint queue state.
5. Restart the service.
6. Call `POST /service/restart-recovery`.
7. Confirm `GET /health/ready` returns ready status again.
