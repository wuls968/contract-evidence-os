# ADR-049: Expanded Purge Manifests And Artifact Layers

## Status

Accepted

## Context

AMOS already supported tombstones, selective purge, and hard purge, but deeper derived layers such as working snapshots, evidence packs, dashboard rows, lifecycle traces, and reconstructed project-state views were not all covered or explicitly reported.

## Decision

Hard purge now covers a broader set of artifact and index layers by default, and both hard and selective purge emit a typed `MemoryPurgeManifest` describing:

- purge mode
- target kinds
- purged record ids by kind
- cascaded record ids
- preserved summaries for selective purge

## Consequences

- Operators can audit what was actually removed instead of inferring from counts alone.
- Purge semantics are now explicit enough to extend further into external artifact layers later.
- Purge manifests remain durable even when the underlying scope memory is removed.
