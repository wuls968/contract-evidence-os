# Milestone 18 Implementation Plan

## Goal

Push AMOS from a one-shot memory repair loop into a more operator-grade repair fabric with:

- repair safety gating
- rollout analytics
- admission promotion recommendations
- periodic memory operations scheduling, interruption recovery, and diagnostics

## Scope

This milestone stays inside the current AMOS and runtime architecture. It does not introduce a new daemon or external scheduler. It adds typed records and operator-visible control points around the recovery loop AMOS already owns.

## Main Changes

1. Add typed records for:
   - repair safety assessment
   - repair rollout analytics
   - admission promotion recommendation
   - memory operations loop schedules
   - interrupted loop recovery
   - memory operations diagnostics
2. Extend contradiction repair so canaries are safety-scored before apply.
3. Persist analytics for both apply and rollback.
4. Let admission canary evidence produce a governed promotion recommendation that evolution mining can consume.
5. Add periodic scheduling, interrupt/resume, and diagnostic visibility for the memory operations loop.

## Verification

- targeted Milestone 18 unit / integration / evaluation tests
- full regression suite under `/Users/a0000/contract-evidence-os/tests`
