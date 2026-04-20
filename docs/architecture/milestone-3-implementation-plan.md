# Milestone 3 Implementation Plan

This milestone deepens the Contract-Evidence OS into a long-horizon runtime rather than expanding its product surface.

## Scope

- Persist and use session handoff packets, open questions, next actions, context compaction, and continuity working sets.
- Resume across execution windows without replaying full transcript history.
- Preserve approval waits, checkpoints, and recovery context across sessions.
- Expose operator-facing inspection and control through a Python API and CLI.
- Add long-horizon evaluation metrics and gate continuity-related evolution candidates on those metrics.

## Implementation Outline

1. Extend typed continuity, approval, telemetry, and tool governance persistence.
2. Wire runtime checkpoints to continuity refresh, handoff generation, and working-set reconstruction.
3. Add approval inbox flows and intervention hooks as first-class operational controls.
4. Add CLI and operator API entrypoints over the existing SQLite-backed runtime.
5. Add long-horizon eval dataset types, graders, and strategy comparison harnesses.
6. Add production-shaped packaging, config loading, and operator examples.

## Non-Goals

- No heavy framework rewrite.
- No new flashy agent roles.
- No transcript-centric resume mechanism.
- No bypass of contract, evidence, audit, or verification layers.

