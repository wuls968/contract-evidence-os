"""Minimal web intelligence adapter."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html import unescape
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.evidence.models import SourceRecord
from contract_evidence_os.tools.models import ToolInvocation, ToolResult, ToolSpec


@dataclass
class WebIntelligenceTool:
    """Fetch pages and perform lightweight HTML search result extraction."""

    spec: ToolSpec = field(
        default_factory=lambda: ToolSpec(
            version="1.0",
            tool_id="web-intelligence",
            name="web_intelligence",
            description="Fetch URLs and perform lightweight search extraction.",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            risk_level="moderate",
            permission_requirements=["external_comm"],
            retry_policy={"max_attempts": 2},
            timeout_policy={"seconds": 15},
            audit_hooks=["record_web_lookup"],
            evidence_hooks=["emit_source_record"],
            validation_hooks=["multi_source_confirmation"],
            mock_provider="mock-web-provider",
            simulator_provider="sim-web-provider",
        )
    )

    def fetch(self, url: str) -> tuple[ToolInvocation, ToolResult, SourceRecord | None]:
        invocation = ToolInvocation(
            version="1.0",
            invocation_id=f"invoke-{uuid4().hex[:10]}",
            tool_id=self.spec.tool_id,
            actor="Researcher",
            input_payload={"url": url},
            requested_at=utc_now(),
            correlation_id=f"web:{url}",
        )
        started_at = utc_now()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ContractEvidenceOS/0.1"})
            with urllib.request.urlopen(request, timeout=15) as response:
                content = response.read().decode("utf-8", errors="ignore")
            result = ToolResult(
                version="1.0",
                invocation_id=invocation.invocation_id,
                tool_id=self.spec.tool_id,
                status="success",
                output_payload={"content": content, "url": url},
                error=None,
                started_at=started_at,
                completed_at=utc_now(),
                correlation_id=invocation.correlation_id,
                provenance={"url": url, "content_length": len(content)},
                confidence=0.7,
                provider_mode="live",
                deterministic=False,
                suggested_follow_up_action="extract cited claims and cross-check with a second source",
                artifact_refs=[url],
            )
            source = SourceRecord(
                version="1.0",
                source_id=f"source-{uuid4().hex[:10]}",
                source_type="web",
                locator=url,
                retrieved_at=utc_now(),
                credibility=0.7,
                time_relevance=1.0,
                content_hash=str(abs(hash(content))),
                snippet=content[:200],
            )
            return invocation, result, source
        except Exception as exc:  # pragma: no cover - network variability
            result = ToolResult(
                version="1.0",
                invocation_id=invocation.invocation_id,
                tool_id=self.spec.tool_id,
                status="failed",
                output_payload={},
                error=str(exc),
                started_at=started_at,
                completed_at=utc_now(),
                correlation_id=invocation.correlation_id,
                provenance={"url": url},
                confidence=0.0,
                provider_mode="live",
                deterministic=False,
                failure_classification="network_or_fetch_error",
                suggested_follow_up_action="retry later or use a simulator result",
            )
            return invocation, result, None

    def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        encoded = urllib.parse.urlencode({"q": query})
        url = f"https://duckduckgo.com/html/?{encoded}"
        _, result, _ = self.fetch(url)
        if result.status != "success":
            return []
        html = result.output_payload["content"]
        pattern = re.compile(r'nofollow" class="result__a" href="(?P<href>[^"]+)">(?P<title>.*?)</a>')
        matches = []
        for match in pattern.finditer(html):
            matches.append(
                {
                    "title": unescape(re.sub(r"<.*?>", "", match.group("title"))),
                    "url": unescape(match.group("href")),
                }
            )
            if len(matches) >= max_results:
                break
        return matches
