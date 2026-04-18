# Durable Backend Outage

## Trigger

The PostgreSQL shared-state backend is degraded or unavailable.

## Immediate response

1. Confirm Redis and SQLite health separately from PostgreSQL health.
2. Move the runtime into degraded mode if shared-state writes are no longer trustworthy.
3. Pause non-critical policy promotion and low-value background work.
4. Preserve verification and recovery reservations.

## Recovery

1. Restore PostgreSQL connectivity.
2. Run reconciliation.
3. Review backlog, outage, and conflict records before resuming full admission.

