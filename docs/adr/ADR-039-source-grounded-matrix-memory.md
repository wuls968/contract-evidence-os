# ADR-039: Source-Grounded Matrix Memory

## Status

Accepted

## Context

Associative memory is useful for high-speed recall, but black-box memory values are hard to audit, delete, and trust.
The runtime needs fast recall without giving up evidence lineage.

## Decision

Matrix memory in this system is implemented as source-grounded associative pointers.

Each pointer stores:

- head or memory lane
- compact key terms
- summary
- target raw episode ids
- target semantic fact ids
- target procedural pattern ids
- strength

Retrieval uses these pointers as a high-recall cueing layer.
Final answers must still ground themselves in raw episodes or semantic facts.

## Why Not Full Neural Memory First

- full neural memory would weaken auditability too early
- deletion and supersession are easier with pointer records
- pointer memory fits the existing contract/evidence runtime without architectural breakage

## Consequences

- associative recall is fast and explainable
- retrieval can survive long histories better than plain chunk search
- future learned low-rank matrix updates can reuse the same pointer targets and governance layer
