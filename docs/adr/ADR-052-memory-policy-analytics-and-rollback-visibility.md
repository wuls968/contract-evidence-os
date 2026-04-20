# ADR-052: Memory Policy Analytics And Rollback Visibility

## Status

Accepted

## Context

Memory-policy candidates could be evaluated, canaried, and promoted or rolled back, but the operator did not have a durable analytics layer explaining the current recommendation after the fact, especially after later purge activity.

## Decision

The evolution layer now persists `MemoryPolicyAnalyticsRecord` objects that summarize:

- recommendation
- evaluation status
- canary status
- promotion state
- rollback risk
- rationale

Analytics are generated during memory-policy analysis and also persisted automatically when memory-policy candidates are promoted or rolled back.

## Consequences

- Operators keep visibility into policy outcomes even if lifecycle traces are later purged.
- Rollback becomes an operator-readable state instead of only an internal result flag.
- Future canary/promotion governance can build on a durable analytics history.
