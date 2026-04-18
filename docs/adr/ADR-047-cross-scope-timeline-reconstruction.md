# ADR-047: Cross-Scope Timeline Reconstruction

## Status

Accepted

## Context

Single-scope timeline reconstruction was enough for task-local memory state.
It was not enough for users asking about state that evolved across related threads or task scopes.

## Decision

We add cross-scope timeline reconstruction that:

- collects temporal semantic facts from multiple scopes
- orders them by valid and observed time
- groups contiguous compatible state
- marks scope changes separately from state changes

The resulting segments remain typed and source grounded.

## Consequences

Positive:

- AMOS can reconstruct longer user/project narratives across task scopes
- operator reports can explain not just what changed, but where it changed
- cross-thread continuity becomes more useful without transcript replay

Tradeoff:

- cross-scope reconstruction remains rule-based
- semantics depend on consistent fact admission across scopes
