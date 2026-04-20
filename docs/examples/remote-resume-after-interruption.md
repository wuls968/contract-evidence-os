# Remote Resume After Interruption

Scenario:
- A task is interrupted after a durable checkpoint.
- A remote operator inspects task status and pending approvals through the HTTP service.
- The operator resumes the task remotely.

Expected artifacts:
- checkpoint list
- remote approval operation if approval is involved
- resumed task result from the remote service
- updated handoff packet and continuity working set after resume
