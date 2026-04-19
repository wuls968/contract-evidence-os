from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from contract_evidence_os.api.asgi import create_console_app
from contract_evidence_os.base import utc_now
from contract_evidence_os.runtime.providers import ProviderUsageRecord
from contract_evidence_os.runtime.service import RuntimeService


def _build_runtime(tmp_path: Path) -> tuple[Path, RuntimeService, str]:
    attachment = tmp_path / "brief.txt"
    attachment.write_text(
        "Build a browser-first UX console for the operator while keeping the governed API intact.\n",
        encoding="utf-8",
    )
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    result = service.run_task(
        goal="Summarize the operator console requirements from the attached brief.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not erase audit lineage."],
    )
    service.repository.save_provider_usage_record(
        ProviderUsageRecord(
            version="1.0",
            usage_id="usage-console-1",
            task_id=result.task_id,
            plan_node_id="",
            correlation_id="corr-console-1",
            role="planner",
            provider_name="openai-primary",
            model_name="gpt-4.1-mini",
            profile="quality",
            request_summary="summarize requirements",
            response_summary="console summary",
            input_tokens=120,
            output_tokens=80,
            total_tokens=200,
            estimated_cost=0.0042,
            latency_ms=210.0,
            retry_count=0,
            fallback_used=False,
            status="success",
            created_at=utc_now() - timedelta(minutes=10),
        )
    )
    return root, service, result.task_id


def test_console_setup_bootstrap_login_and_dashboard(tmp_path: Path) -> None:
    root, _, task_id = _build_runtime(tmp_path)
    config_path = root / "config.local.json"
    env_path = root / ".env.local"
    config_path.write_text("{}", encoding="utf-8")
    env_path.write_text("", encoding="utf-8")

    app = create_console_app(
        storage_root=root,
        token="secret-token",
        config_path=config_path,
        env_path=env_path,
    )
    client = TestClient(app)

    response = client.get("/", follow_redirects=False)
    assert response.status_code in {302, 307}
    assert response.headers["location"].endswith("/setup")

    bootstrap_state = client.get("/ui/bootstrap-state")
    assert bootstrap_state.status_code == 200
    assert bootstrap_state.json()["setup_required"] is True

    bootstrap = client.post(
        "/auth/bootstrap-admin",
        json={
            "email": "admin@example.com",
            "password": "very-secret-password",
            "display_name": "Admin Operator",
            "provider": {
                "kind": "deterministic",
                "base_url": "https://api.openai.com/v1",
                "default_model": "gpt-4.1-mini",
                "api_key": "",
            },
            "service": {"host": "127.0.0.1", "port": 8080},
            "observability_enabled": True,
            "software_control_repo_path": "",
        },
    )
    assert bootstrap.status_code == 200
    assert bootstrap.json()["account"]["email"] == "admin@example.com"

    login = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "very-secret-password"},
    )
    assert login.status_code == 200
    assert login.cookies.get("ceos_session")

    dashboard = client.get("/ui/dashboard-summary")
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["recent_tasks"]
    assert payload["system"]["summary"]["system_mode"] in {"normal", "degraded"}
    assert payload["usage"]["totals"]["total_tokens"] >= 200
    assert any(item["task_id"] == task_id for item in payload["recent_tasks"])


def test_console_usage_summary_and_task_cockpit(tmp_path: Path) -> None:
    root, _, task_id = _build_runtime(tmp_path)
    config_path = root / "config.local.json"
    env_path = root / ".env.local"
    config_path.write_text("{}", encoding="utf-8")
    env_path.write_text("", encoding="utf-8")

    app = create_console_app(
        storage_root=root,
        token="secret-token",
        config_path=config_path,
        env_path=env_path,
    )
    client = TestClient(app)
    client.post(
        "/auth/bootstrap-admin",
        json={
            "email": "admin@example.com",
            "password": "very-secret-password",
            "display_name": "Admin Operator",
            "provider": {"kind": "deterministic", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4.1-mini", "api_key": ""},
            "service": {"host": "127.0.0.1", "port": 8080},
            "observability_enabled": True,
            "software_control_repo_path": "",
        },
    )
    client.post("/auth/login", json={"email": "admin@example.com", "password": "very-secret-password"})

    usage = client.get("/usage/summary?window=24h")
    assert usage.status_code == 200
    usage_payload = usage.json()
    assert usage_payload["totals"]["total_tokens"] >= 200
    assert usage_payload["providers"][0]["provider_name"] == "openai-primary"

    cockpit = client.get(f"/ui/tasks/{task_id}")
    assert cockpit.status_code == 200
    cockpit_payload = cockpit.json()
    assert cockpit_payload["task"]["task_id"] == task_id
    assert cockpit_payload["usage"]["total_tokens"] >= 200
    assert "memory" in cockpit_payload
    assert "approvals" in cockpit_payload


def test_console_preserves_v1_operator_contract(tmp_path: Path) -> None:
    root, _, task_id = _build_runtime(tmp_path)
    app = create_console_app(
        storage_root=root,
        token="secret-token",
        config_path=root / "config.local.json",
        env_path=root / ".env.local",
    )
    client = TestClient(app)

    response = client.get(
        "/v1/service/api-contract",
        headers={
            "Authorization": "Bearer secret-token",
            "X-Request-Id": "req-contract",
            "X-Request-Nonce": "nonce-contract",
            "X-Idempotency-Key": "idem-contract",
        },
    )
    assert response.status_code == 200
    assert response.json()["version"] == "v1"

    kernel = client.get(
        f"/v1/tasks/{task_id}/memory/kernel",
        headers={
            "Authorization": "Bearer secret-token",
            "X-Request-Id": "req-kernel",
            "X-Request-Nonce": "nonce-kernel",
            "X-Idempotency-Key": "idem-kernel",
        },
    )
    assert kernel.status_code == 200
    assert kernel.json()["task_id"] == task_id


def test_console_event_stream_emits_usage_and_health_updates(tmp_path: Path) -> None:
    root, _, _ = _build_runtime(tmp_path)
    config_path = root / "config.local.json"
    env_path = root / ".env.local"
    config_path.write_text("{}", encoding="utf-8")
    env_path.write_text("", encoding="utf-8")

    app = create_console_app(
        storage_root=root,
        token="secret-token",
        config_path=config_path,
        env_path=env_path,
    )
    client = TestClient(app)
    client.post(
        "/auth/bootstrap-admin",
        json={
            "email": "admin@example.com",
            "password": "very-secret-password",
            "display_name": "Admin Operator",
            "provider": {"kind": "deterministic", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4.1-mini", "api_key": ""},
            "service": {"host": "127.0.0.1", "port": 8080},
            "observability_enabled": True,
            "software_control_repo_path": "",
        },
    )
    client.post("/auth/login", json={"email": "admin@example.com", "password": "very-secret-password"})

    with client.stream("GET", "/events/stream") as response:
        lines = [line for line in response.iter_lines() if line][:6]
    joined = "\n".join(lines)
    assert "event: dashboard" in joined
    assert "event: usage" in joined


def test_console_exposes_trusted_runtime_views_and_collaboration_state(tmp_path: Path) -> None:
    root, _, task_id = _build_runtime(tmp_path)
    config_path = root / "config.local.json"
    env_path = root / ".env.local"
    config_path.write_text("{}", encoding="utf-8")
    env_path.write_text("", encoding="utf-8")

    app = create_console_app(
        storage_root=root,
        token="secret-token",
        config_path=config_path,
        env_path=env_path,
    )
    client = TestClient(app)
    client.post(
        "/auth/bootstrap-admin",
        json={
            "email": "admin@example.com",
            "password": "very-secret-password",
            "display_name": "Admin Operator",
            "provider": {"kind": "deterministic", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4.1-mini", "api_key": ""},
            "service": {"host": "127.0.0.1", "port": 8080},
            "observability_enabled": True,
            "software_control_repo_path": "",
        },
    )
    client.post("/auth/login", json={"email": "admin@example.com", "password": "very-secret-password"})

    timeline = client.get(f"/ui/tasks/{task_id}/timeline")
    assert timeline.status_code == 200
    timeline_payload = timeline.json()
    assert timeline_payload["task_id"] == task_id
    assert timeline_payload["events"]

    evidence_trace = client.get(f"/ui/tasks/{task_id}/evidence-trace")
    assert evidence_trace.status_code == 200
    trace_payload = evidence_trace.json()
    assert trace_payload["task_id"] == task_id
    assert trace_payload["sources"]
    assert trace_payload["spans"]

    audit = client.get("/ui/audit/overview")
    assert audit.status_code == 200
    audit_payload = audit.json()
    assert audit_payload["summary"]["total_events"] > 0
    assert audit_payload["trend"]["points"]

    playbooks = client.get("/ui/playbooks/overview")
    assert playbooks.status_code == 200
    assert any(item["task_id"] == task_id for item in playbooks.json()["items"])

    benchmarks = client.get("/ui/benchmarks/overview")
    assert benchmarks.status_code == 200
    assert "summary" in benchmarks.json()

    collaboration = client.get("/ui/collaboration/overview")
    assert collaboration.status_code == 200
    collaboration_payload = collaboration.json()
    assert collaboration_payload["users"]
    assert collaboration_payload["sessions"]
    assert any(item["task_id"] == task_id for item in collaboration_payload["task_bindings"])

    mcp = client.get("/ui/mcp/overview")
    assert mcp.status_code == 200
    mcp_payload = mcp.json()
    assert mcp_payload["server_surface"]["tools"]
    assert mcp_payload["schema_registry"]["items"]


def test_console_can_manage_users_invitations_and_mcp_registry(tmp_path: Path) -> None:
    root, _, task_id = _build_runtime(tmp_path)
    config_path = root / "config.local.json"
    env_path = root / ".env.local"
    config_path.write_text("{}", encoding="utf-8")
    env_path.write_text("", encoding="utf-8")

    app = create_console_app(
        storage_root=root,
        token="secret-token",
        config_path=config_path,
        env_path=env_path,
    )
    client = TestClient(app)
    client.post(
        "/auth/bootstrap-admin",
        json={
            "email": "admin@example.com",
            "password": "very-secret-password",
            "display_name": "Admin Operator",
            "provider": {"kind": "deterministic", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4.1-mini", "api_key": ""},
            "service": {"host": "127.0.0.1", "port": 8080},
            "observability_enabled": True,
            "software_control_repo_path": "",
        },
    )
    client.post("/auth/login", json={"email": "admin@example.com", "password": "very-secret-password"})

    created_user = client.post(
        "/auth/users",
        json={
            "email": "reviewer@example.com",
            "password": "reviewer-secret-password",
            "display_name": "Evidence Reviewer",
            "role_name": "reviewer",
        },
    )
    assert created_user.status_code == 200
    assert created_user.json()["account"]["email"] == "reviewer@example.com"

    invitation = client.post(
        "/auth/invitations",
        json={"email": "watcher@example.com", "role_name": "viewer", "invited_by": "admin@example.com"},
    )
    assert invitation.status_code == 200
    assert invitation.json()["invitation"]["email"] == "watcher@example.com"

    server = client.post(
        "/ui/mcp/servers",
        json={
            "display_name": "Contracts MCP",
            "transport": "stdio",
            "endpoint": "python -m contracts_mcp",
            "direction": "client",
        },
    )
    assert server.status_code == 200
    server_payload = server.json()
    assert server_payload["server"]["display_name"] == "Contracts MCP"

    tool = client.post(
        f"/ui/mcp/servers/{server_payload['server']['server_id']}/tools",
        json={
            "tool_name": "search_contracts",
            "display_name": "Search Contracts",
            "description": "Search indexed contract clauses.",
            "permission_mode": "read-only",
        },
    )
    assert tool.status_code == 200
    tool_payload = tool.json()
    assert tool_payload["tool"]["tool_name"] == "search_contracts"

    invocation = client.post(
        f"/ui/mcp/servers/{server_payload['server']['server_id']}/invoke",
        json={
            "task_id": task_id,
            "tool_name": "search_contracts",
            "actor": "admin@example.com",
            "arguments": {"query": "termination for convenience"},
        },
    )
    assert invocation.status_code == 200
    invocation_payload = invocation.json()
    assert invocation_payload["invocation"]["tool_name"] == "search_contracts"
    assert invocation_payload["permission"]["decision"] in {"allowed", "approval_required"}
