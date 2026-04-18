# ADR-031: Stronger Durable Shared-State Backend Strategy

## Decision

Adopt a hybrid shared-state model for Milestone 9:

- SQLite remains the full local replay/audit repository.
- Redis remains the fast coordination path for queue and lease pressure.
- PostgreSQL becomes the first stronger durable shared-state option for cross-host coordination metadata, quota state, trust records, and reconciliation history.

## Why

Redis improves cross-host speed but is not the clearest place to anchor durable reconciliation and security metadata. PostgreSQL gives us a stronger transactional store without forcing the whole runtime to become a generic distributed scheduler.

## Consequences

- Durable shared-state becomes explicit rather than implied.
- Hybrid deployment assumptions are documented and testable.
- Replay clarity is preserved because task/evidence/audit history still lives in the core repository model.

