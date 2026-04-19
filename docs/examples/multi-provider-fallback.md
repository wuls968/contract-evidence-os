# Multi-Provider Fallback

1. A build or verification node requests structured output.
2. Routing policy prefers the primary provider based on current scorecards.
3. The primary provider fails with a retryable error or incompatible structured output.
4. `ProviderManager` falls through to the next provider in `provider_order`.
5. The runtime records:
   - the routing receipt,
   - the provider usage record,
   - the updated provider scorecard,
   - the routing decision and fallback path in audit/history.

This keeps failover observable and replayable instead of silently hiding it inside provider code.
