# Interruption And Resume

Use `RuntimeService.run_task(..., interrupt_after="planned")` or `interrupt_after="after_node_execute"` to simulate a session boundary.

Then call `resume_task(task_id)` to reconstruct the working set from:

- latest checkpoint,
- latest handoff packet,
- open question ledger,
- next action ledger,
- compacted hot and warm context,
- pending approvals.

