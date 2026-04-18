# ADR-065 Shared Artifact Backend Repair

## Status

Accepted

## Context

AMOS already materialized local artifact and index files, but Milestone 19 needs a more realistic path for repairing shared memory indexes used beyond one local runtime.

## Decision

We add a second artifact backend mode, `shared_fs`, alongside the existing `local_fs` path. Shared artifact mirrors are still simple files, but they are tracked as first-class AMOS artifacts with backend identity, health snapshots, and repair runs.

## Consequences

- shared memory indexes remain source-grounded files, not opaque remote state
- operator surfaces can now explain missing shared artifacts explicitly
- rebuild and purge semantics remain understandable because both backends use the same artifact registry

