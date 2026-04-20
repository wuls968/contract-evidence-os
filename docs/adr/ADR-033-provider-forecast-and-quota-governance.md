# ADR-033: Provider Forecast and Quota Governance

## Decision

Extend provider governance from reactive health and reservation handling into explicit demand forecasts, quota policies, and quota decisions.

## Why

Under sustained load, the runtime needs to protect verification, recovery, and higher-risk work before capacity is already exhausted.

## Consequences

- Provider routing can consider near-term demand, not only current health.
- Low-value work can be deferred for quota reasons with a recorded explanation.
- Operators can inspect why a reservation or quota boundary dominated a routing decision.

