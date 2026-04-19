# Evidence Replay

The runtime can replay a completed vertical-slice task from SQLite-backed state.

Replay includes:

- task request and persisted result,
- contract and lattice,
- plan graph,
- evidence graph,
- claims,
- audit events,
- execution receipts,
- routing receipts,
- tool invocations and tool results.

Evidence lineage queries walk upstream from a target evidence node through persisted
`evidence_edges` to reconstruct provenance chains.

## Verified By

- [tests/replay/test_crash_resume_and_lineage.py](/Users/a0000/contract-evidence-os/tests/replay/test_crash_resume_and_lineage.py:40)
- [tests/unit/test_storage_sqlite.py](/Users/a0000/contract-evidence-os/tests/unit/test_storage_sqlite.py:77)
