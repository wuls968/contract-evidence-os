# Runbook: Provider Degradation

When provider routing quality drops or circuit breakers open:

1. Inspect `GET /providers/health`.
2. Review `degradation_events`, `cooldown_windows`, and `rate_limit_states`.
3. If one provider is unsafe, disable it with `POST /providers/control` and `action=disable_provider`.
4. If recovery is suspected, use `action=force_half_open_probe` for a controlled probe.
5. Confirm routing receipts show fallback choices and policy reasons.
6. If degradation persists, keep the provider disabled and promote a temporary routing candidate only after evaluation.
