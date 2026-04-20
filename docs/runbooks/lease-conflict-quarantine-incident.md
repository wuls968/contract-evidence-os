# Lease Conflict and Quarantine Incident

## Trigger

A stale owner, fencing mismatch, or reclaim race is detected.

## Response

1. Confirm the active fencing token.
2. Quarantine the losing owner path.
3. Record the incident and conflict resolution record.
4. Resume only through the active owner or a recovery branch.

