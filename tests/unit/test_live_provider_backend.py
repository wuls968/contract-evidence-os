import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from contract_evidence_os.runtime.model_routing import ModelRoute
from contract_evidence_os.runtime.providers import (
    DeterministicLLMProvider,
    OpenAIResponsesProvider,
    ProviderManager,
    ProviderRequest,
)


def _start_server(handler_cls: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


class _StructuredResponseHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        assert payload["model"] == "gpt-4.1-mini"
        assert payload["text"]["format"]["type"] == "json_schema"
        body = {
            "id": "resp_123",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps({"summary": "Built structured output", "confidence": 0.91}),
                        }
                    ],
                }
            ],
            "usage": {"input_tokens": 12, "output_tokens": 7, "total_tokens": 19},
        }
        raw = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


class _RateLimitHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        body = json.dumps({"error": {"message": "rate limited"}}).encode("utf-8")
        self.send_response(429)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def test_openai_responses_provider_handles_structured_outputs() -> None:
    server, url = _start_server(_StructuredResponseHandler)
    try:
        provider = OpenAIResponsesProvider(
            name="openai_live",
            api_key="test-key",
            base_url=f"{url}/v1/responses",
            timeout_seconds=2.0,
        )
        route = ModelRoute(
            role="Builder",
            workload="build",
            risk_level="low",
            profile="builder-live",
            cost_tier="medium",
            rationale="build delivery with live provider",
            model_name="gpt-4.1-mini",
        )
        request = ProviderRequest(
            version="1.0",
            request_id="provider-request-001",
            task_id="task-001",
            role="Builder",
            workload="build",
            prompt="Produce a structured build summary.",
            input_payload={"facts": ["Audit history must never be deleted."]},
            structured_output={
                "name": "build_summary",
                "schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["summary", "confidence"],
                },
            },
            created_at=route_time(),
        )

        response = provider.complete(route, request)

        assert response.provider_name == "openai_live"
        assert response.provider_mode == "live"
        assert response.output_payload["summary"] == "Built structured output"
        assert response.usage["total_tokens"] == 19
    finally:
        server.shutdown()


def test_provider_manager_falls_back_from_live_provider_to_secondary() -> None:
    server, url = _start_server(_RateLimitHandler)
    try:
        manager = ProviderManager(
            providers={
                "primary": OpenAIResponsesProvider(
                    name="openai_live",
                    api_key="test-key",
                    base_url=f"{url}/v1/responses",
                    timeout_seconds=1.0,
                ),
                "fallback": DeterministicLLMProvider(name="fallback"),
            }
        )
        route = ModelRoute(
            role="Researcher",
            workload="extraction",
            risk_level="medium",
            profile="quality-extractor",
            cost_tier="high",
            rationale="prefer live extraction but degrade safely",
            provider_order=["primary", "fallback"],
            model_name="gpt-4.1-mini",
            retry_budget=1,
        )
        request = ProviderRequest(
            version="1.0",
            request_id="provider-request-002",
            task_id="task-002",
            role="Researcher",
            workload="extraction",
            prompt="Extract grounded mandatory constraints.",
            input_payload={"content": "Audit history must never be deleted."},
            created_at=route_time(),
        )

        response, receipt = manager.complete(route, request)

        assert response.provider_name == "fallback"
        assert receipt.fallback_used is True
        assert receipt.status == "success"
    finally:
        server.shutdown()


def route_time():
    from contract_evidence_os.base import utc_now

    return utc_now()
