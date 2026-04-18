# ADR-077: Resident Maintenance Workers

## Status

Accepted

## Context

Milestone 21 introduced scheduled background maintenance, but execution still looked like direct helper invocation rather than a resident worker lifecycle.

## Decision

We add `MemoryMaintenanceWorkerRecord` plus worker-facing methods for registration, heartbeat, and schedule-claiming execution. Due maintenance schedules can now be claimed by one worker with a lease window, and interrupted runs keep the claim until resume or expiry.

## Consequences

- maintenance work now has an explicit worker identity
- due schedules become safer under multiple workers
- the system remains understandable because this worker path only covers AMOS maintenance schedules
