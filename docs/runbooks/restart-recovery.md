# Runbook: Restart Recovery

1. Put the system in drain mode.
2. Trigger graceful shutdown through `POST /service/shutdown`.
3. Restart the process.
4. Call `GET /service/startup-validation` and confirm migrations and provider policies are present.
5. Call `POST /service/restart-recovery`.
6. Inspect queue status for recovered leases and deferred items.
7. Resume normal dispatch only after readiness is restored.
