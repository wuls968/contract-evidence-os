# Example: Governed CLI-Anything Software Control

## Scenario

An operator registers a generated `cli-anything-demo` harness and invokes a safe command.

## Flow

1. Register the harness through the operator service.
2. Validate that `--help` and `--json` are available.
3. Invoke `status`.
4. The runtime auto-creates or joins a task.
5. The result is written as:
   - `ToolInvocation`
   - `ToolResult`
   - `ExecutionReceipt`
   - audit event
   - evidence source + extraction nodes

## Outcome

The software action becomes part of the normal contract/evidence/audit lifecycle instead of living in an opaque shell transcript.
