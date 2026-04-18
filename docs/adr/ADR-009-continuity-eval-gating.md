# ADR-009: Continuity Eval Gating

## Decision

Require continuity-related evolution candidates to pass long-horizon evaluation metrics before promotion.

## Rationale

Continuity changes can look attractive in short traces while silently dropping constraints, contradictions, or approvals across sessions. Long-horizon evaluation is therefore a promotion gate, not a nice-to-have.

## Alternatives Rejected

- Promote continuity heuristics based on offline single-run metrics only.
- Let continuity candidates canary without dedicated long-horizon scoring.

## Tradeoffs

- Slower promotion for continuity features.
- More evaluation infrastructure to maintain.

## Consequences

`continuity.*` candidates now require resumed completion, handoff quality, continuity reconstruction, and open-question carry-forward quality before passing evaluation.

