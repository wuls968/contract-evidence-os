# ADR-012 Remote Operator Service

## Status
Accepted

## Decision
Expose a lightweight token-authenticated HTTP service on top of the existing operator API instead of introducing a separate remote control stack.

## Rationale
- The system already had durable operator surfaces in the runtime and CLI.
- Milestone 4 required remote approvals, replay, and resume, not a polished UI.
- A small HTTP layer keeps the control plane explicit, testable, and easy to reason about.

## Consequences
- Remote operations remain bound to the same repository, runtime methods, approvals, and audit trails.
- Auth is intentionally simple: bearer token plus configuration, with limits documented rather than overstated.
- Remote approval actions are persisted as `RemoteApprovalOperation` records.

## Alternatives Rejected
- Building a dedicated web UI first.
- Embedding remote control logic directly into the scheduler.
- Adding fake enterprise auth complexity before the operator surface was proven.
