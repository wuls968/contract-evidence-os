# Runbook: Split-Brain Prevention and Lease Conflict Response

1. Inspect lease ownership history for the affected lease.
2. Confirm the newest fencing token and epoch.
3. Reject any completion or acknowledgement from older owners.
4. Requeue or continue the task only from the current owner.
5. Preserve all ownership records for replay and incident review.
