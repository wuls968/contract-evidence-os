"""Provider-agnostic model execution and routing receipts."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4

from contract_evidence_os.base import SchemaModel, utc_now
from contract_evidence_os.runtime.model_routing import ModelRoute


class ProviderError(RuntimeError):
    """Raised when a provider cannot satisfy a request."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        status_code: int | None = None,
        recoverable: bool = True,
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.recoverable = recoverable
        self.retryable = retryable


@dataclass
class ProviderRequest(SchemaModel):
    """Normalized provider request."""

    version: str
    request_id: str
    task_id: str
    role: str
    workload: str
    prompt: str
    input_payload: dict[str, Any]
    plan_node_id: str = ""
    correlation_id: str = ""
    structured_output: dict[str, Any] | None = None
    timeout_seconds: float | None = None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderResponse(SchemaModel):
    """Structured provider response."""

    version: str
    response_id: str
    provider_name: str
    model_name: str
    profile: str
    output_payload: dict[str, Any]
    confidence: float
    provider_mode: str
    deterministic: bool
    usage: dict[str, int]
    response_summary: str = ""
    latency_ms: float = 0.0
    raw_response: dict[str, Any] = field(default_factory=dict)
    completed_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderUsageRecord(SchemaModel):
    """Durable record of one provider request/response cycle."""

    version: str
    usage_id: str
    task_id: str
    plan_node_id: str
    correlation_id: str
    role: str
    provider_name: str
    model_name: str
    profile: str
    request_summary: str
    response_summary: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    latency_ms: float
    retry_count: int
    fallback_used: bool
    status: str
    error_code: str = ""
    audit_event_id: str = ""
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderCapabilityRecord(SchemaModel):
    """Structured capability metadata for one live or simulator provider."""

    version: str
    provider_name: str
    supported_response_modes: list[str]
    supports_structured_output: bool
    max_context_hint: int
    cost_characteristics: str
    rate_limit_characteristics: str
    reliability_inputs: dict[str, float]
    timeout_defaults: dict[str, float]
    retry_defaults: dict[str, int]
    availability_state: str

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class RoutingReceipt(SchemaModel):
    """Durable receipt for a routing decision and provider execution."""

    version: str
    routing_id: str
    task_id: str
    role: str
    workload: str
    risk_level: str
    strategy_name: str
    provider_name: str
    model_name: str
    profile: str
    cost_tier: str
    attempt_count: int
    fallback_used: bool
    status: str
    rationale: str
    correlation_id: str = ""
    error_code: str = ""
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


class LLMProvider(Protocol):
    """Provider protocol for model execution."""

    name: str

    def complete(self, route: ModelRoute, request: ProviderRequest) -> ProviderResponse:
        """Execute a routed request."""


@dataclass
class BaseLLMProvider:
    """Base provider adapter with common helpers."""

    name: str
    provider_mode: str = "live"

    def complete(self, route: ModelRoute, request: ProviderRequest) -> ProviderResponse:  # pragma: no cover - interface
        raise NotImplementedError

    def _response(
        self,
        route: ModelRoute,
        request: ProviderRequest,
        *,
        output_payload: dict[str, Any],
        confidence: float,
        deterministic: bool,
        usage: dict[str, int],
        response_summary: str,
        latency_ms: float,
        raw_response: dict[str, Any] | None = None,
    ) -> ProviderResponse:
        return ProviderResponse(
            version="1.0",
            response_id=f"provider-response-{uuid4().hex[:10]}",
            provider_name=self.name,
            model_name=route.model_name,
            profile=route.profile,
            output_payload=output_payload,
            confidence=confidence,
            provider_mode=self.provider_mode,
            deterministic=deterministic,
            usage=usage,
            response_summary=response_summary,
            latency_ms=latency_ms,
            raw_response={} if raw_response is None else raw_response,
            completed_at=utc_now(),
        )


@dataclass
class DeterministicLLMProvider(BaseLLMProvider):
    """Deterministic provider used for testing and simulator-first routing."""

    fail_profiles: set[str] = field(default_factory=set)
    provider_mode: str = "simulator"

    def complete(self, route: ModelRoute, request: ProviderRequest) -> ProviderResponse:
        if route.profile in self.fail_profiles:
            raise ProviderError(f"{self.name} configured to fail profile {route.profile}")

        payload = self._render_payload(route, request)
        return self._response(
            route,
            request,
            output_payload=payload,
            confidence=float(payload.get("confidence", 0.85)),
            deterministic=True,
            usage={"input_tokens": len(request.prompt.split()), "output_tokens": len(str(payload).split()), "total_tokens": len(request.prompt.split()) + len(str(payload).split())},
            response_summary=str(payload)[:120],
            latency_ms=0.0,
        )

    def _render_payload(self, route: ModelRoute, request: ProviderRequest) -> dict[str, Any]:
        if request.workload == "extraction":
            content = str(request.input_payload.get("content", ""))
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            if route.strategy_name == "economy":
                selected = [line for line in lines if "must" in line.lower() or "never" in line.lower()]
            elif route.strategy_name == "quality":
                selected = lines
            else:
                selected = lines
            return {
                "statements": [{"statement": line, "confidence": 0.9} for line in selected],
                "confidence": 0.9 if selected else 0.0,
            }
        if request.workload == "verification":
            facts = request.input_payload.get("facts", [])
            return {
                "supported": bool(facts),
                "missing_evidence": any(not fact.get("evidence_refs") for fact in facts if isinstance(fact, dict)),
                "confidence": 0.9 if facts else 0.0,
            }
        return {"echo": request.input_payload, "confidence": 0.8}


@dataclass
class OpenAIResponsesProvider(BaseLLMProvider):
    """Live provider adapter for the OpenAI Responses API."""

    api_key: str = ""
    base_url: str = "https://api.openai.com/v1/responses"
    timeout_seconds: float = 30.0
    provider_mode: str = "live"

    def complete(self, route: ModelRoute, request: ProviderRequest) -> ProviderResponse:
        return self.complete_live(model_name=route.model_name, profile=route.profile, request=request)

    def complete_live(self, *, model_name: str, profile: str, request: ProviderRequest) -> ProviderResponse:
        started = time.monotonic()
        body = {
            "model": model_name,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": f"Role: {request.role}. Workload: {request.workload}."}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": f"{request.prompt}\n\nInput:\n{json.dumps(request.input_payload, ensure_ascii=True, sort_keys=True)}"}],
                },
            ],
        }
        if request.structured_output is not None:
            body["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": str(request.structured_output.get("name", "structured_output")),
                    "schema": dict(request.structured_output.get("schema", {})),
                }
            }
        raw_request = json.dumps(body, ensure_ascii=True).encode("utf-8")
        http_request = urllib.request.Request(
            self.base_url,
            data=raw_request,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(http_request, timeout=request.timeout_seconds or self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore")
            raise self._normalize_http_error(exc.code, message) from exc
        except urllib.error.URLError as exc:
            raise ProviderError(str(exc.reason), code="network_error", recoverable=True, retryable=True) from exc

        text = self._extract_output_text(raw)
        if request.structured_output is not None and text:
            output_payload = json.loads(text)
            response_summary = text[:160]
        else:
            output_payload = {"text": text}
            response_summary = text[:160]
        usage = {
            "input_tokens": int(raw.get("usage", {}).get("input_tokens", 0)),
            "output_tokens": int(raw.get("usage", {}).get("output_tokens", 0)),
            "total_tokens": int(raw.get("usage", {}).get("total_tokens", 0)),
        }
        latency_ms = (time.monotonic() - started) * 1000.0
        return self._response(
            ModelRoute(
                role=request.role,
                workload=request.workload,
                risk_level="unknown",
                profile=profile,
                cost_tier="medium",
                rationale="live provider request",
                model_name=model_name,
            ),
            request,
            output_payload=output_payload,
            confidence=0.9 if text else 0.0,
            deterministic=False,
            usage=usage,
            response_summary=response_summary,
            latency_ms=latency_ms,
            raw_response=raw,
        )

    def _extract_output_text(self, raw: dict[str, Any]) -> str:
        if isinstance(raw.get("output_text"), str):
            return str(raw["output_text"])
        for item in raw.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return str(content.get("text", ""))
        return ""

    def _normalize_http_error(self, status_code: int, message: str) -> ProviderError:
        if status_code == 401:
            return ProviderError(message or "unauthorized", code="unauthorized", status_code=status_code, recoverable=False, retryable=False)
        if status_code == 429:
            return ProviderError(message or "rate_limited", code="rate_limited", status_code=status_code, recoverable=True, retryable=True)
        if status_code >= 500:
            return ProviderError(message or "server_error", code="server_error", status_code=status_code, recoverable=True, retryable=True)
        return ProviderError(message or "invalid_request", code="invalid_request", status_code=status_code, recoverable=False, retryable=False)

    def capability(self) -> ProviderCapabilityRecord:
        return ProviderCapabilityRecord(
            version="1.0",
            provider_name=self.name,
            supported_response_modes=["responses"],
            supports_structured_output=True,
            max_context_hint=200000,
            cost_characteristics="higher",
            rate_limit_characteristics="moderate",
            reliability_inputs={"base": 0.9},
            timeout_defaults={"seconds": self.timeout_seconds},
            retry_defaults={"max_attempts": 2},
            availability_state="available",
        )


@dataclass
class AnthropicMessagesProvider(BaseLLMProvider):
    """Live provider adapter for the Anthropic Messages API."""

    api_key: str = ""
    base_url: str = "https://api.anthropic.com/v1/messages"
    anthropic_version: str = "2023-06-01"
    timeout_seconds: float = 30.0
    model_default: str = "claude-sonnet-4-20250514"
    provider_mode: str = "live"

    def complete(self, route: ModelRoute, request: ProviderRequest) -> ProviderResponse:
        return self.complete_live(model_name=route.model_name or self.model_default, profile=route.profile, request=request)

    def complete_live(self, *, model_name: str, profile: str, request: ProviderRequest) -> ProviderResponse:
        started = time.monotonic()
        prompt_text = f"{request.prompt}\n\nInput:\n{json.dumps(request.input_payload, ensure_ascii=True, sort_keys=True)}"
        if request.structured_output is not None:
            prompt_text += "\n\nReturn only valid JSON matching this schema:\n"
            prompt_text += json.dumps(request.structured_output.get("schema", {}), ensure_ascii=True, sort_keys=True)
        body = {
            "model": model_name,
            "max_tokens": 1024,
            "system": f"Role: {request.role}. Workload: {request.workload}.",
            "messages": [{"role": "user", "content": prompt_text}],
        }
        http_request = urllib.request.Request(
            self.base_url,
            data=json.dumps(body, ensure_ascii=True).encode("utf-8"),
            method="POST",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": self.anthropic_version,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(http_request, timeout=request.timeout_seconds or self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore")
            raise self._normalize_http_error(exc.code, message) from exc
        except urllib.error.URLError as exc:
            raise ProviderError(str(exc.reason), code="network_error", recoverable=True, retryable=True) from exc

        text = self._extract_output_text(raw)
        if request.structured_output is not None and text:
            output_payload = json.loads(text)
            response_summary = text[:160]
        else:
            output_payload = {"text": text}
            response_summary = text[:160]
        usage = {
            "input_tokens": int(raw.get("usage", {}).get("input_tokens", 0)),
            "output_tokens": int(raw.get("usage", {}).get("output_tokens", 0)),
            "total_tokens": int(raw.get("usage", {}).get("input_tokens", 0)) + int(raw.get("usage", {}).get("output_tokens", 0)),
        }
        return self._response(
            ModelRoute(
                role=request.role,
                workload=request.workload,
                risk_level="unknown",
                profile=profile,
                cost_tier="medium",
                rationale="anthropic messages request",
                model_name=model_name,
            ),
            request,
            output_payload=output_payload,
            confidence=0.88 if text else 0.0,
            deterministic=False,
            usage=usage,
            response_summary=response_summary,
            latency_ms=(time.monotonic() - started) * 1000.0,
            raw_response=raw,
        )

    def _extract_output_text(self, raw: dict[str, Any]) -> str:
        content = raw.get("content", [])
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "text":
                    return str(item.get("text", ""))
        return ""

    def _normalize_http_error(self, status_code: int, message: str) -> ProviderError:
        if status_code == 401:
            return ProviderError(message or "unauthorized", code="unauthorized", status_code=status_code, recoverable=False, retryable=False)
        if status_code == 429:
            return ProviderError(message or "rate_limited", code="rate_limited", status_code=status_code, recoverable=True, retryable=True)
        if status_code >= 500:
            return ProviderError(message or "server_error", code="server_error", status_code=status_code, recoverable=True, retryable=True)
        return ProviderError(message or "invalid_request", code="invalid_request", status_code=status_code, recoverable=False, retryable=False)

    def capability(self) -> ProviderCapabilityRecord:
        return ProviderCapabilityRecord(
            version="1.0",
            provider_name=self.name,
            supported_response_modes=["messages"],
            supports_structured_output=True,
            max_context_hint=200000,
            cost_characteristics="low",
            rate_limit_characteristics="moderate",
            reliability_inputs={"base": 0.88},
            timeout_defaults={"seconds": self.timeout_seconds},
            retry_defaults={"max_attempts": 2},
            availability_state="available",
        )


@dataclass
class ProviderManager:
    """Run provider requests with retry, backoff, and fallback handling."""

    providers: dict[str, LLMProvider] = field(
        default_factory=lambda: {
            "primary": DeterministicLLMProvider(name="primary"),
            "fallback": DeterministicLLMProvider(name="fallback"),
        }
    )
    backoff_seconds: float = 0.0

    def complete(
        self,
        route: ModelRoute,
        request: ProviderRequest,
    ) -> tuple[ProviderResponse, RoutingReceipt]:
        attempts = 0
        available_order = [provider_name for provider_name in (route.provider_order or list(self.providers)) if provider_name in self.providers]
        first_provider = available_order[0] if available_order else ""
        last_error = ProviderError(f"no providers configured for route {route.profile}", code="missing_provider", recoverable=True)
        for provider_name in available_order:
            provider = self.providers[provider_name]
            for _ in range(route.retry_budget):
                attempts += 1
                try:
                    started = time.monotonic()
                    response = provider.complete(route, request)
                    if self.backoff_seconds > 0 and time.monotonic() - started < self.backoff_seconds:
                        time.sleep(self.backoff_seconds - (time.monotonic() - started))
                    receipt = RoutingReceipt(
                        version="1.0",
                        routing_id=f"routing-{uuid4().hex[:10]}",
                        task_id=request.task_id,
                        role=request.role,
                        workload=request.workload,
                        risk_level=route.risk_level,
                        strategy_name=route.strategy_name,
                        provider_name=provider_name,
                        model_name=route.model_name,
                        profile=route.profile,
                        cost_tier=route.cost_tier,
                        attempt_count=attempts,
                        fallback_used=provider_name != first_provider,
                        status="success",
                        rationale=route.rationale,
                        correlation_id=request.correlation_id,
                        created_at=utc_now(),
                    )
                    return response, receipt
                except ProviderError as exc:
                    last_error = exc
                    if self.backoff_seconds > 0:
                        time.sleep(self.backoff_seconds)
                    if not exc.retryable:
                        break
                    continue
        raise last_error

    def build_usage_record(
        self,
        request: ProviderRequest,
        route: ModelRoute,
        response: ProviderResponse,
        receipt: RoutingReceipt,
        *,
        audit_event_id: str = "",
        estimated_cost: float = 0.0,
    ) -> ProviderUsageRecord:
        return ProviderUsageRecord(
            version="1.0",
            usage_id=f"provider-usage-{uuid4().hex[:10]}",
            task_id=request.task_id,
            plan_node_id=request.plan_node_id,
            correlation_id=request.correlation_id,
            role=request.role,
            provider_name=response.provider_name,
            model_name=response.model_name,
            profile=response.profile,
            request_summary=request.prompt[:160],
            response_summary=response.response_summary,
            input_tokens=int(response.usage.get("input_tokens", 0)),
            output_tokens=int(response.usage.get("output_tokens", 0)),
            total_tokens=int(response.usage.get("total_tokens", 0)),
            estimated_cost=estimated_cost,
            latency_ms=response.latency_ms,
            retry_count=max(receipt.attempt_count - 1, 0),
            fallback_used=receipt.fallback_used,
            status=receipt.status,
            audit_event_id=audit_event_id,
        )
