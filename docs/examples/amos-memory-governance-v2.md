# AMOS Memory Governance V2

This example shows the Milestone 15 memory-governance flow:

1. A procedural candidate with hidden approval-bypass language is governed.
2. The feature-scored admission controller emits a `MemoryAdmissionFeatureScore`.
3. A contradiction-aware timeline reconstructs a project state where a prior state later resumes.
4. A hard purge removes artifact and index layers and emits a `MemoryPurgeManifest`.
5. Memory-policy analytics remain visible after purge because they are persisted independently.

Typical operator surfaces:

- `GET /tasks/{task_id}/memory/project-state`
- `GET /tasks/{task_id}/memory/policy`
- `POST /tasks/{task_id}/memory/hard-purge`

Typical outcomes:

- `feature_scores` explain why a candidate was quarantined
- `project_state_snapshots` expose contradiction counts
- `purge_manifests` show exactly which derived layers were removed
- `analytics` explain whether a memory-policy candidate should be promoted, canaried, iterated, or rolled back
