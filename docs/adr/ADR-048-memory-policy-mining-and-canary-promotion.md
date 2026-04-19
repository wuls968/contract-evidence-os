# ADR-048: Memory Policy Mining and Canary Promotion

## Status

Accepted

## Context

Memory lifecycle traces already existed, but they were not yet first-class inputs to mining and promotion flow.
We needed a path from repeated memory-governance events to:

- candidate proposal
- evaluation
- canarying
- promotion

without bypassing the existing governed-evolution model.

## Decision

We add memory-policy mining runs that:

- mine repeated lifecycle traces
- propose `memory_policy` candidates
- require memory-governance evaluation metrics
- remain subject to canary and promotion gates

## Consequences

Positive:

- memory governance can improve from real lifecycle evidence
- promotion stays auditable and rollbackable
- AMOS memory policy joins the same evolution loop as other governed components

Tradeoff:

- mining is intentionally conservative and repetition-based
- candidate generation still needs strong trace support before activation
