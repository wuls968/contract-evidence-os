# ADR-014: Scorecard-Driven Routing

## Status
Accepted

## Context
Previous milestones stored scorecards but did not fully use them as runtime routing inputs. Milestone 5 requires live provider and tool selection to be guided by persisted operational evidence.

## Decision
We made routing policy explicit and explainable through:
- `RoutingPolicy`,
- `ProviderSelectionPolicy`,
- persisted provider scorecards,
- persisted tool scorecards,
- persisted routing decision records.

Runtime selection now considers:
- reliability,
- latency,
- cost characteristics,
- verification usefulness,
- continuity usefulness,
- execution mode,
- degraded-mode constraints.

## Rationale
- Routing must be auditable, not hidden in prompt text or ad hoc heuristics.
- Persisted scorecards let the runtime learn from actual operational outcomes.
- Explainable routing decisions support operator trust and evaluation.

## Alternatives Rejected
- Static provider mapping by role only.
- Cost-only routing for economy mode.
- Unstructured narrative explanations instead of typed routing receipts.

## Tradeoffs
- Routing is slightly more stateful because recent behavior matters.
- Scorecards can lag reality, so degraded-mode overrides remain necessary.

## Future Implications
- Evolution candidates can safely target routing policies because the inputs and outputs are now explicit and benchmarkable.
