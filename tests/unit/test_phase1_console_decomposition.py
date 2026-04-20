from __future__ import annotations

from pathlib import Path

from contract_evidence_os.api.operator import OperatorAPI
from contract_evidence_os.console.auth import ConsoleAuthService
from contract_evidence_os.console.config_service import ConsoleConfigService
from contract_evidence_os.console.projections import ConsoleProjectionService
from contract_evidence_os.console.service import ConsoleService
from contract_evidence_os.console.usage import ConsoleUsageService
from contract_evidence_os.runtime.providers import ProviderUsageRecord
from contract_evidence_os.runtime.service import RuntimeService
from contract_evidence_os.storage.console_facade import ConsoleRepositoryFacade
from contract_evidence_os.base import utc_now


def _build_console(tmp_path: Path) -> ConsoleService:
    attachment = tmp_path / "brief.txt"
    attachment.write_text("Extract trusted runtime signals for the UX console.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    runtime = RuntimeService(storage_root=root, routing_strategy="quality")
    result = runtime.run_task(
        goal="Summarize trusted runtime posture for the operator console.",
        attachments=[str(attachment)],
        preferences={},
        prohibitions=[],
    )
    runtime.repository.save_provider_usage_record(
        ProviderUsageRecord(
            version="1.0",
            usage_id="usage-phase1-console",
            task_id=result.task_id,
            plan_node_id="",
            correlation_id="corr-phase1-console",
            role="planner",
            provider_name="openai-primary",
            model_name="gpt-4.1-mini",
            profile="quality",
            request_summary="summarize trusted runtime",
            response_summary="trusted runtime summary",
            input_tokens=80,
            output_tokens=40,
            total_tokens=120,
            estimated_cost=0.002,
            latency_ms=120.0,
            retry_count=0,
            fallback_used=False,
            status="success",
            created_at=utc_now(),
        )
    )
    config_path = root / "config.local.json"
    env_path = root / ".env.local"
    config_path.write_text("{}", encoding="utf-8")
    env_path.write_text("", encoding="utf-8")
    api = OperatorAPI(storage_root=root)
    return ConsoleService(api=api, config_path=config_path, env_path=env_path)


def test_console_service_exposes_decomposed_subservices_and_store(tmp_path: Path) -> None:
    console = _build_console(tmp_path)

    assert isinstance(console.store, ConsoleRepositoryFacade)
    assert isinstance(console.auth_service, ConsoleAuthService)
    assert isinstance(console.config_service, ConsoleConfigService)
    assert isinstance(console.projection_service, ConsoleProjectionService)
    assert isinstance(console.usage_service, ConsoleUsageService)


def test_console_service_delegates_public_methods_to_subservices(tmp_path: Path) -> None:
    console = _build_console(tmp_path)

    bootstrap = console.bootstrap_state()
    assert bootstrap["setup_required"] is True
    assert console.auth_service.bootstrap_state()["setup_required"] is True

    effective = console.config_effective()
    assert effective["paths"]["config_path"].endswith("config.local.json")
    assert console.config_service.config_effective()["paths"]["config_path"].endswith("config.local.json")

    usage = console.usage_summary()
    assert usage["totals"]["total_tokens"] >= 120
    assert console.usage_service.usage_summary()["totals"]["total_tokens"] >= 120
