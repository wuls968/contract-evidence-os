"""Shared console subservice behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from contract_evidence_os.console.service import ConsoleService


class ConsoleSubservice:
    """Base class for decomposed console subservices."""

    def __init__(self, owner: "ConsoleService") -> None:
        self.owner = owner

    def __getattr__(self, name: str) -> Any:
        return getattr(self.owner, name)

    @property
    def api(self) -> Any:
        return self.owner.api

    @property
    def repository(self) -> Any:
        return self.owner.repository

    @property
    def store(self) -> Any:
        return self.owner.store

    @property
    def config_path(self) -> Any:
        return self.owner.config_path

    @property
    def env_path(self) -> Any:
        return self.owner.env_path

    def _save_model(self, record_type: str, record_id: str, scope_key: str | None, created_at: str, model: Any) -> None:
        self.store.save_model(record_type, record_id, scope_key, created_at, model)

    def _load_model(self, record_type: str, record_id: str, model_cls: type[Any]) -> Any | None:
        return self.store.load_model(record_type, record_id, model_cls)

    def _list_models(self, record_type: str, model_cls: type[Any], scope_key: str | None = None) -> list[Any]:
        return self.store.list_models(record_type, model_cls, scope_key=scope_key)
