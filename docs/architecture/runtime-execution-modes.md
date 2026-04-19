# Runtime Execution Modes

Milestone 5 formalizes execution modes as persisted governance state rather than transient prompt framing.

## Modes
- `standard`: balanced execution with normal routing and bounded concurrency.
- `high_risk`: stronger verification bias and effectively serialized execution.
- `low_cost`: cheaper routing preference with protected verification and recovery reserves.
- `verification_heavy`: stronger verifier bias and reduced concurrency.
- `degraded`: reserved for provider or tool degradation scenarios with reduced concurrency and fallback-first routing.
- `recovery_priority`: future-facing mode for repeated failure handling.
- `continuity_priority`: future-facing mode for fragile long-horizon task continuation.

## Dominant Inputs
- contract risk level,
- remaining task budget,
- provider degradation signals,
- repeated tool failures,
- operator overrides,
- pending approval pressure.

## Persisted Surfaces
- `execution_modes`
- `governance_events`
- `routing_policies`
- `budget_events`
- `concurrency_states`

## Operational Effect
Modes influence:
- provider selection,
- tool selection,
- fallback tolerance,
- concurrency limits,
- operator-visible governance summaries.

## Design Constraint
Execution modes do not replace contracts or policies. They are runtime governance overlays constrained by the contract, permission lattice, audit ledger, and recovery engine.
