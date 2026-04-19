# Milestone 5 Implementation Plan

Milestone 5 deepens the runtime into a production-shaped operational engine without changing the core contract/evidence/audit/recovery identity.

## Goals

- add a second real live provider backend through the existing abstraction
- make provider and tool routing genuinely scorecard- and policy-driven at runtime
- introduce bounded concurrency for independent plan nodes with replayable state
- add typed budget governance and cost-aware execution modes
- expose governance state and controls through the remote operator surface

## Implementation Order

1. Add failing tests for second-provider support, adaptive routing, bounded concurrency, budget governance, and governance endpoints.
2. Add typed models and migration `006_operations_governance_and_budgeting`.
3. Implement a second live provider backend plus provider capability and scorecard persistence.
4. Introduce routing policy objects and use them in actual provider and tool selection.
5. Add bounded concurrency control and join/barrier handling in the scheduler while preserving auditability.
6. Implement budget ledgers, budget enforcement, and execution mode switching.
7. Extend operator APIs and remote service for governance state and operator interventions.
8. Add operational benchmark scenarios, ADRs, and examples, then run the full suite.

## Boundaries

- no framework rewrite
- no decorative UI
- no bypass of contract compilation, evidence binding, verification, audit, or governed evolution
- keep concurrency deliberately bounded and persistence-first
