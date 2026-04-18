# Recovery Under Cost Pressure

When a node fails under budget pressure, the runtime does not blindly spend through the failure.

Instead it:

1. preserves the failed path,
2. classifies the incident,
3. checks budget guardrails before retry or recovery work,
4. replans with an explicit recovery branch when justified,
5. records budget deltas and governance events for the recovery path.

This keeps recovery compatible with both auditability and reserve-aware execution.
