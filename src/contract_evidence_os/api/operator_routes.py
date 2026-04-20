"""Router builders for operator and compatibility HTTP surfaces."""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse


def build_operator_router(
    *,
    controller: Any,
    serialize: Callable[[Any], Any],
    proxy_error_response: Callable[[HTTPException], JSONResponse],
) -> APIRouter:
    """Build versioned operator routes and explicit legacy compatibility routes."""

    router = APIRouter(tags=["operator-v1"])

    @router.get("/memory/cross-scope-timeline")
    def legacy_cross_scope_timeline(request: Request, scope_keys: str, subject: str, predicate: str) -> JSONResponse:
        headers = {key.lower(): value for key, value in request.headers.items()}
        remote_host = request.client.host if request.client else ""
        path = ["memory", "cross-scope-timeline"]
        try:
            controller.authorize_request(path=path, method="GET", headers=headers, remote_host=remote_host)
            payload = controller.dispatch_get(
                path,
                {"scope_keys": [scope_keys], "subject": [subject], "predicate": [predicate]},
            )
        except HTTPException as exc:
            return proxy_error_response(exc)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
        return JSONResponse(serialize(payload))

    @router.get("/memory/cross-scope-repairs")
    def legacy_cross_scope_repairs(request: Request, scope_keys: str, subject: str, predicate: str) -> JSONResponse:
        headers = {key.lower(): value for key, value in request.headers.items()}
        remote_host = request.client.host if request.client else ""
        path = ["memory", "cross-scope-repairs"]
        try:
            controller.authorize_request(path=path, method="GET", headers=headers, remote_host=remote_host)
            payload = controller.dispatch_get(
                path,
                {"scope_keys": [scope_keys], "subject": [subject], "predicate": [predicate]},
            )
        except HTTPException as exc:
            return proxy_error_response(exc)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
        return JSONResponse(serialize(payload))

    @router.get("/metrics")
    def metrics(request: Request) -> PlainTextResponse:
        headers = {key.lower(): value for key, value in request.headers.items()}
        controller.authorize_request(
            path=["metrics"],
            method="GET",
            headers=headers,
            remote_host=request.client.host if request.client else "",
        )
        return PlainTextResponse(controller.api.prometheus_metrics(), media_type="text/plain; version=0.0.4")

    @router.api_route("/v1/{full_path:path}", methods=["GET", "POST"])
    async def v1_proxy(full_path: str, request: Request) -> Response:
        path = controller.normalized_path("/v1/" + full_path)
        headers = {key.lower(): value for key, value in request.headers.items()}
        remote_host = request.client.host if request.client else ""
        try:
            if request.method == "GET":
                controller.authorize_request(path=path, method="GET", headers=headers, remote_host=remote_host)
                payload = controller.dispatch_get(path, parse_qs(request.url.query))
                if path == ["metrics"]:
                    return PlainTextResponse(str(payload), media_type="text/plain; version=0.0.4")
                return JSONResponse(serialize(payload))
            body = await request.body()
            if len(body) > controller.max_request_bytes:
                raise HTTPException(status_code=413, detail={"error": "request_too_large"})
            controller.authorize_request(path=path, method="POST", headers=headers, body=body, remote_host=remote_host)
            payload = controller.dispatch_post(path, {} if not body else json.loads(body.decode("utf-8")))
        except HTTPException as exc:
            return proxy_error_response(exc)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
        return JSONResponse(serialize(payload))

    return router


def build_legacy_proxy_router(
    *,
    controller: Any,
    serialize: Callable[[Any], Any],
    proxy_error_response: Callable[[HTTPException], JSONResponse],
) -> APIRouter:
    """Build the historical catch-all proxy route last."""

    router = APIRouter(tags=["operator-v1"])

    @router.api_route("/{full_path:path}", methods=["GET", "POST"])
    async def legacy_proxy(full_path: str, request: Request) -> Response:
        path = controller.normalized_path("/" + full_path)
        headers = {key.lower(): value for key, value in request.headers.items()}
        remote_host = request.client.host if request.client else ""
        try:
            if request.method == "GET":
                controller.authorize_request(path=path, method="GET", headers=headers, remote_host=remote_host)
                payload = controller.dispatch_get(path, parse_qs(request.url.query))
                if path == ["metrics"]:
                    return PlainTextResponse(str(payload), media_type="text/plain; version=0.0.4")
                return JSONResponse(serialize(payload))
            body = await request.body()
            if len(body) > controller.max_request_bytes:
                raise HTTPException(status_code=413, detail={"error": "request_too_large"})
            controller.authorize_request(path=path, method="POST", headers=headers, body=body, remote_host=remote_host)
            payload = controller.dispatch_post(path, {} if not body else json.loads(body.decode("utf-8")))
        except HTTPException as exc:
            return proxy_error_response(exc)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
        return JSONResponse(serialize(payload))

    return router
