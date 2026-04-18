# ADR-013: Second Live Provider Backend

## Status
Accepted

## Context
Milestone 4 introduced one real live provider backend behind the provider abstraction. Milestone 5 requires the runtime to become truly multi-provider without flattening the system into a provider-specific orchestration stack.

## Decision
We added `AnthropicMessagesProvider` alongside the existing `OpenAIResponsesProvider`, both behind the same `ProviderManager` and `ProviderRequest` / `ProviderResponse` abstraction.

The runtime now persists:
- provider capability records,
- provider usage records,
- routing decisions,
- routing receipts,
- scorecard updates after each request.

## Rationale
- A second live backend proves the abstraction is real instead of decorative.
- Anthropic support exercises a different response shape and error surface than OpenAI.
- The contract/evidence runtime can now make policy-driven choices without binding itself to one vendor.

## Alternatives Rejected
- Hard-code a second provider directly into the runtime execution path.
- Add a generic third-party orchestration framework for provider routing.
- Treat simulator providers as sufficient proof of multi-provider support.

## Tradeoffs
- The runtime carries slightly more provider normalization code.
- Structured-output guarantees differ across vendors, so the abstraction must tolerate capability differences.

## Future Implications
- Additional providers should enter through the same capability and scorecard model.
- Provider-specific prompt shaping should remain behind the provider adapter boundary, not leak into contracts or plan nodes.
