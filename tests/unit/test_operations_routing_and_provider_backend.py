import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from contract_evidence_os.runtime.governance import (
    ProviderScorecard,
    ProviderSelectionPolicy,
    RoutingContext,
    RoutingPolicy,
    ToolScorecardView,
)
from contract_evidence_os.runtime.providers import AnthropicMessagesProvider, ProviderCapabilityRecord, ProviderRequest


def _start_server(handler_cls: type[BaseHTTPRequestHandler]) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


class _AnthropicHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        assert payload["model"] == "claude-sonnet-test"
        body = {
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": json.dumps({"summary": "anthropic structured reply", "confidence": 0.88})}],
            "usage": {"input_tokens": 17, "output_tokens": 9},
        }
        raw = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def test_anthropic_provider_supports_live_completion_and_structured_output() -> None:
    server, url = _start_server(_AnthropicHandler)
    try:
        provider = AnthropicMessagesProvider(
            name="anthropic_live",
            api_key="test-key",
            base_url=f"{url}/v1/messages",
            model_default="claude-sonnet-test",
        )
        request = ProviderRequest(
            version="1.0",
            request_id="provider-request-001",
            task_id="task-001",
            role="Builder",
            workload="build",
            prompt="Return a structured summary.",
            input_payload={"facts": ["Audit history must never be deleted."]},
            structured_output={
                "name": "anthropic_summary",
                "schema": {
                    "type": "object",
                    "properties": {"summary": {"type": "string"}, "confidence": {"type": "number"}},
                    "required": ["summary", "confidence"],
                },
            },
        )
        response = provider.complete_live(
            model_name="claude-sonnet-test",
            profile="builder-live",
            request=request,
        )
        assert response.provider_name == "anthropic_live"
        assert response.output_payload["summary"] == "anthropic structured reply"
        assert response.usage["total_tokens"] == 26
    finally:
        server.shutdown()


def test_provider_selection_policy_uses_scorecards_and_structured_output_compatibility() -> None:
    policy = RoutingPolicy(
        version="1.0",
        policy_id="routing-policy-001",
        name="adaptive-default",
        execution_mode="low_cost",
        provider_policy=ProviderSelectionPolicy(prefer_live=True, require_structured_output=False, verification_bias=False),
        tool_policy={"prefer_reliable_tools": True},
        degraded_mode_policy={"max_disabled_providers": 1},
    )
    context = RoutingContext(
        role="Researcher",
        workload="extraction",
        risk_level="low",
        requires_structured_output=False,
        execution_mode="low_cost",
        budget_remaining=1.5,
    )
    capabilities = {
        "openai_live": ProviderCapabilityRecord(
            version="1.0",
            provider_name="openai_live",
            supported_response_modes=["responses"],
            supports_structured_output=True,
            max_context_hint=100000,
            cost_characteristics="higher",
            rate_limit_characteristics="moderate",
            reliability_inputs={"base": 0.9},
            timeout_defaults={"seconds": 30},
            retry_defaults={"max_attempts": 2},
            availability_state="available",
        ),
        "anthropic_live": ProviderCapabilityRecord(
            version="1.0",
            provider_name="anthropic_live",
            supported_response_modes=["messages"],
            supports_structured_output=True,
            max_context_hint=200000,
            cost_characteristics="lower",
            rate_limit_characteristics="moderate",
            reliability_inputs={"base": 0.88},
            timeout_defaults={"seconds": 30},
            retry_defaults={"max_attempts": 2},
            availability_state="available",
        ),
    }
    provider_scorecards = {
        "openai_live": ProviderScorecard(
            version="1.0",
            provider_name="openai_live",
            profile="quality-extractor",
            total_requests=20,
            successes=19,
            failures=1,
            structured_output_successes=10,
            retries=1,
            fallbacks=0,
            average_latency_ms=180.0,
            average_cost_per_success=0.08,
            verification_usefulness=0.9,
            continuity_usefulness=0.8,
            last_updated=context.created_at,
        ),
        "anthropic_live": ProviderScorecard(
            version="1.0",
            provider_name="anthropic_live",
            profile="quality-extractor",
            total_requests=20,
            successes=18,
            failures=2,
            structured_output_successes=9,
            retries=2,
            fallbacks=1,
            average_latency_ms=150.0,
            average_cost_per_success=0.03,
            verification_usefulness=0.8,
            continuity_usefulness=0.75,
            last_updated=context.created_at,
        ),
    }
    tool_scorecards = {
        "file_retrieval": ToolScorecardView(
            tool_name="file_retrieval",
            variant="live",
            reliability=0.98,
            average_latency_ms=10.0,
            evidence_usefulness=0.9,
            cost_impact=0.01,
            approval_friction=0.0,
        )
    }

    decision = policy.select_provider(
        context=context,
        capabilities=capabilities,
        provider_scorecards=provider_scorecards,
        tool_scorecards=tool_scorecards,
    )
    assert decision.chosen_provider == "anthropic_live"
    assert "cost" in decision.reason.lower()
