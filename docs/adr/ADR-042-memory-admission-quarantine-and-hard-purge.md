# ADR-042: Memory Admission, Quarantine, and Hard Purge

## Status

Accepted

## Context

AMOS could write, consolidate, delete by tombstone, and rebuild.
What it still lacked was a stronger governance boundary for suspicious memory candidates and a real physical purge path for scopes that must be removed from durable retrieval.

## Decision

We add:

- scope-level memory admission policies
- explicit quarantine and confirmation outcomes before consolidation
- hard purge runs that physically remove selected memory kinds from durable AMOS state

Quarantine is used for suspicious but not yet definitively malicious candidates.
Hard purge is used when tombstones are not strong enough for the requested forgetting behavior.

## Consequences

Positive:

- suspicious procedural memories no longer need to be either blindly blocked or silently accepted
- operators can distinguish reversible forgetting from durable purge
- memory governance becomes more explicit and testable

Tradeoff:

- hard purge intentionally targets AMOS-managed state only
- cache coherence must treat the repository as authoritative after purge
