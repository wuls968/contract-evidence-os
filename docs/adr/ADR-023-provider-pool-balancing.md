# ADR-023: Provider-Pool Balancing Under Sustained Load

## Decision

Add a provider-pool manager that balances provider choice using health, reservations, pressure, and fairness hints rather than only per-request routing scorecards.

## Why

Multi-worker scaling introduces pool-level pressure that immediate routing alone cannot represent well.

## Consequences

- Verification and recovery can reserve provider capacity.
- Balancing decisions are explainable and persisted.
- Low-value work is easier to defer when the pool is under pressure.
