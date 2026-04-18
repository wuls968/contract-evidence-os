# Example: CLI-Anything Approval-Gated Destructive Command

## Scenario

A registered harness exposes a command like `delete-layer`.

## Expected Runtime Behavior

1. The runtime classifies the command as destructive from policy.
2. Execution is blocked before the subprocess runs.
3. An `ApprovalRequest` is created and linked to the software-control action.
4. Audit records show:
   - approval requested
   - why it was required
   - which harness and command were involved
5. After approval, the same task can retry the invocation with explicit authorization.

## Why This Matters

This keeps software control aligned with the system's governance model. Desktop power does not become a side door around approval policy.
