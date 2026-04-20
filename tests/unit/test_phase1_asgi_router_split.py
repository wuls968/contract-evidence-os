from __future__ import annotations

from pathlib import Path

from fastapi.routing import APIRoute

from contract_evidence_os.api.asgi import create_console_app


def test_console_app_registers_route_families_with_router_tags(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir(parents=True, exist_ok=True)
    app = create_console_app(
        storage_root=root,
        token="secret-token",
        config_path=root / "config.local.json",
        env_path=root / ".env.local",
    )

    tags = {
        tag
        for route in app.routes
        if isinstance(route, APIRoute)
        for tag in route.tags
    }

    assert {
        "console-spa",
        "console-auth",
        "console-ui",
        "console-config",
        "console-usage",
        "console-events",
        "operator-v1",
    } <= tags
