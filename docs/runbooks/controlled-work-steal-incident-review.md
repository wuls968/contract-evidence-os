# Controlled Work-Steal Incident Review

## When to use

After a lease was stolen due to stale ownership, drain pressure, or cross-host recovery pressure.

## Review checklist

1. Confirm the steal policy allowed this task class and owner state.
2. Confirm verification- or recovery-reserved work was not violated.
3. Inspect the prior owner heartbeat, drain state, and fencing history.
4. Inspect the work-steal decision, transfer record, and resulting audit events.
5. Confirm no duplicate evidence or duplicate node delivery was produced.

## Follow-up

- If the steal was helpful, feed the trace into policy evaluation.
- If it caused confusion or duplicate effort, capture it as a regression scenario before changing policy.

