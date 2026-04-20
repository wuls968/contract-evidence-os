"""Console-focused repository facade."""

from __future__ import annotations

from typing import Any

from contract_evidence_os.storage.repository import SQLiteRepository


class ConsoleRepositoryFacade:
    """Wrap runtime-state persistence needed by the browser console."""

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    def save_model(self, record_type: str, record_id: str, scope_key: str | None, created_at: str, model: Any) -> None:
        self.repository._save_runtime_state_record(record_type, record_id, scope_key, created_at, model)  # noqa: SLF001

    def load_model(self, record_type: str, record_id: str, model_cls: type[Any]) -> Any | None:
        return self.repository._load_runtime_state_record(record_type, record_id, model_cls)  # noqa: SLF001

    def list_models(self, record_type: str, model_cls: type[Any], scope_key: str | None = None) -> list[Any]:
        return self.repository._list_runtime_state_records(record_type, model_cls, scope_key=scope_key)  # noqa: SLF001
