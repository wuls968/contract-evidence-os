# ADR-008: Operator CLI and Approval Inbox

## Decision

Expose operator controls through a lightweight Python API and `ceos` CLI instead of introducing a new service framework.

## Rationale

Milestone 3 needs usable operator surfaces, but the system identity is still contract-first and audit-native rather than UI-first. A CLI and operator API preserve that identity while remaining testable and deployable.

## Alternatives Rejected

- FastAPI-first control plane: workable, but heavier than needed for the current runtime.
- Direct SQLite inspection by operators: too error-prone and not sufficiently governed.

## Tradeoffs

- The operator API is in-process rather than remote-first.
- HTTP exposure can be added later on top of the same methods.

## Consequences

Approval queues, handoff inspection, replay, and intervention flows are now available through stable entrypoints without changing the runtime core.

