# Milestone 22 Implementation Plan

Milestone 22 deepens AMOS from a scheduled maintenance fabric into a more resident, operator-grade maintenance runtime.

This increment focuses on:

- resident maintenance worker registration, heartbeat, and schedule claim semantics
- explicit maintenance incident resolution and degraded-mode clearing
- maintenance controller rollout apply/rollback with auditable records
- remote control-plane and CLI surfaces for worker cycles and rollout governance

The implementation remains minimal and source-grounded:

- maintenance workers only claim AMOS maintenance schedules; they do not introduce a second general scheduler
- rollout state only switches maintenance controller versions between `v1` and `v2`
- incident resolution is explicit and auditable instead of silent automatic recovery
- operator and remote service surfaces expose workers, incidents, rollouts, and controller state
