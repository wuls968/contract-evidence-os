"""Configuration and setup handling for the browser console."""

from __future__ import annotations

import secrets
import urllib.error
import urllib.request
from typing import Any

from contract_evidence_os.console._base import ConsoleSubservice


class ConsoleConfigService(ConsoleSubservice):
    """Own installer/setup-aligned runtime configuration behavior."""

    def apply_setup_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        config_payload = self._load_config_payload()
        provider_payload = dict(payload.get("provider", {}))
        provider_kind = str(provider_payload.get("kind", "deterministic"))
        provider_api_key = str(provider_payload.get("api_key", ""))
        provider_base_url = str(provider_payload.get("base_url", "")) or config_payload.get("provider", {}).get("base_url", "https://api.openai.com/v1")
        config_payload["service"] = {
            **dict(config_payload.get("service", {})),
            "host": str(dict(payload.get("service", {})).get("host", "127.0.0.1")),
            "port": int(dict(payload.get("service", {})).get("port", 8080)),
            "token_env": "CEOS_OPERATOR_TOKEN",
        }
        config_payload["provider"] = {
            **dict(config_payload.get("provider", {})),
            "kind": provider_kind,
            "base_url": provider_base_url,
            "default_model": str(provider_payload.get("default_model", config_payload.get("provider", {}).get("default_model", "gpt-4.1-mini"))),
            "api_key_env": "CEOS_API_KEY",
            "base_url_env": "CEOS_API_BASE_URL",
        }
        config_payload["observability"] = {
            **dict(config_payload.get("observability", {})),
            "enabled": bool(payload.get("observability_enabled", True)),
        }
        config_payload["software_control"] = {
            **dict(config_payload.get("software_control", {})),
            "repo_path": str(payload.get("software_control_repo_path", "")),
        }
        self._write_config_payload(config_payload)
        env_updates = {
            "CEOS_OPERATOR_TOKEN": self._env_values().get("CEOS_OPERATOR_TOKEN", secrets.token_urlsafe(24)),
            "CEOS_PROVIDER_KIND": provider_kind,
            "CEOS_API_BASE_URL": provider_base_url,
            "CEOS_DEFAULT_MODEL": str(config_payload["provider"]["default_model"]),
        }
        if provider_api_key:
            env_updates["CEOS_API_KEY"] = provider_api_key
        self._write_env_values(env_updates)
        return {"config_path": str(self.config_path), "env_path": str(self.env_path)}

    def config_effective(self) -> dict[str, Any]:
        config = self._runtime_config()
        env_values = self._env_values()
        oidc_providers = self.list_oidc_provider_configs()
        return {
            "effective": config.audit_summary(),
            "paths": {"config_path": str(self.config_path), "env_path": str(self.env_path)},
            "env_overrides": {
                "operator_token_present": bool(env_values.get("CEOS_OPERATOR_TOKEN")),
                "api_key_present": bool(env_values.get("CEOS_API_KEY")),
                "configured_env_keys": sorted(env_values),
            },
            "oidc_providers": [
                {
                    **item.to_dict(),
                    "client_secret_present": bool(env_values.get(item.client_secret_env)),
                }
                for item in oidc_providers
            ],
        }

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        config_payload = self._load_config_payload()
        if "service" in payload:
            config_payload["service"] = {**dict(config_payload.get("service", {})), **dict(payload["service"])}
        if "provider" in payload:
            provider_payload = {**dict(config_payload.get("provider", {})), **dict(payload["provider"])}
            secret_api_key = str(provider_payload.pop("api_key", ""))
            config_payload["provider"] = provider_payload
            if secret_api_key:
                self._write_env_values({"CEOS_API_KEY": secret_api_key})
        if "observability" in payload:
            config_payload["observability"] = {**dict(config_payload.get("observability", {})), **dict(payload["observability"])}
        if "software_control" in payload:
            config_payload["software_control"] = {**dict(config_payload.get("software_control", {})), **dict(payload["software_control"])}
        self._write_config_payload(config_payload)
        return self.config_effective()

    def _new_config_validation_result(self, *, validation_kind: str, status: str, messages: list[str], details: dict[str, Any]) -> Any:
        from uuid import uuid4

        from contract_evidence_os.console.models import ConfigValidationResult

        result = ConfigValidationResult(
            version="1.0",
            result_id=f"config-check-{uuid4().hex[:10]}",
            validation_kind=validation_kind,
            status=status,
            messages=messages,
            details=details,
        )
        self._save_model("console_config_validation", result.result_id, validation_kind, result.created_at.isoformat(), result)
        return result

    def test_provider_connection(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        provider = {**self._runtime_config().provider, **(payload or {})}
        kind = str(provider.get("kind", "deterministic"))
        messages: list[str] = []
        status = "ok"
        details: dict[str, Any] = {
            "kind": kind,
            "base_url": provider.get("resolved_base_url", provider.get("base_url", "")),
            "default_model": provider.get("default_model", ""),
        }
        if kind == "deterministic":
            messages.append("Deterministic provider is active; live API connectivity is not required.")
        else:
            api_key = str(provider.get("api_key") or provider.get("resolved_api_key") or self._env_values().get("CEOS_API_KEY", ""))
            if not api_key:
                status = "invalid"
                messages.append("Missing API key for live provider.")
            base_url = str(provider.get("base_url") or provider.get("resolved_base_url") or "")
            if not base_url:
                status = "invalid"
                messages.append("Missing provider base URL.")
            elif status == "ok":
                request = urllib.request.Request(
                    base_url,
                    headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
                    method="GET",
                )
                try:
                    with urllib.request.urlopen(request, timeout=5) as response:
                        details["http_status"] = getattr(response, "status", 200)
                    messages.append("Provider endpoint responded successfully.")
                except urllib.error.HTTPError as exc:
                    details["http_status"] = exc.code
                    messages.append(f"Provider endpoint responded with HTTP {exc.code}; network path is reachable.")
                except urllib.error.URLError as exc:
                    status = "error"
                    messages.append(f"Provider connectivity failed: {exc.reason}")
        result = self._new_config_validation_result(
            validation_kind="provider",
            status=status,
            messages=messages or ["Provider settings look valid."],
            details=details,
        )
        return result.to_dict()
