# AMOS Memory Operations V4

Milestone 17 adds a tighter memory-operations recovery loop:

1. a scope suffers partial damage such as missing index files or lost matrix pointers
2. `selective_rebuild_scope(...)` repairs only the affected layers
3. cross-scope contradictions produce a `MemoryRepairCanaryRun`
4. the operator can apply the repair, observe the resulting active state, then rollback if needed
5. admission-canary evidence can be mined into a governed memory-policy candidate
6. `run_memory_operations_loop(...)` joins consolidation and selective rebuild into one persisted recovery pass

This keeps AMOS auditable: every recovery action is typed, persisted, and reversible where practical.
