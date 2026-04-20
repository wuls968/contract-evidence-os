# AMOS Memory Operations V3

This example shows the Milestone 16 operational memory loop:

1. A task produces governed memory state and exported delivery artifacts.
2. `rebuild_indexes` regenerates matrix pointers and materializes JSON memory indexes.
3. `run_sleep_consolidation` synthesizes project-state snapshots and contradiction counts.
4. `run_admission_controller_canary` compares baseline admission against the feature-scored controller.
5. `repair_cross_scope_contradictions` emits a recommendation when active state conflicts across scopes.
6. `hard_purge_scope(target_kinds=["artifact_file"])` removes governed artifact files.

Operator-visible surfaces:

- `GET /tasks/{task_id}/memory/artifacts`
- `POST /tasks/{task_id}/memory/admission-canary`
- `GET /memory/cross-scope-repairs`
- `GET /tasks/{task_id}/memory/policy`

Expected outcomes:

- artifact files are registered and purgeable
- consolidation reports project-state synthesis depth
- admission canary reports whether v2 should be promoted or held
- contradiction repair records explain which cross-scope state should currently dominate
