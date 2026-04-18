# Milestone 2 Implementation Plan

## Goal

Harden Contract-Evidence OS from a vertical-slice prototype into a production-candidate core
by replacing file persistence with SQLite, making execution resumable, and adding a real
evaluation and routing backbone without changing the system's identity.

## File Structure

- `src/contract_evidence_os/storage/`
  - SQLite migrations, migration runner, repository, and query helpers
- `src/contract_evidence_os/runtime/`
  - runtime service resume/replay logic, provider abstraction, routing manager
- `src/contract_evidence_os/evals/`
  - golden tasks, graders, comparison harness
- `src/contract_evidence_os/tools/`
  - structured tool result hardening and simulator/mock improvements
- `docs/adr/`
  - architecture decisions for SQLite persistence, resumable execution, and provider routing
- `docs/examples/`
  - crash/resume, replay, routing benchmark, evolution rollback
- `tests/`
  - persistence, migration, replay, recovery, evaluation, and routing tests

## Execution Steps

1. Write failing tests for SQLite migrations, repository round-trips, crash resume, replay,
   lineage query, and strategy comparison.
2. Implement the storage layer with indexed tables and migration runner.
3. Refactor runtime, audit, recovery, memory, and evolution to use the repository.
4. Add provider abstraction and integrate routing receipts into the runtime.
5. Implement evaluation datasets, graders, and candidate gating from evaluation outputs.
6. Add docs and example scenarios.
7. Run the full test suite and fix any regressions.
