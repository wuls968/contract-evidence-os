"""Layered runtime configuration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RuntimeConfig:
    """Minimal layered config for operators and local development."""

    storage_root: str = "./runtime"
    profile: str = "default"
    provider_profiles: dict[str, str] = field(default_factory=lambda: {"planner": "quality", "builder": "quality", "critic": "quality", "verifier": "quality"})
    tool_matrix: dict[str, bool] = field(default_factory=lambda: {"file_retrieval": True, "web_intelligence": True, "computer_use": False, "software_control": True})
    operator_profile: dict[str, str] = field(default_factory=lambda: {"default_role": "Strategist"})
    secrets_env: dict[str, str] = field(default_factory=lambda: {"api_key_env": "CEOS_API_KEY"})
    service: dict[str, Any] = field(default_factory=lambda: {"host": "127.0.0.1", "port": 8080, "token_env": "CEOS_OPERATOR_TOKEN"})
    external_backend: dict[str, Any] = field(default_factory=lambda: {"kind": "sqlite", "url": "", "namespace": "ceos"})
    shared_state_backend: dict[str, Any] = field(default_factory=lambda: {"kind": "sqlite", "url": "", "schema": "public"})
    software_control: dict[str, Any] = field(default_factory=lambda: {"enabled": True, "source_kind": "cli-anything", "repo_path": "", "allow_auto_task": True, "macro_enabled": True, "macro_default_approval": True})
    observability: dict[str, Any] = field(default_factory=lambda: {"enabled": True, "snapshot_interval_seconds": 60, "prometheus_enabled": True, "alerts_enabled": True, "history_window_hours": 24})
    maintenance: dict[str, Any] = field(default_factory=lambda: {"daemon_enabled": True, "poll_interval_seconds": 30, "heartbeat_seconds": 30, "lease_seconds": 300})
    roles: dict[str, bool] = field(default_factory=lambda: {"control_plane": True, "dispatcher": True, "worker": True, "maintenance": True})
    auth: dict[str, Any] = field(default_factory=lambda: {"require_nonce_for_sensitive_actions": True, "bootstrap_scopes": ["viewer", "operator", "approver", "policy-admin", "runtime-admin", "evaluator", "worker-service"], "admin_allowlist": ["127.0.0.1", "::1"], "max_request_bytes": 65536})
    trust: dict[str, Any] = field(default_factory=lambda: {"mode": "standard", "allow_service_hmac": True, "request_timeout_seconds": 5})

    @classmethod
    def load(cls, config_path: Path | None = None, overrides: dict[str, Any] | None = None) -> "RuntimeConfig":
        payload: dict[str, Any] = cls().__dict__.copy()
        if config_path is not None and config_path.exists():
            payload.update(json.loads(config_path.read_text(encoding="utf-8")))
        env_storage_root = os.environ.get("CEOS_STORAGE_ROOT")
        if env_storage_root:
            payload["storage_root"] = env_storage_root
        if os.environ.get("CEOS_EXTERNAL_BACKEND_KIND"):
            payload["external_backend"] = {
                **dict(payload.get("external_backend", {})),
                "kind": os.environ["CEOS_EXTERNAL_BACKEND_KIND"],
                "url": os.environ.get("CEOS_EXTERNAL_BACKEND_URL", dict(payload.get("external_backend", {})).get("url", "")),
                "namespace": os.environ.get("CEOS_EXTERNAL_BACKEND_NAMESPACE", dict(payload.get("external_backend", {})).get("namespace", "ceos")),
            }
        if os.environ.get("CEOS_SHARED_STATE_BACKEND_KIND"):
            payload["shared_state_backend"] = {
                **dict(payload.get("shared_state_backend", {})),
                "kind": os.environ["CEOS_SHARED_STATE_BACKEND_KIND"],
                "url": os.environ.get("CEOS_SHARED_STATE_BACKEND_URL", dict(payload.get("shared_state_backend", {})).get("url", "")),
                "schema": os.environ.get("CEOS_SHARED_STATE_BACKEND_SCHEMA", dict(payload.get("shared_state_backend", {})).get("schema", "public")),
            }
        if os.environ.get("CEOS_TRUST_MODE"):
            payload["trust"] = {
                **dict(payload.get("trust", {})),
                "mode": os.environ["CEOS_TRUST_MODE"],
            }
        if os.environ.get("CEOS_CLI_ANYTHING_REPO_PATH"):
            payload["software_control"] = {
                **dict(payload.get("software_control", {})),
                "repo_path": os.environ["CEOS_CLI_ANYTHING_REPO_PATH"],
            }
        if os.environ.get("CEOS_OBSERVABILITY_PROMETHEUS_ENABLED"):
            payload["observability"] = {
                **dict(payload.get("observability", {})),
                "prometheus_enabled": os.environ["CEOS_OBSERVABILITY_PROMETHEUS_ENABLED"].lower() in {"1", "true", "yes"},
            }
        if os.environ.get("CEOS_MAINTENANCE_POLL_INTERVAL_SECONDS"):
            payload["maintenance"] = {
                **dict(payload.get("maintenance", {})),
                "poll_interval_seconds": int(os.environ["CEOS_MAINTENANCE_POLL_INTERVAL_SECONDS"]),
            }
        if overrides:
            payload.update(overrides)
        config = cls(**payload)
        config.validate_or_raise()
        return config

    def validate_or_raise(self) -> None:
        storage_root = Path(self.storage_root)
        if not str(storage_root):
            raise ValueError("storage_root must not be empty")
        required_roles = {"control_plane", "dispatcher", "worker", "maintenance"}
        missing_roles = sorted(required_roles.difference(self.roles))
        if missing_roles:
            raise ValueError(f"roles missing required keys: {', '.join(missing_roles)}")
        if "token_env" not in self.service:
            raise ValueError("service.token_env must be configured")
        if not self.auth.get("bootstrap_scopes"):
            raise ValueError("auth.bootstrap_scopes must not be empty")
        if self.external_backend.get("kind", "sqlite") not in {"sqlite", "redis"}:
            raise ValueError("external_backend.kind must be sqlite or redis")
        if self.shared_state_backend.get("kind", "sqlite") not in {"sqlite", "postgres"}:
            raise ValueError("shared_state_backend.kind must be sqlite or postgres")
        if self.trust.get("mode", "standard") not in {"standard", "hmac"}:
            raise ValueError("trust.mode must be standard or hmac")
        if int(self.observability.get("snapshot_interval_seconds", 60)) <= 0:
            raise ValueError("observability.snapshot_interval_seconds must be positive")
        if int(self.maintenance.get("heartbeat_seconds", 30)) <= 0:
            raise ValueError("maintenance.heartbeat_seconds must be positive")
        if int(self.maintenance.get("lease_seconds", 300)) <= 0:
            raise ValueError("maintenance.lease_seconds must be positive")

    def audit_summary(self) -> dict[str, Any]:
        token_env = str(self.service.get("token_env", ""))
        return {
            "storage_root": self.storage_root,
            "profile": self.profile,
            "provider_profiles": self.provider_profiles,
            "tool_matrix": self.tool_matrix,
            "service": {
                "host": self.service.get("host", "127.0.0.1"),
                "port": self.service.get("port", 8080),
                "token_env": token_env,
                "token_present": bool(token_env and os.environ.get(token_env)),
            },
            "roles": self.roles,
            "external_backend": self.external_backend,
            "shared_state_backend": self.shared_state_backend,
            "software_control": self.software_control,
            "observability": self.observability,
            "maintenance": self.maintenance,
            "auth": self.auth,
            "trust": self.trust,
        }
