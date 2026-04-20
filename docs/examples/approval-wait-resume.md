# Approval Wait Then Resume

Moderate- and high-risk contracts can pause at an approval gate.

The runtime persists:

- `ApprovalRequest`
- audit events bound to the request
- a checkpoint at the approval wait boundary
- a handoff packet that recommends the next action: resolve the approval queue

After the operator records an approval decision, `resume_task()` continues from the latest stable checkpoint.

