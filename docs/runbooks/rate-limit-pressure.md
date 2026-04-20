# Runbook: Rate-Limit Pressure

Rate-limit pressure should change routing and admission before it becomes an outage.

1. Inspect `GET /providers/health`.
2. Verify which provider is saturated and whether the cooldown window is active.
3. If both compatible providers are constrained, expect queue deferrals instead of unsafe dispatch.
4. Temporarily reduce admission pressure with drain mode or lower-cost routing when appropriate.
5. After cooldown, use restart recovery or a half-open probe to restore normal operation.
