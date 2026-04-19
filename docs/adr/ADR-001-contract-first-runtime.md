# ADR-001: Contract-First Runtime

## Decision

Execution begins with a typed `TaskContract` rather than a free-form prompt loop.

## Rationale

Contracts force explicit deliverables, constraints, failure conditions, evidence needs,
budgets, permissions, and evolution boundaries before any tool action occurs.

## Alternatives Rejected

- Prompt-first tool loops: too opaque and weakly governed
- Unstructured plans: insufficient for replay and local replanning

## Tradeoffs

Contract compilation adds upfront structure but dramatically improves traceability.
