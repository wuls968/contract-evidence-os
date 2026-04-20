# SQLite Migrations

The runtime now persists its durable state in `contract_evidence_os.sqlite3` under the
runtime storage root.

## Migration Flow

The migration runner lives in
[src/contract_evidence_os/storage/migrations.py](/Users/a0000/contract-evidence-os/src/contract_evidence_os/storage/migrations.py)
and applies schema changes incrementally using `schema_migrations`.

Current migrations:

1. `001_initial_core`
   Creates durable tables for tasks, contracts, plan graphs, evidence, audit events,
   checkpoints, memory, and evolution records.
2. `002_query_indexes`
   Adds the indexes needed for audit query, lineage traversal, checkpoint lookup, and plan
   node status scans.
3. `003_routing_and_eval`
   Adds routing receipts for provider execution and evaluation-era benchmarking metadata.
4. `004_long_horizon_and_ops`
   Adds continuity records, approval inbox state, telemetry events, and tool scorecards for
   long-horizon operability.

## Version-Safe Loading

Persisted rows store `record_version` alongside the serialized payload. Load-time payload
upgrades are handled in
[src/contract_evidence_os/storage/migration_hooks.py](/Users/a0000/contract-evidence-os/src/contract_evidence_os/storage/migration_hooks.py).

Current upgrade shims normalize:

- legacy audit events without `risk_level`
- legacy tool invocations without idempotency metadata
- legacy tool results without provenance/confidence/provider-mode fields
- legacy continuity payloads without the current `created_at` default behavior

## Operational Notes

- Migrations run automatically when `SQLiteRepository` initializes.
- Schema changes remain additive and append-friendly by default.
- Exported artifacts may still be written to files, but the source of truth is SQLite.
