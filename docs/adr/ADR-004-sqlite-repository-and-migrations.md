# ADR-004: SQLite Repository and Migrations

## Decision

Replace file-by-file JSON and JSONL persistence with a single SQLite-backed repository layer,
using incremental schema migrations and version-aware payload loading.

## Rationale

Milestone 2 needs indexed audit queries, crash resume, replay, lineage traversal, and
evaluation history. SQLite gives us transactional durability, simple deployment, and query
power without turning the project into a service mesh.

## Alternatives Rejected

- Keep JSON/JSONL files as the primary store: too weak for indexed query and replay
- Add a network database immediately: unnecessary operational complexity at this stage
- Use one giant key-value blob table: weaker lineage and query ergonomics

## Tradeoffs

The repository layer adds schema management and SQL complexity, but it preserves the
existing modular architecture and keeps persistence local and inspectable.
