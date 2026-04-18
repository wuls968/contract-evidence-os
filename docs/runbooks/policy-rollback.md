# Runbook: Policy Rollback

Use rollback when a promoted policy harms queue stability, provider survival, or verification quality.

1. Inspect `GET /policies` and identify the affected scope and active version.
2. Review the latest promotion run and evidence bundle.
3. Call `POST /policies/rollback` with the scope id and rollback reason.
4. Confirm a rollback record was persisted.
5. Re-run the affected benchmark or operational comparison before any new promotion attempt.
