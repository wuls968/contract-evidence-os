# Milestone 13 Implementation Plan

## Goal

Deepen AMOS from a lifecycle-capable memory substrate into a governed memory policy system with:

- poison-aware admission and quarantine
- selective hard purge for durable forgetting requests
- temporal timeline reconstruction for evolving state
- lifecycle traces that can drive eval-gated memory policy evolution

## Scope

This milestone stays focused on AMOS correctness and governance depth.
It does not broaden the runtime into a generic knowledge platform.

The emphasis is:

- deciding what should not be consolidated
- physically removing memory when the request demands it
- reconstructing meaningful temporal state from fact history
- learning from memory lifecycle outcomes without bypassing evaluation

## Core Additions

1. **Admission policy and quarantine**
   - Scope-specific memory admission policies
   - Quarantine path for medium-risk poisoning or override patterns
   - Confirmation gate for sensitive or contradictory candidates

2. **Hard purge**
   - Physical deletion of selected memory kinds from durable state
   - Support for raw episodes, semantic facts, matrix pointers, and related timeline artifacts

3. **Timeline reconstruction**
   - Rebuild durative state segments from temporal fact history
   - Preserve state changes instead of flattening updates into a single active fact

4. **Lifecycle traces**
   - Persist lifecycle traces for quarantine, purge, and timeline events
   - Use those traces to propose memory-policy candidates through the evolution engine

5. **Operator and remote surfaces**
   - Timeline inspection
   - Remote hard purge
   - Memory-policy benchmark reporting

## Intentional Minimums

- Quarantine is heuristic and policy-driven, not a learned classifier.
- Hard purge targets AMOS runtime state, not every downstream artifact store in the system.
- Timeline reconstruction is rule-based over semantic fact history, not a learned temporal planner.
- Memory-policy evolution remains eval-gated and trace-backed instead of self-promoting online.
