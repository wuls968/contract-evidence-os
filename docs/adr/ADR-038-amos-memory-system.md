# ADR-038: AMOS Memory System

## Status

Accepted

## Context

The runtime already had persistence, continuity, audit, evaluation, and recovery.
What it lacked was a layered memory system that could preserve raw experience while also supporting temporal reasoning, associative recall, and governed long-term reuse.

## Decision

We introduce AMOS: Auditable Matrix-Graph Operating Memory System.

AMOS is implemented as complementary memory lanes:

- raw episodic ledger for lossless evidence preservation
- working memory snapshots for execution-critical state
- temporal semantic facts for structured long-term state
- source-grounded matrix pointers for high-recall associative retrieval
- procedural patterns for reusable execution experience
- explicit editable records for future parametric-style memory
- governance decisions and dashboard views for operator trust

The system keeps raw evidence authoritative.
Derived memory objects may accelerate retrieval or reasoning, but they do not replace source provenance.

## Consequences

Positive:

- better long-horizon recall without transcript replay
- stronger temporal updates and supersession handling
- auditable evidence packs
- safer memory writes with blocking of obvious poisoning patterns

Tradeoffs:

- more typed state to maintain
- memory retrieval is more structured but also more opinionated
- matrix memory remains intentionally conservative until stronger learned policies exist
