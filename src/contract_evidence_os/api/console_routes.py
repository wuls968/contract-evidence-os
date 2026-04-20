"""Router builders for browser-facing console surfaces."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse

from contract_evidence_os.console.service import SessionPrincipal


def build_console_spa_router(
    *,
    controller: Any,
    spa_shell: Callable[[], HTMLResponse],
) -> APIRouter:
    """Build SPA shell and browser entrypoint routes."""

    router = APIRouter(tags=["console-spa"])

    @router.get("/", include_in_schema=False)
    def root(request: Request) -> Response:
        bootstrap = controller.console.bootstrap_state()
        if bootstrap["setup_required"]:
            return RedirectResponse("/setup", status_code=307)
        session_id = request.cookies.get("ceos_session", "")
        principal = controller.console.resolve_session(session_id) if session_id else None
        if principal is None:
            return RedirectResponse("/login", status_code=307)
        return RedirectResponse("/dashboard", status_code=307)

    def serve_shell() -> HTMLResponse:
        return spa_shell()

    for path in (
        "/setup",
        "/login",
        "/dashboard",
        "/memory",
        "/software",
        "/maintenance",
        "/usage",
        "/settings",
        "/doctor",
        "/audit",
        "/benchmarks",
        "/playbooks",
        "/collaboration",
        "/mcp",
    ):
        router.add_api_route(path, serve_shell, methods=["GET"], include_in_schema=False)

    @router.get("/tasks/{task_id}", include_in_schema=False)
    def spa_task(task_id: str) -> HTMLResponse:  # noqa: ARG001
        return spa_shell()

    @router.get("/memory/{task_id}", include_in_schema=False)
    def spa_memory(task_id: str) -> HTMLResponse:  # noqa: ARG001
        return spa_shell()

    return router


def build_console_auth_router(
    *,
    controller: Any,
    current_session: Callable[..., SessionPrincipal],
    host: str,
    port: int,
) -> APIRouter:
    """Build authentication, account, session, and OIDC routes."""

    router = APIRouter(tags=["console-auth"])

    @router.post("/auth/bootstrap-admin")
    async def auth_bootstrap_admin(request: Request) -> JSONResponse:
        payload = await request.json()
        created = controller.console.bootstrap_admin(dict(payload))
        return JSONResponse(created)

    @router.post("/auth/login")
    async def auth_login(request: Request) -> JSONResponse:
        payload = await request.json()
        principal = controller.console.authenticate_local(
            email=str(payload.get("email", "")),
            password=str(payload.get("password", "")),
        )
        response = JSONResponse(
            {
                "account": principal.user.to_dict(),
                "roles": principal.roles,
                "scopes": principal.scopes,
                "session": {
                    "session_id": principal.session.session_id,
                    "expires_at": None if principal.session.expires_at is None else principal.session.expires_at.isoformat(),
                },
            }
        )
        response.set_cookie(
            "ceos_session",
            principal.session.session_id,
            httponly=True,
            samesite="lax",
            max_age=7 * 24 * 60 * 60,
        )
        return response

    @router.post("/auth/logout")
    def auth_logout(request: Request) -> JSONResponse:
        session_id = request.cookies.get("ceos_session", "")
        if session_id:
            controller.console.logout_session(session_id)
        response = JSONResponse({"status": "logged_out"})
        response.delete_cookie("ceos_session")
        return response

    @router.get("/auth/session")
    def auth_session(request: Request) -> dict[str, Any]:
        principal = current_session(request)
        return {
            "account": principal.user.to_dict(),
            "roles": principal.roles,
            "scopes": principal.scopes,
            "session": principal.session.to_dict(),
        }

    @router.get("/auth/users")
    def auth_users(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        return {"items": [item.to_dict() for item in controller.console.list_user_accounts()]}

    @router.post("/auth/users")
    async def auth_users_create(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.create_user_account(
            email=str(payload.get("email", "")),
            password=str(payload.get("password", "")),
            display_name=str(payload.get("display_name", "")),
            role_name=str(payload.get("role_name", "viewer")),
        )

    @router.get("/auth/roles")
    def auth_roles(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        return {"items": [item.to_dict() for item in controller.console.list_user_role_bindings()]}

    @router.get("/auth/sessions")
    def auth_sessions(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        return {"items": [item.to_dict() for item in controller.console.list_browser_sessions()]}

    @router.get("/auth/invitations")
    def auth_invitations(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        return {"items": [item.to_dict() for item in controller.console.list_workspace_invitations()]}

    @router.post("/auth/invitations")
    async def auth_invitations_create(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.create_workspace_invitation(
            email=str(payload.get("email", "")),
            role_name=str(payload.get("role_name", "viewer")),
            invited_by=str(payload.get("invited_by", "runtime-admin")),
        )

    @router.get("/auth/oidc/presets")
    def auth_oidc_presets() -> dict[str, Any]:
        return {"items": controller.console.oidc_presets()}

    @router.get("/auth/oidc/providers")
    def auth_oidc_providers(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        return {"items": [item.to_dict() for item in controller.console.list_oidc_provider_configs()]}

    @router.post("/auth/oidc/providers")
    async def auth_oidc_save_provider(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.save_oidc_provider_config(dict(payload))

    @router.get("/auth/oidc/start/{provider_id}")
    def auth_oidc_start(provider_id: str, request: Request, next_path: str = "/dashboard") -> RedirectResponse:
        host_value = request.headers.get("host", f"{host}:{port}")
        redirect_uri = f"{request.url.scheme}://{host_value}/auth/oidc/callback"
        url = controller.console.start_oidc_login(provider_id, redirect_uri=redirect_uri, next_path=next_path)
        return RedirectResponse(url, status_code=307)

    @router.get("/auth/oidc/callback")
    def auth_oidc_callback(state: str, code: str) -> RedirectResponse:
        principal = controller.console.finish_oidc_login(state_id=state, code=code)
        response = RedirectResponse("/dashboard", status_code=307)
        response.set_cookie(
            "ceos_session",
            principal.session.session_id,
            httponly=True,
            samesite="lax",
            max_age=7 * 24 * 60 * 60,
        )
        return response

    return router


def build_console_ui_router(
    *,
    controller: Any,
    current_session: Callable[..., SessionPrincipal],
) -> APIRouter:
    """Build browser UI read-model and action routes."""

    router = APIRouter(tags=["console-ui"])

    @router.get("/ui/bootstrap-state")
    def ui_bootstrap_state() -> dict[str, Any]:
        return controller.console.bootstrap_state()

    @router.get("/ui/dashboard-summary")
    def ui_dashboard_summary(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.dashboard_summary()

    @router.get("/ui/tasks/recent")
    def ui_tasks_recent(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return {"items": controller.console.dashboard_summary()["recent_tasks"]}

    @router.get("/ui/tasks/{task_id}")
    def ui_task_cockpit(task_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.task_cockpit(task_id)

    @router.post("/ui/tasks/{task_id}/collaboration")
    async def ui_task_collaboration(task_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["operator"])
        payload = await request.json()
        return controller.api.configure_task_collaboration(
            task_id=task_id,
            owner=str(payload.get("owner", "")),
            reviewer=str(payload.get("reviewer", "")),
            operators=[str(item) for item in payload.get("operators", [])],
            watchers=[str(item) for item in payload.get("watchers", [])],
            approval_assignee=str(payload.get("approval_assignee", "")),
        ).to_dict()

    @router.post("/ui/tasks/{task_id}/leases")
    async def ui_task_leases(task_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["operator"])
        payload = await request.json()
        return controller.api.acquire_task_lease(
            task_id=task_id,
            actor=str(payload.get("actor", "operator")),
            lease_kind=str(payload.get("lease_kind", "owner")),
            phase=str(payload.get("phase", "execution")),
            ttl_seconds=int(payload.get("ttl_seconds", 900)),
        ).to_dict()

    @router.post("/ui/tasks/{task_id}/branches")
    async def ui_task_branches(task_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["operator"])
        payload = await request.json()
        return controller.api.create_task_branch(
            task_id=task_id,
            actor=str(payload.get("actor", "operator")),
            branch_kind=str(payload.get("branch_kind", "research")),
            title=str(payload.get("title", "Task branch")),
            parent_branch_id=str(payload.get("parent_branch_id", "")),
        ).to_dict()

    @router.post("/ui/tasks/{task_id}/handoff")
    async def ui_task_handoff(task_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["operator"])
        payload = await request.json()
        return controller.api.open_handoff_window(
            task_id=task_id,
            from_actor=str(payload.get("from_actor", "operator")),
            to_actor=str(payload.get("to_actor", "")),
            summary=str(payload.get("summary", "")),
            branch_id=str(payload.get("branch_id", "")),
        ).to_dict()

    @router.post("/ui/tasks/{task_id}/strategy/feedback")
    async def ui_task_strategy_feedback(task_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["evaluator"])
        payload = await request.json()
        return controller.api.record_strategy_feedback(
            scope_key=task_id,
            actor=str(payload.get("actor", "reviewer")),
            strategy_kind=str(payload.get("strategy_kind", "summarization_policy")),
            signal_kind=str(payload.get("signal_kind", "review_accept")),
            metrics=dict(payload.get("metrics", {})),
            evidence_refs=[str(item) for item in payload.get("evidence_refs", [])],
        ).to_dict()

    @router.post("/ui/tasks/{task_id}/strategy/candidates")
    async def ui_task_strategy_candidate(task_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["evaluator"])
        payload = await request.json()
        return controller.api.propose_strategy_candidate(
            scope_key=task_id,
            actor=str(payload.get("actor", "reviewer")),
            strategy_kind=str(payload.get("strategy_kind", "summarization_policy")),
            target_component=str(payload.get("target_component", "")),
            hypothesis=str(payload.get("hypothesis", "")),
            supporting_signal_ids=[str(item) for item in payload.get("supporting_signal_ids", [])],
        ).to_dict()

    @router.post("/ui/tasks/{task_id}/strategy/candidates/{candidate_id}/evaluate")
    async def ui_task_strategy_evaluate(task_id: str, candidate_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["evaluator"])
        payload = await request.json()
        return controller.api.evaluate_strategy_candidate(
            candidate_id,
            regression_failures=None if payload.get("regression_failures") is None else int(payload.get("regression_failures")),
            gain=None if payload.get("gain") is None else float(payload.get("gain")),
        ).to_dict()

    @router.post("/ui/tasks/{task_id}/strategy/candidates/{candidate_id}/canary")
    async def ui_task_strategy_canary(task_id: str, candidate_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["evaluator"])
        payload = await request.json()
        return controller.api.run_strategy_canary(
            candidate_id,
            actor=str(payload.get("actor", "reviewer")),
            success_rate=float(payload.get("success_rate", 0.0)),
            anomaly_count=int(payload.get("anomaly_count", 0)),
            scope=task_id,
        ).to_dict()

    @router.post("/ui/tasks/{task_id}/strategy/candidates/{candidate_id}/promote")
    async def ui_task_strategy_promote(task_id: str, candidate_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["approver"])
        payload = await request.json()
        return controller.api.promote_strategy_candidate(
            candidate_id,
            actor=str(payload.get("actor", "reviewer")),
            reason=str(payload.get("reason", "UI strategy promotion requested")),
        ).to_dict()

    @router.get("/ui/tasks/{task_id}/timeline")
    def ui_task_timeline(task_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.task_cockpit(task_id)["timeline"]

    @router.get("/ui/tasks/{task_id}/evidence-trace")
    def ui_task_evidence_trace(task_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.task_cockpit(task_id)["evidence_trace"]

    @router.get("/ui/memory/overview")
    def ui_memory_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.memory_overview()

    @router.get("/ui/memory/{task_id}")
    def ui_memory_task(task_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.api.memory_kernel_state(task_id)

    @router.get("/ui/software/overview")
    def ui_software_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.software_overview()

    @router.get("/ui/maintenance/overview")
    def ui_maintenance_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.maintenance_overview()

    @router.get("/ui/approvals")
    def ui_approvals(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.approvals_inbox()

    @router.post("/ui/approvals/{request_id}/decision")
    async def ui_approval_decision(request_id: str, request: Request) -> dict[str, Any]:
        principal = current_session(request, required_scopes=["approver"])
        payload = await request.json()
        return controller.console.decide_approval(
            request_id=request_id,
            approver=principal.user.email,
            status=str(payload.get("status", "approved")),
            rationale=str(payload.get("rationale", "")),
        )

    @router.get("/ui/doctor")
    def ui_doctor(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.doctor_report()

    @router.get("/ui/audit/overview")
    def ui_audit_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.audit_overview()

    @router.get("/ui/playbooks/overview")
    def ui_playbooks_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.playbooks_overview()

    @router.get("/ui/benchmarks/overview")
    def ui_benchmarks_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.benchmarks_overview()

    @router.get("/ui/collaboration/overview")
    def ui_collaboration_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.collaboration_summary().to_dict()

    @router.get("/ui/mcp/overview")
    def ui_mcp_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.mcp_overview()

    @router.post("/ui/mcp/servers")
    async def ui_mcp_register_server(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.register_mcp_server(dict(payload))

    @router.post("/ui/mcp/servers/{server_id}/tools")
    async def ui_mcp_register_tool(server_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.register_mcp_tool(server_id, dict(payload))

    @router.post("/ui/mcp/servers/{server_id}/invoke")
    async def ui_mcp_invoke(server_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["operator"])
        payload = await request.json()
        return controller.console.invoke_mcp_tool(server_id, dict(payload))

    return router


def build_console_config_router(
    *,
    controller: Any,
    current_session: Callable[..., SessionPrincipal],
) -> APIRouter:
    """Build config and diagnostics routes."""

    router = APIRouter(tags=["console-config"])

    @router.get("/config/effective")
    def config_effective(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        return controller.console.config_effective()

    @router.post("/config/update")
    async def config_update(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.update_config(dict(payload))

    @router.post("/config/test-provider")
    async def config_test_provider(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.test_provider_connection(dict(payload))

    @router.post("/config/test-oidc")
    async def config_test_oidc(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.test_oidc_provider_config(dict(payload))

    return router


def build_console_usage_router(
    *,
    controller: Any,
    current_session: Callable[..., SessionPrincipal],
) -> APIRouter:
    """Build usage and cost monitoring routes."""

    router = APIRouter(tags=["console-usage"])

    @router.get("/usage/summary")
    def usage_summary(request: Request, window: str = "24h") -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.usage_summary(window=window)

    @router.get("/usage/tasks/{task_id}")
    def usage_task(request: Request, task_id: str, window: str = "24h") -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.task_usage_summary(task_id, window=window)

    return router


def build_console_events_router(
    *,
    controller: Any,
    current_session: Callable[..., SessionPrincipal],
    serialize: Callable[[Any], Any],
) -> APIRouter:
    """Build event-stream routes for live console updates."""

    router = APIRouter(tags=["console-events"])

    @router.get("/events/stream")
    def events_stream(request: Request) -> StreamingResponse:
        current_session(request, required_scopes=["viewer"])

        def iterator() -> Any:
            for event_name, payload in controller.console.event_stream_payloads():
                yield f"event: {event_name}\n".encode("utf-8")
                yield f"data: {json.dumps(serialize(payload), ensure_ascii=True)}\n\n".encode("utf-8")
            yield b"event: heartbeat\n"
            yield f"data: {json.dumps({'timestamp': datetime.now().isoformat()})}\n\n".encode("utf-8")

        return StreamingResponse(iterator(), media_type="text/event-stream")

    return router
