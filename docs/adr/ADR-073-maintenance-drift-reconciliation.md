# ADR-073: Maintenance Drift Reconciliation

## Status

Accepted

## Context

AMOS already mirrored memory indexes into a shared artifact backend, but it did not explicitly model drift between the local source-grounded index and the shared mirror.

## Decision

We add `MemoryArtifactDriftRecord` and a `scan_artifact_drift(...)` path that compares local and shared artifact payloads by scope and artifact kind. Background maintenance may recommend and execute `reconcile_shared_artifacts`, which rewrites shared mirrors from the local source-grounded index and marks active drift records as reconciled.

## Consequences

- operators can see drift instead of inferring it from vague backend failures
- shared-index repair is now separate from missing-file repair
- reconciliation remains auditable because it rewrites from AMOS-owned artifacts rather than opaque external state
