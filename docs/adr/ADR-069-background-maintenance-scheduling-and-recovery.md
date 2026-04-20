# ADR-069 Background Maintenance Scheduling And Recovery

## Status

Accepted

## Decision

Background memory maintenance becomes schedulable and resumable in its own right, rather than only being a direct callable operation.

We add:

- maintenance schedules
- due-run execution
- interrupted maintenance runs
- explicit maintenance recovery records

## Why

AMOS already had operations-loop scheduling, but the broader maintenance fabric still lacked its own periodic orchestration and replay-safe resume path.

