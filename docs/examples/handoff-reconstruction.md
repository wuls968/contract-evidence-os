# Handoff Reconstruction

`ContinuityManager.reconstruct_working_set()` rebuilds an execution-ready slice for a role without loading the full task history.

For example:

- `Strategist` gets contract and plan deltas.
- `Researcher` gets evidence frontier and unresolved questions.
- `Governor` gets risk and approval state.

