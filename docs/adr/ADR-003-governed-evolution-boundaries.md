# ADR-003: Governed Evolution Boundaries

## Decision

Self-improvement is represented as typed `EvolutionCandidate` artifacts that must pass
offline evaluation, limited canarying, and rollback-safe promotion checks.

## Rationale

Ungoverned self-modification is unsafe and incompatible with audit-native operation.

## Alternatives Rejected

- Direct prompt mutation from runtime traces
- Automatic policy modification without approval

## Tradeoffs

Governed evolution is slower than uncontrolled adaptation but preserves trust.
