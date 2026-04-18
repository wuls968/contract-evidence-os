# Milestone 14 Implementation Plan

## Goal

Deepen AMOS from lifecycle governance into a more recoverable and self-improving memory operating system with:

- selective physical purge for derived memory artifacts
- a first learned admission controller driven by lifecycle traces
- cross-scope temporal timeline reconstruction
- lifecycle-trace mining that can produce canaryable memory-policy candidates

## Scope

This milestone keeps AMOS grounded in explicit, typed, auditable state.
The focus is not on black-box learning.
It is on making memory governance more adaptive without weakening source grounding or replay clarity.

## Core Additions

1. **Selective purge**
   - Physical purge of derived memory layers such as evidence packs, dashboard items, and risky governance artifacts
   - Preserve surviving semantic and raw history where the operator only wants derived state cleared

2. **Admission learning state**
   - Trace-informed learning state for quarantine sensitivity
   - Policy remains explicit and inspectable; learning only adjusts thresholds and boosts

3. **Cross-scope timeline reconstruction**
   - Reconstruct related state evolution across multiple task scopes
   - Distinguish state changes from scope changes

4. **Lifecycle-driven policy mining**
   - Mine memory-policy candidates from repeated quarantine, purge, and timeline-rebuild traces
   - Keep candidate promotion eval-gated and canary-mediated

5. **Operator and benchmark surfaces**
   - Memory policy state
   - Selective purge control
   - Cross-scope timeline endpoint
   - Governance benchmark metrics for learned admission and canary promotion

## Intentional Minimums

- Learned admission is trace-informed threshold tuning, not a neural memory gate.
- Cross-scope timeline reconstruction remains rule-based and typed.
- Policy mining is conservative and only proposes candidates when trace repetition is strong.
- Selective purge targets AMOS-managed runtime state, not every downstream storage system.
