"""Shared repository substore behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from contract_evidence_os.storage.repository import SQLiteRepository


class SQLiteSubstore:
    """Base class for decomposed repository substores."""

    def __init__(self, owner: "SQLiteRepository") -> None:
        self.owner = owner

    def __getattr__(self, name: str) -> Any:
        return getattr(self.owner, name)

    @property
    def db_path(self) -> Any:
        return self.owner.db_path

    def dumps(self, payload: dict[str, Any]) -> str:
        return self.owner.dumps(payload)

    def loads(self, payload_json: str) -> dict[str, Any]:
        return self.owner.loads(payload_json)

    def _insert_or_replace(self, table: str, values: dict[str, Any]) -> None:
        self.owner._insert_or_replace(table, values)  # noqa: SLF001

    def _save_runtime_state_record(
        self,
        record_type: str,
        record_id: str,
        scope_key: str | None,
        created_at: str,
        model: Any,
    ) -> None:
        self.owner._save_runtime_state_record(record_type, record_id, scope_key, created_at, model)  # noqa: SLF001

    def _load_runtime_state_record(self, record_type: str, record_id: str, model_cls: type[Any]) -> Any | None:
        return self.owner._load_runtime_state_record(record_type, record_id, model_cls)  # noqa: SLF001

    def _list_runtime_state_records(
        self,
        record_type: str,
        model_cls: type[Any],
        scope_key: str | None = None,
    ) -> list[Any]:
        return self.owner._list_runtime_state_records(record_type, model_cls, scope_key=scope_key)  # noqa: SLF001
