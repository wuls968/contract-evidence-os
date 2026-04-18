# Lease Conflict and Fencing Incident

## Trigger

Two workers appear to act on the same lease or a stale owner attempts renewal after ownership changed.

## Response

1. Inspect ownership conflict events and the latest lease ownership record.
2. Verify the current monotonic fencing token.
3. Reject stale-owner actions and preserve both sides of the incident in audit.
4. If needed, force the losing worker into drain or quarantine mode.
5. Continue only from the current owner or from a fresh recovery branch.

## Post-incident review

- Was heartbeat expiry too aggressive?
- Did host pressure or backend latency distort renewal timing?
- Should the renewal or steal policy candidate be evaluated for adjustment?

