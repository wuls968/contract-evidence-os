"""Durable shared-state backends and descriptors."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from contract_evidence_os.base import SchemaModel, utc_now
from contract_evidence_os.runtime.backends import BackendHealthRecord

try:  # pragma: no cover - optional dependency path
    import psycopg
except Exception:  # pragma: no cover - exercised when postgres backend is not installed
    psycopg = None  # type: ignore[assignment]


def _require_psycopg() -> Any:
    if psycopg is None:
        raise RuntimeError("psycopg is required for the postgres shared-state backend")
    return psycopg


@dataclass
class SharedStateBackendDescriptor(SchemaModel):
    """Descriptor for one durable shared-state backend."""

    version: str
    backend_name: str
    backend_kind: str
    durability_class: str
    coordination_capability: str
    transaction_capability: str
    reconciliation_capability: str
    failure_modes: list[str]
    deployment_assumption: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class NetworkIdentityRecord(SchemaModel):
    """Observed network identity assertion tied to a trusted request."""

    version: str
    network_identity_id: str
    principal_id: str
    source_address: str
    asserted_identity: str
    trust_mode: str
    status: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


class SharedStateBackend(Protocol):
    """Shared-state backend interface for durable cross-host runtime metadata."""

    def descriptor(self) -> SharedStateBackendDescriptor: ...

    def health(self) -> BackendHealthRecord: ...

    def save_descriptor(self, descriptor: SharedStateBackendDescriptor) -> None: ...

    def save_health(self, record: BackendHealthRecord) -> None: ...

    def upsert_record(self, *, record_type: str, record_id: str, scope_key: str, payload: dict[str, object]) -> None: ...

    def load_record(self, record_type: str, record_id: str) -> dict[str, object] | None: ...

    def list_records(self, record_type: str, *, scope_key: str | None = None) -> list[dict[str, object]]: ...


class SQLiteSharedStateBackend:
    """SQLite reference implementation for durable shared-state records."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def descriptor(self) -> SharedStateBackendDescriptor:
        return SharedStateBackendDescriptor(
            version="1.0",
            backend_name="sqlite_shared_state",
            backend_kind="sqlite",
            durability_class="single_host_durable_file",
            coordination_capability="durable_shared_metadata",
            transaction_capability="local_atomic_upsert",
            reconciliation_capability="checkpoint_and_record_repair",
            failure_modes=["file_lock_contention", "single_host_limit"],
            deployment_assumption="local sqlite file in runtime storage",
        )

    def health(self) -> BackendHealthRecord:
        return BackendHealthRecord(
            version="1.0",
            backend_name="sqlite_shared_state",
            backend_kind="sqlite",
            status="available",
            latency_ms=0.0,
            connected=True,
        )

    def save_descriptor(self, descriptor: SharedStateBackendDescriptor) -> None:
        self.upsert_record(
            record_type="shared_state_backend_descriptor",
            record_id=descriptor.backend_name,
            scope_key=descriptor.backend_kind,
            payload=descriptor.to_dict(),
        )

    def save_health(self, record: BackendHealthRecord) -> None:
        self.upsert_record(
            record_type="shared_state_backend_health",
            record_id=f"{record.backend_name}:{record.updated_at.isoformat()}",
            scope_key=record.backend_name,
            payload=record.to_dict(),
        )

    def upsert_record(self, *, record_type: str, record_id: str, scope_key: str, payload: dict[str, object]) -> None:
        created_at = payload.get("created_at") or payload.get("updated_at") or utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO shared_state_records(record_type, record_id, scope_key, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(record_type, record_id) DO UPDATE SET
                    scope_key=excluded.scope_key,
                    created_at=excluded.created_at,
                    payload_json=excluded.payload_json
                """,
                (record_type, record_id, scope_key, str(created_at), json.dumps(payload, ensure_ascii=True, sort_keys=True)),
            )
            connection.commit()

    def load_record(self, record_type: str, record_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM shared_state_records WHERE record_type = ? AND record_id = ?",
                (record_type, record_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "record_type": row["record_type"],
            "record_id": row["record_id"],
            "scope_key": row["scope_key"],
            "payload": json.loads(str(row["payload_json"])),
            "created_at": row["created_at"],
        }

    def list_records(self, record_type: str, *, scope_key: str | None = None) -> list[dict[str, object]]:
        query = "SELECT * FROM shared_state_records WHERE record_type = ?"
        params: tuple[Any, ...] = (record_type,)
        if scope_key is not None:
            query += " AND scope_key = ?"
            params += (scope_key,)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            {
                "record_type": row["record_type"],
                "record_id": row["record_id"],
                "scope_key": row["scope_key"],
                "payload": json.loads(str(row["payload_json"])),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS shared_state_records (
                    record_type TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (record_type, record_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_shared_state_records_scope ON shared_state_records(record_type, scope_key, created_at)"
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection


class PostgresSharedStateBackend:
    """PostgreSQL-backed durable shared-state backend with optional injected client."""

    def __init__(
        self,
        *,
        url: str | None = None,
        client: Any | None = None,
        schema: str = "public",
    ) -> None:
        self.url = url
        self.client = client
        self.schema = schema
        if self.client is None and self.url is not None:
            module = _require_psycopg()
            self.client = module.connect(self.url)
            self._ensure_schema()

    def descriptor(self) -> SharedStateBackendDescriptor:
        return SharedStateBackendDescriptor(
            version="1.0",
            backend_name="postgres_shared_state",
            backend_kind="postgres",
            durability_class="shared_transactional_store",
            coordination_capability="durable_shared_metadata_and_reconciliation",
            transaction_capability="transactional_upsert",
            reconciliation_capability="cross_host_repair_after_outage",
            failure_modes=["connection_loss", "partial_write_visibility", "pool_exhaustion"],
            deployment_assumption="shared postgres service reachable by runtime roles",
        )

    def health(self) -> BackendHealthRecord:
        started = time.perf_counter()
        try:
            if self.client is None:
                raise RuntimeError("postgres shared-state backend not configured")
            if hasattr(self.client, "ping"):
                self.client.ping()
            else:  # pragma: no cover - only used with live postgres
                with self.client.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            latency = (time.perf_counter() - started) * 1000.0
            return BackendHealthRecord(
                version="1.0",
                backend_name="postgres_shared_state",
                backend_kind="postgres",
                status="available",
                latency_ms=latency,
                connected=True,
            )
        except Exception as exc:  # pragma: no cover - exercised through outage tests later
            return BackendHealthRecord(
                version="1.0",
                backend_name="postgres_shared_state",
                backend_kind="postgres",
                status="degraded",
                latency_ms=0.0,
                connected=False,
                last_error=str(exc),
            )

    def save_descriptor(self, descriptor: SharedStateBackendDescriptor) -> None:
        self.upsert_record(
            record_type="shared_state_backend_descriptor",
            record_id=descriptor.backend_name,
            scope_key=descriptor.backend_kind,
            payload=descriptor.to_dict(),
        )

    def save_health(self, record: BackendHealthRecord) -> None:
        self.upsert_record(
            record_type="shared_state_backend_health",
            record_id=f"{record.backend_name}:{record.updated_at.isoformat()}",
            scope_key=record.backend_name,
            payload=record.to_dict(),
        )

    def upsert_record(self, *, record_type: str, record_id: str, scope_key: str, payload: dict[str, object]) -> None:
        if self.client is None:
            raise RuntimeError("postgres shared-state backend not configured")
        if hasattr(self.client, "upsert_record"):
            self.client.upsert_record(record_type=record_type, record_id=record_id, scope_key=scope_key, payload=payload)
            return
        self._ensure_schema()
        created_at = payload.get("created_at") or payload.get("updated_at") or utc_now().isoformat()
        with self.client.cursor() as cursor:  # pragma: no cover - live postgres path
            cursor.execute(
                f"""
                INSERT INTO {self.schema}.shared_state_records(record_type, record_id, scope_key, created_at, payload_json)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (record_type, record_id) DO UPDATE SET
                    scope_key = EXCLUDED.scope_key,
                    created_at = EXCLUDED.created_at,
                    payload_json = EXCLUDED.payload_json
                """,
                (record_type, record_id, scope_key, str(created_at), json.dumps(payload, ensure_ascii=True, sort_keys=True)),
            )
        self.client.commit()

    def load_record(self, record_type: str, record_id: str) -> dict[str, object] | None:
        if self.client is None:
            return None
        if hasattr(self.client, "load_record"):
            return self.client.load_record(record_type=record_type, record_id=record_id)
        self._ensure_schema()
        with self.client.cursor() as cursor:  # pragma: no cover - live postgres path
            cursor.execute(
                f"SELECT record_type, record_id, scope_key, payload_json, created_at FROM {self.schema}.shared_state_records WHERE record_type = %s AND record_id = %s",
                (record_type, record_id),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return {
            "record_type": row[0],
            "record_id": row[1],
            "scope_key": row[2],
            "payload": row[3] if isinstance(row[3], dict) else json.loads(str(row[3])),
            "created_at": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
        }

    def list_records(self, record_type: str, *, scope_key: str | None = None) -> list[dict[str, object]]:
        if self.client is None:
            return []
        if hasattr(self.client, "list_records"):
            return self.client.list_records(record_type=record_type, scope_key=scope_key)
        self._ensure_schema()
        query = f"SELECT record_type, record_id, scope_key, payload_json, created_at FROM {self.schema}.shared_state_records WHERE record_type = %s"
        params: list[object] = [record_type]
        if scope_key is not None:
            query += " AND scope_key = %s"
            params.append(scope_key)
        query += " ORDER BY created_at DESC"
        with self.client.cursor() as cursor:  # pragma: no cover - live postgres path
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
        return [
            {
                "record_type": row[0],
                "record_id": row[1],
                "scope_key": row[2],
                "payload": row[3] if isinstance(row[3], dict) else json.loads(str(row[3])),
                "created_at": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
            }
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        if self.client is None or hasattr(self.client, "upsert_record"):
            return
        with self.client.cursor() as cursor:  # pragma: no cover - live postgres path
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.schema}.shared_state_records (
                    record_type TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    payload_json JSONB NOT NULL,
                    PRIMARY KEY (record_type, record_id)
                )
                """
            )
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_shared_state_scope ON {self.schema}.shared_state_records(record_type, scope_key, created_at)"
            )
        self.client.commit()
