# Example: Degraded-Provider Survival

One live provider opens its circuit after repeated failures. The runtime:

- records degradation and cooldown,
- routes to the healthier compatible provider,
- emits routing and governance receipts,
- preserves queue state for tasks that still cannot safely run.

This keeps the system auditable under provider pressure rather than masking the failure.
