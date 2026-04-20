# ADR-016: Budget Governance and Execution Modes

## Status
Accepted

## Context
The runtime needed real cost guardrails for long-running tasks. Budget pressure had to influence routing and scheduling without bypassing verification, recovery, or continuity obligations.

## Decision
We introduced typed budget governance:
- `BudgetPolicy`,
- `BudgetLedger`,
- `BudgetEvent`,
- `BudgetConsumptionRecord`,
- persisted execution mode state.

The runtime now:
- initializes per-task budget policy from preferences,
- enforces reserve-aware preflight checks,
- records estimated and actual cost,
- switches execution mode under budget pressure,
- exposes mode and budget state to operators.

## Rationale
- Cost control must be computable and auditable.
- Verification and recovery need protected reserves to avoid false savings.
- Execution modes provide a clean bridge between budget pressure and routing behavior.

## Alternatives Rejected
- Best-effort budget warnings with no enforcement.
- Provider-only cost control without tool or continuity accounting.
- Replanning that ignores budget state.

## Tradeoffs
- Budget estimates remain heuristic for simulator paths.
- Conservative reserves may block some otherwise-successful runs.

## Future Implications
- Budget-aware replanning and policy promotion can now be evaluated against explicit ledgers instead of narrative claims.
