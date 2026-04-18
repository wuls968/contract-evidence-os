# ADR-032: Predictive Lease Management and Conflict Recovery

## Decision

Add prediction-aware lease records, conflict quarantine, and reconciliation runs as first-class runtime objects instead of relying only on immediate renew/reclaim outcomes.

## Why

Cross-host reliability failures often happen in the gray zone between healthy and stale. Latency spikes, delayed heartbeats, and reclaim races need recorded forecasts and explicit recovery actions.

## Consequences

- Renewal decisions can explain why they were urgent or risky.
- Ownership conflicts produce quarantine records instead of silent rejection only.
- Reconciliation becomes a named, auditable repair path after outage or ambiguity.

