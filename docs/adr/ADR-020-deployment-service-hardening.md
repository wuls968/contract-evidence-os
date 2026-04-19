# ADR-020: Deployment-Grade Service Hardening

## Decision

Keep the system as one deployable package, but make service roles explicit in config and docs: control plane, dispatcher, worker, and maintenance. Add startup validation, liveness/readiness, drain mode, restart recovery, idempotent control actions, and server launch assets.

## Rationale

The runtime needs real operational behavior without being split into premature microservices. A single package with explicit roles and lifecycle controls is enough for current scale while preserving audit clarity.

## Alternatives Rejected

- Immediate split into multiple services.
- Treating the runtime as a library only with no operational entrypoints.

## Tradeoffs

- Single-package deployment keeps complexity low, but horizontal scaling remains limited.
- Some role separation is still conceptual and config-driven rather than process-isolated.

## Consequences

- Operators can safely drain, restart, and validate the runtime.
- Deployment guidance is concrete without hiding service behavior behind opaque infrastructure.
