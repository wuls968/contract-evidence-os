# ADR-064: Memory Repair Fabric Operator Surfaces

## Status

Accepted

## Context

The memory repair fabric is only useful if operators can schedule, inspect, and resume it through the existing control plane.

## Decision

Expose:

- memory operations schedules
- memory operations diagnostics
- interrupted loop resume
- admission promotion recommendations

through the existing operator API and remote operator service.

## Consequences

- no new UI or service split is needed
- the control plane stays aligned with the rest of the runtime governance model
- benchmarks can verify operator-visible recovery behavior directly
