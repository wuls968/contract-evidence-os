import json
from pathlib import Path

import pytest

from contract_evidence_os.config import RuntimeConfig
from contract_evidence_os.runtime.providers import DeterministicLLMProvider, OpenAIResponsesProvider
from contract_evidence_os.runtime.service import RuntimeService


def test_runtime_config_loads_provider_settings_from_file_and_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "config.local.json"
    config_path.write_text(
        json.dumps(
            {
                "storage_root": str(tmp_path / "runtime"),
                "provider": {
                    "kind": "openai-compatible",
                    "api_key_env": "CEOS_API_KEY",
                    "base_url_env": "CEOS_API_BASE_URL",
                    "default_model": "gpt-4.1-mini",
                    "base_url": "https://example.invalid/v1",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CEOS_API_KEY", "test-key")
    monkeypatch.setenv("CEOS_API_BASE_URL", "https://api.example.test/v1")

    config = RuntimeConfig.load(config_path=config_path)

    assert config.provider["kind"] == "openai-compatible"
    assert config.provider["api_key_env"] == "CEOS_API_KEY"
    assert config.provider["api_key_present"] is True
    assert config.provider["resolved_api_key"] == "test-key"
    assert config.provider["resolved_base_url"] == "https://api.example.test/v1"
    assert config.audit_summary()["provider"]["api_key_present"] is True


def test_runtime_service_uses_live_provider_when_provider_config_is_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CEOS_API_KEY", "test-key")
    monkeypatch.setenv("CEOS_API_BASE_URL", "https://api.example.test/v1")
    config = RuntimeConfig.load(
        overrides={
            "storage_root": str(tmp_path / "runtime"),
            "provider": {
                "kind": "openai-compatible",
                "api_key_env": "CEOS_API_KEY",
                "base_url_env": "CEOS_API_BASE_URL",
                "default_model": "gpt-4.1-mini",
            },
        }
    )

    runtime = RuntimeService(storage_root=Path(config.storage_root), provider_settings=config.provider)

    assert isinstance(runtime.provider_manager.providers["primary"], OpenAIResponsesProvider)
    assert runtime.provider_manager.providers["primary"].api_key == "test-key"
    assert runtime.provider_manager.providers["primary"].base_url == "https://api.example.test/v1/responses"
    assert isinstance(runtime.provider_manager.providers["fallback"], DeterministicLLMProvider)


def test_runtime_service_keeps_deterministic_provider_when_api_key_is_missing(tmp_path: Path) -> None:
    config = RuntimeConfig.load(
        overrides={
            "storage_root": str(tmp_path / "runtime"),
            "provider": {
                "kind": "openai-compatible",
                "api_key_env": "CEOS_API_KEY",
                "base_url_env": "CEOS_API_BASE_URL",
                "default_model": "gpt-4.1-mini",
            },
        }
    )

    runtime = RuntimeService(storage_root=Path(config.storage_root), provider_settings=config.provider)

    assert isinstance(runtime.provider_manager.providers["primary"], DeterministicLLMProvider)
    assert isinstance(runtime.provider_manager.providers["fallback"], DeterministicLLMProvider)
