# ADR-006: Provider Routing and Evaluation Gating

## Decision

Introduce a provider-agnostic model execution layer with routing receipts, deterministic
simulator providers, strategy comparison benchmarking, and evaluation-gated evolution
promotion.

## Rationale

Policy-only routing was not enough for production hardening. The runtime needs a real
execution interface for provider requests, retries, fallback, and route receipts. Evolution
promotion must also depend on measured evaluation outputs rather than hand-fed gains.

## Alternatives Rejected

- Keep routing as a pure metadata decision with no provider abstraction
- Hard-wire a single external SDK into the runtime
- Promote evolution candidates from local heuristics with no benchmark report

## Tradeoffs

The current provider layer is simulator-first, but the interface is stable enough for later
production providers without changing runtime orchestration semantics.
