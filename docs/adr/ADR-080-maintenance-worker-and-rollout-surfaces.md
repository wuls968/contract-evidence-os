# ADR-080: Maintenance Worker And Rollout Surfaces

## Status

Accepted

## Context

The runtime, operator API, remote service, and maintenance CLI all need a consistent way to expose maintenance workers, rollouts, and incident resolution.

## Decision

We extend the control plane with:

- maintenance worker registration and cycle execution
- maintenance worker listing
- incident resolution endpoints
- rollout listing, apply, and rollback endpoints
- maintenance CLI support for worker-mode background runs

## Consequences

- operator workflows can use the same shapes locally and remotely
- maintenance behavior becomes easier to inspect and recover in production-like setups
