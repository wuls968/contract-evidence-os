# ADR-044: Memory Policy Evolution from Lifecycle Traces

## Status

Accepted

## Context

AMOS memory policy should improve from real lifecycle outcomes, not only from hand-authored rules.
By Milestone 12 the system could observe deletion, consolidation, and rebuild.
It still lacked a formal path to convert those signals into governed evolution candidates.

## Decision

We add memory lifecycle traces as a durable evolution input.

These traces capture:

- quarantine outcomes
- hard purge compliance
- timeline reconstruction outcomes

The evolution engine can then:

- propose `memory_policy` candidates
- require a dedicated `memory-lifecycle` evaluation suite
- keep promotion eval-gated instead of auto-adaptive

## Consequences

Positive:

- memory governance can improve from runtime evidence
- trace-backed policy changes fit the existing governed-evolution model
- AMOS memory policy changes stay auditable and rollbackable

Tradeoff:

- lifecycle learning remains conservative and metric-driven
- no online self-modifying memory policy is allowed
