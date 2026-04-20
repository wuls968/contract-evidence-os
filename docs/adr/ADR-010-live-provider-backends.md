# ADR-010 Live Provider Backends

## Status
Accepted

## Decision
Milestone 4 keeps the existing provider abstraction and adds a real OpenAI Responses backend behind it instead of replacing the abstraction with a framework SDK layer.

## Rationale
- The runtime already routes by role, workload, and risk.
- A live backend had to fit the same receipt, retry, fallback, and replay model as simulator providers.
- The OpenAI Responses API supports typed JSON outputs cleanly enough for contract-bound build and verification steps.

## Consequences
- `ProviderRequest`, `ProviderResponse`, `ProviderUsageRecord`, and `RoutingReceipt` remain the stable provider boundary.
- Live provider calls are audited and persisted with the same correlation fields as simulator calls.
- Failure to reach a live provider degrades through the existing fallback path instead of creating a side-channel.

## Alternatives Rejected
- Directly calling provider SDKs from node handlers.
- Replacing provider routing with a third-party agent framework.
- Keeping all providers simulator-only.
