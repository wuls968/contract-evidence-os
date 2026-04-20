# Milestone 17 Implementation Plan

## Goal

Push AMOS from governed memory operations into a tighter memory-recovery loop:

- selective rebuild and partial repair for damaged memory layers
- contradiction repair canary plus apply/rollback semantics
- admission-canary signals mined into governed memory-policy candidates
- a joined sleep-time operations loop that synthesizes, repairs, and rebuilds

## Scope

This milestone stays inside the existing contract/evidence/audit architecture. It does not add new memory lanes. It hardens how AMOS repairs and evolves the lanes it already owns.

## Main Changes

1. Add typed run records for:
   - selective rebuild
   - contradiction repair canary
   - contradiction repair apply/rollback
   - joined memory operations loop
2. Extend `MemoryMatrix` with:
   - selective rebuild over specific target kinds
   - repair canary decision path
   - apply / rollback for cross-scope contradiction repairs
   - an operations loop that chains consolidation and rebuild
3. Extend `EvolutionEngine` so admission-canary evidence can feed governed memory-policy mining.
4. Expose the new behavior through operator and remote service endpoints.
5. Extend evals to measure:
   - selective rebuild recovery
   - repair apply/rollback safety
   - canary-to-evolution linkage
   - memory operations loop completion

## Verification

- targeted unit/integration/eval tests for Milestone 17
- full regression suite across `/Users/a0000/contract-evidence-os/tests`
