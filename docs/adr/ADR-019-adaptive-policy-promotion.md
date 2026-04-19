# ADR-019: Adaptive Policy Promotion From Real Traces

## Decision

Add a policy registry with explicit versions, candidates, evidence bundles, promotion runs, and rollback records. Runtime policy candidates are mined from real scorecard and routing traces, then gated by evaluation before promotion.

## Rationale

The system already supports governed evolution. Milestone 6 extends that principle from skills and heuristics into operational policy without allowing uncontrolled self-modification.

## Alternatives Rejected

- Ad hoc config edits as “policy tuning”.
- Immediate automatic promotion from runtime metrics without evaluation.

## Tradeoffs

- Candidate generation is still heuristic and conservative.
- Promotion velocity is slower because regression and policy checks are mandatory.

## Consequences

- Routing, admission, and pressure-handling policies can improve from evidence.
- Every promotion and rollback remains explainable and auditable.
