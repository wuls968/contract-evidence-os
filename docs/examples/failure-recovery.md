# Failure and Recovery Example

If the target file is missing:

1. The retrieval tool emits a failed `ToolResult`.
2. The orchestrator records an `AuditEvent` and a failure `ExecutionReceipt`.
3. The recovery engine classifies the incident as a retriable environment failure.
4. A checkpoint is restored or a local replan is attempted.
5. An incident report is written if the task remains blocked.
