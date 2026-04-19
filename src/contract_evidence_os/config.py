"""Layered runtime configuration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _default_provider_config() -> dict[str, Any]:
    return {
        "kind": "deterministic",
        "api_key_env": "CEOS_API_KEY",
        "base_url_env": "CEOS_API_BASE_URL",
        "default_model": "gpt-4.1-mini",
        "base_url": "https://api.openai.com/v1",
        "anthropic_version": "2023-06-01",
        "api_key_present": False,
        "resolved_api_key": "",
        "resolved_base_url": "https://api.openai.com/v1",
    }


def _provider_default_base_url(kind: str) -> str:
    if kind == "anthropic":
        return "https://api.anthropic.com/v1"
    return "https://api.openai.com/v1"


def _normalize_provider_settings(settings: dict[str, Any] | None) -> dict[str, Any]:
    provider = {**_default_provider_config(), **(settings or {})}
    kind = str(provider.get("kind", "deterministic")).strip() or "deterministic"
    provider["kind"] = kind
    provider["base_url"] = str(provider.get("base_url") or _provider_default_base_url(kind))
    provider["resolved_base_url"] = str(provider.get("resolved_base_url") or provider["base_url"])
    provider["api_key_env"] = str(provider.get("api_key_env") or "CEOS_API_KEY")
    provider["base_url_env"] = str(provider.get("base_url_env") or "CEOS_API_BASE_URL")
    provider["default_model"] = str(provider.get("default_model") or ("claude-sonnet-4-20250514" if kind == "anthropic" else "gpt-4.1-mini"))
    provider["anthropic_version"] = str(provider.get("anthropic_version") or "2023-06-01")
    provider["resolved_api_key"] = str(provider.get("resolved_api_key") or "")
    provider["api_key_present"] = bool(provider.get("api_key_present") or provider["resolved_api_key"])
    return provider


@dataclass
class RuntimeConfig:
    """Minimal layered config for operators and local development."""

    storage_root: str = "./runtime"
    profile: str = "default"
    provider_profiles: dict[str, str] = field(default_factory=lambda: {"planner": "quality", "builder": "quality", "critic": "quality", "verifier": "quality"})
    tool_matrix: dict[str, bool] = field(default_factory=lambda: {"file_retrieval": True, "web_intelligence": True, "computer_use": False, "software_control": True})
    operator_profile: dict[str, str] = field(default_factory=lambda: {"default_role": "Strategist"})
    secrets_env: dict[str, str] = field(default_factory=lambda: {"api_key_env": "CEOS_API_KEY"})
    provider: dict[str, Any] = field(default_factory=_default_provider_config)
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
        payload["provider"] = _normalize_provider_settings(payload.get("provider"))
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
        provider = _normalize_provider_settings(payload.get("provider"))
        env_provider_kind = os.environ.get("CEOS_PROVIDER_KIND")
        if env_provider_kind:
            provider["kind"] = env_provider_kind
            provider["base_url"] = _provider_default_base_url(provider["kind"])
        provider["api_key_env"] = str(provider.get("api_key_env") or "CEOS_API_KEY")
        provider["base_url_env"] = str(provider.get("base_url_env") or "CEOS_API_BASE_URL")
        env_api_key = os.environ.get(provider["api_key_env"], "")
        env_base_url = os.environ.get(provider["base_url_env"], "")
        if env_api_key:
            provider["resolved_api_key"] = env_api_key
            provider["api_key_present"] = True
        else:
            provider["resolved_api_key"] = ""
            provider["api_key_present"] = False
        if env_base_url:
            provider["resolved_base_url"] = env_base_url
        else:
            provider["resolved_base_url"] = str(provider.get("base_url") or _provider_default_base_url(provider["kind"]))
        if os.environ.get("CEOS_DEFAULT_MODEL"):
            provider["default_model"] = os.environ["CEOS_DEFAULT_MODEL"]
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
            provider = _normalize_provider_settings(payload.get("provider"))
            env_api_key = os.environ.get(str(provider.get("api_key_env", "CEOS_API_KEY")), "")
            env_base_url = os.environ.get(str(provider.get("base_url_env", "CEOS_API_BASE_URL")), "")
            provider["resolved_api_key"] = env_api_key
            provider["api_key_present"] = bool(env_api_key)
            provider["resolved_base_url"] = env_base_url or str(provider.get("base_url") or _provider_default_base_url(str(provider.get("kind", "deterministic"))))
        payload["provider"] = provider
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
        if str(self.provider.get("kind", "deterministic")) not in {"deterministic", "openai-compatible", "anthropic"}:
            raise ValueError("provider.kind must be deterministic, openai-compatible, or anthropic")
        if int(self.observability.get("snapshot_interval_seconds", 60)) <= 0:
            raise ValueError("observability.snapshot_interval_seconds must be positive")
        if int(self.maintenance.get("heartbeat_seconds", 30)) <= 0:
            raise ValueError("maintenance.heartbeat_seconds must be positive")
        if int(self.maintenance.get("lease_seconds", 300)) <= 0:
            raise ValueError("maintenance.lease_seconds must be positive")

    def runtime_kwargs(self) -> dict[str, Any]:
        return {
            "queue_backend_kind": str(self.external_backend.get("kind", "sqlite")),
            "coordination_backend_kind": str(self.external_backend.get("kind", "sqlite")),
            "external_backend_url": str(self.external_backend.get("url", "")) or None,
            "external_backend_namespace": str(self.external_backend.get("namespace", "ceos")),
            "shared_state_backend_kind": str(self.shared_state_backend.get("kind", "sqlite")),
            "shared_state_backend_url": str(self.shared_state_backend.get("url", "")) or None,
            "trust_mode": str(self.trust.get("mode", "standard")),
            "cli_anything_repo_path": str(self.software_control.get("repo_path", "")) or None,
            "provider_settings": dict(self.provider),
        }

    def audit_summary(self) -> dict[str, Any]:
        token_env = str(self.service.get("token_env", ""))
        provider = dict(self.provider)
        provider.pop("resolved_api_key", None)
        return {
            "storage_root": self.storage_root,
            "profile": self.profile,
            "provider_profiles": self.provider_profiles,
            "tool_matrix": self.tool_matrix,
            "provider": provider,
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
