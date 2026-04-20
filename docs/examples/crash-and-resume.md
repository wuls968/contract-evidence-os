# Crash and Resume

This example demonstrates intentional interruption and resume for the vertical slice.

## Scenario

1. Start a task with `interrupt_after="after_node_execute"`.
2. The runtime persists:
   - task state,
   - completed node receipt,
   - evidence nodes and edges,
   - latest checkpoint.
3. A `RuntimeInterrupted` exception is raised.
4. Call `resume_task(task_id)`.
5. The runtime loads the latest plan and checkpoint from SQLite, detects the completed node,
   skips duplicate execution, and finishes delivery.

## Verified By

- [tests/replay/test_crash_resume_and_lineage.py](/Users/a0000/contract-evidence-os/tests/replay/test_crash_resume_and_lineage.py:8)
