# Approval-Delayed Branch

Scenario:
- The contract implies external publication.
- The verification node is approval-gated.
- Execution pauses with `awaiting_approval`.
- The operator approves later and the task resumes on the same persisted task id.

Expected artifacts:
- approval request
- approval decision
- handoff packet with pending approval ids
- scheduler transition from `waiting_for_approval` back to `running`
