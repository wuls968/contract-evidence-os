# ADR-043: Temporal Timeline Reconstruction from Semantic Fact History

## Status

Accepted

## Context

AMOS already stored temporal semantic facts and durative records, but operator-visible reconstruction of evolving state remained shallow.
We needed a clearer way to answer questions such as:

- what state held first
- when did it change
- what evidence supports each phase

## Decision

We reconstruct timeline segments from temporal semantic fact history by:

- grouping facts by subject and predicate
- ordering them by valid time and observation time
- merging contiguous facts with the same object
- marking explicit state-change transitions between segments

The resulting segments are persisted as first-class timeline records.

## Consequences

Positive:

- operator surfaces can show memory evolution instead of only active facts
- AMOS can preserve update lineage without flattening history
- timeline reconstruction can be benchmarked and improved over time

Tradeoff:

- reconstruction is rule-based and conservative
- segment quality depends on the quality of temporal fact admission
