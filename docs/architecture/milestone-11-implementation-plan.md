# Milestone 11 Implementation Plan

## Goal

Deepen the runtime into a governed memory OS centered on AMOS:

- L0 raw episodic ledger
- L1 working memory snapshots
- L2 episodic retrieval via preserved episodes
- L3 temporal semantic facts and durative state
- L4 source-grounded associative matrix pointers
- L5 procedural patterns
- L6 editable explicit memory slots
- L7 governance, blocking, conflict handling, and dashboard visibility

## Scope

This milestone does not replace the existing contract/evidence/audit runtime.
It adds a typed memory subsystem that remains:

- source grounded
- replayable
- operator visible
- conflict aware
- safe to delete or supersede

## Implementation Slices

1. Extend typed memory models and reuse `runtime_state_records` for persistence.
2. Upgrade `MemoryMatrix` into an AMOS facade while preserving old lifecycle APIs.
3. Capture task request, working state, semantic constraints, and delivery facts from the runtime.
4. Add memory benchmark dataset and evaluation harness metrics.
5. Expose memory dashboard and evidence-pack surfaces through operator APIs.

## Intentional Minimums

- Matrix memory is pointer-based and auditable, not a black-box fact generator.
- Parametric memory remains an explicit editable lane instead of fine-tuning.
- Durative memory is lightweight and derived from temporal semantic updates.
- Governance is rule-based first, with room for future learned write policies.
