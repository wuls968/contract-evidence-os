# ADR-041: Sleep-Time Consolidation and Rebuild

## Status

Accepted

## Context

AMOS already stored raw episodes, semantic facts, and matrix pointers.
What it lacked was a controlled lifecycle phase that could:

- reconstruct durative state
- deduplicate associative pointers
- refresh indexes after change

## Decision

We add explicit consolidation and rebuild runs.

Consolidation:

- groups temporal semantic facts by subject and predicate
- reconstructs durative records
- deduplicates repeated matrix pointers conservatively

Rebuild:

- regenerates source-grounded matrix pointers from surviving active semantic facts
- refreshes operator-visible dashboard material

## Consequences

Positive:

- memory state improves over time instead of only accumulating
- temporal retrieval gets a clearer durable layer
- deletion and consolidation can be followed by deterministic repair

Tradeoff:

- rebuild remains intentionally simple and pointer-based
- no learned consolidation policy is introduced yet
