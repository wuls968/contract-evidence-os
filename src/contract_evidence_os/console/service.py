"""Thin coordinator for the browser-facing UX console."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from pathlib import Path
from typing import Any

from contract_evidence_os.api.operator import OperatorAPI
from contract_evidence_os.config import RuntimeConfig
from contract_evidence_os.console.auth import ConsoleAuthService
from contract_evidence_os.console.common import ROLE_SCOPES, SessionPrincipal
from contract_evidence_os.console.config_service import ConsoleConfigService
from contract_evidence_os.console.projections import ConsoleProjectionService
from contract_evidence_os.console.usage import ConsoleUsageService
from contract_evidence_os.storage.console_facade import ConsoleRepositoryFacade


class ConsoleService:
    """Coordinate browser-console subservices on top of ``OperatorAPI``."""

    def __init__(
        self,
        *,
        api: OperatorAPI,
        config_path: Path,
        env_path: Path,
    ) -> None:
        self.api = api
        self.repository = api.repository
        self.config_path = Path(config_path)
        self.env_path = Path(env_path)
        self.store = ConsoleRepositoryFacade(self.repository)
        self.auth_service = ConsoleAuthService(self)
        self.config_service = ConsoleConfigService(self)
        self.projection_service = ConsoleProjectionService(self)
        self.usage_service = ConsoleUsageService(self)

    def __getattr__(self, name: str) -> Any:
        for attr_name in ("auth_service", "config_service", "projection_service", "usage_service"):
            service = object.__getattribute__(self, attr_name)
            if hasattr(type(service), name):
                return getattr(service, name)
        raise AttributeError(f"{type(self).__name__!s} has no attribute {name!r}")

    def _hash_password(self, password: str, *, salt: str | None = None) -> tuple[str, str]:
        salt_bytes = secrets.token_bytes(16) if salt is None else bytes.fromhex(salt)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt_bytes, n=2**14, r=8, p=1)
        return base64.b64encode(digest).decode("ascii"), salt_bytes.hex()

    def _verify_password(self, password: str, credential: Any) -> bool:
        digest, _ = self._hash_password(password, salt=credential.password_salt)
        return secrets.compare_digest(digest, credential.password_hash)

    def _env_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        if not self.env_path.exists():
            return values
        for raw_line in self.env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        return values

    def _write_env_values(self, updates: dict[str, str]) -> None:
        merged = self._env_values()
        for key, value in updates.items():
            if value == "":
                merged.pop(key, None)
            else:
                merged[key] = value
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{key}={value}" for key, value in sorted(merged.items())]
        self.env_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _load_config_payload(self) -> dict[str, Any]:
        payload = RuntimeConfig().__dict__.copy()
        if self.config_path.exists():
            payload.update(json.loads(self.config_path.read_text(encoding="utf-8")))
        return payload

    def _write_config_payload(self, payload: dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _runtime_config(self) -> RuntimeConfig:
        return RuntimeConfig.load(config_path=self.config_path)


__all__ = ["ConsoleService", "ROLE_SCOPES", "SessionPrincipal"]
