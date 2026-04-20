import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from contract_evidence_os.audit.models import AuditEvent
from contract_evidence_os.contracts.compiler import ContractCompiler
from contract_evidence_os.evidence.graph import EvidenceBuilder
from contract_evidence_os.evidence.models import SourceRecord
from contract_evidence_os.storage.migrations import MigrationRunner
from contract_evidence_os.storage.repository import SQLiteRepository


def _now() -> datetime:
    return datetime(2026, 4, 17, 0, 0, tzinfo=UTC)


def test_migration_runner_applies_incremental_schema_versions(tmp_path: Path) -> None:
    db_path = tmp_path / "ceos.sqlite3"
    runner = MigrationRunner(db_path)

    runner.apply_up_to("001_initial_core")
    assert runner.current_version() == "001_initial_core"

    runner.apply_all()
    assert runner.current_version() == "011_software_control_harness_indexes"


def test_repository_round_trips_models_and_upgrades_legacy_payloads(tmp_path: Path) -> None:
    db_path = tmp_path / "ceos.sqlite3"
    repo = SQLiteRepository(db_path)

    event = AuditEvent(
        version="1.0",
        event_id="audit-001",
        task_id="task-001",
        contract_id="contract-001",
        event_type="tool_invocation",
        actor="Researcher",
        why="Need source evidence",
        evidence_refs=["evidence-001"],
        tool_refs=["file-retrieval"],
        approval_refs=[],
        result="success",
        rollback_occurred=False,
        learning_candidate_generated=False,
        system_version="0.1.0",
        skill_version="initial",
        timestamp=_now(),
        risk_level="moderate",
    )
    repo.save_audit_event(event)
    assert repo.query_audit(task_id="task-001")[0] == event

    legacy_payload = event.to_dict()
    legacy_payload.pop("risk_level")
    legacy_payload["version"] = "0.9"

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO audit_events (
                event_id, task_id, contract_id, event_type, actor, risk_level,
                timestamp, record_version, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "audit-legacy-001",
                "task-legacy",
                "contract-legacy",
                "tool_invocation",
                "Researcher",
                "",
                _now().isoformat(),
                "0.9",
                repo.dumps(legacy_payload),
            ),
        )

    migrated = repo.query_audit(task_id="task-legacy")
    assert migrated[0].risk_level == "low"
    assert migrated[0].version == "1.0"


def test_repository_supports_evidence_lineage_queries(tmp_path: Path) -> None:
    db_path = tmp_path / "ceos.sqlite3"
    repo = SQLiteRepository(db_path)
    compiler = ContractCompiler()
    contract = compiler.compile(
        goal="Read the attachment and summarize the mandatory constraints with evidence.",
        attachments=["/tmp/example.txt"],
        preferences={},
        prohibitions=["do not delete audit history"],
    )
    repo.save_contract(task_id="task-001", contract=contract)

    evidence = EvidenceBuilder()
    source = SourceRecord(
        version="1.0",
        source_id="source-001",
        source_type="file",
        locator="/tmp/example.txt",
        retrieved_at=_now(),
        credibility=0.95,
        time_relevance=1.0,
        content_hash="abc123",
        snippet="Audit history must never be deleted.",
    )
    source_node = evidence.add_source(source)
    extraction = evidence.add_extractions(source_node, ["Audit history must never be deleted."])[0]

    repo.save_source_record(task_id="task-001", source=source)
    repo.save_evidence_graph(task_id="task-001", graph=evidence.graph, claims=evidence.claims)

    lineage = repo.evidence_lineage(task_id="task-001", node_id=extraction.node_id)

    assert {node.node_type for node in lineage["nodes"]} == {"source", "extraction"}
    assert lineage["edges"]
