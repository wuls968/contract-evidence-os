# Milestone 4 Implementation Plan

Milestone 4 deepens the runtime into an operational execution engine without changing its core identity.

## Goals

- add at least one real live provider backend behind the current abstraction
- deepen execution from a shallow vertical slice into a persisted multi-node, branch-aware engine
- expose a small remote operator service on top of the existing operator API
- preserve contract-first execution, evidence-bound reasoning, audit-native traces, recovery, and governed evolution

## Implementation Order

1. Write failing tests for live providers, provider fallback, multi-node execution, replanning, recovery branches, remote approval, and execution-depth evals.
2. Add typed models and migration `005_execution_depth_and_remote_ops`.
3. Implement live provider adapters and provider usage persistence.
4. Extend planning and runtime execution into scheduler-driven multi-node execution with revision and recovery branches.
5. Add a lightweight token-authenticated HTTP operator service over the current operator API.
6. Add evaluation scenarios, ADRs, examples, and run the full suite.

## Boundaries

- no heavy agent framework rewrite
- no broad new product surface
- no bypass of contract, evidence, audit, recovery, or evolution layers
