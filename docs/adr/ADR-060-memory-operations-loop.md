# ADR-060: Memory Operations Loop

## Status

Accepted

## Context

Consolidation, rebuild, and contradiction repair signals existed, but there was no joined run object representing a sleep-time memory recovery loop.

## Decision

Add `MemoryOperationsLoopRun` and `run_memory_operations_loop(...)` to join:

1. sleep-time consolidation
2. selective rebuild of key layers
3. persisted counters for synthesized state and repaired artifacts

## Consequences

- operator workflows gain a single recovery primitive
- evals can measure whether the memory loop actually completed
- future milestones can extend the loop with richer repair planners without changing the control shape
