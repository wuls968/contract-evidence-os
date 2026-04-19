"""Tool governance and scorecards."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from contract_evidence_os.base import SchemaModel, utc_now
from contract_evidence_os.tools.models import ToolResult


@dataclass
class ToolScorecard(SchemaModel):
    """Persistent QoS scorecard for a tool or tool variant."""

    version: str
    tool_name: str
    variant: str
    total_invocations: int
    successes: int
    failures: int
    retry_successes: int
    safety_incidents: int
    average_latency_ms: float
    evidence_usefulness: float
    token_impact: float
    cost_impact: float
    last_updated: datetime

    def __post_init__(self) -> None:
        self.validate()


class ToolGovernanceManager:
    """Track tool QoS and recommend tool modes."""

    def update(
        self,
        scorecard: ToolScorecard | None,
        result: ToolResult,
        evidence_usefulness: float,
        token_impact: float = 0.0,
        cost_impact: float = 0.0,
        safety_incident: bool = False,
    ) -> ToolScorecard:
        latency_ms = (result.completed_at - result.started_at).total_seconds() * 1000.0
        if scorecard is None:
            total = 0
            successes = 0
            failures = 0
            retry_successes = 0
            safety_incidents = 0
            average_latency = 0.0
            avg_usefulness = 0.0
            avg_token = 0.0
            avg_cost = 0.0
        else:
            total = scorecard.total_invocations
            successes = scorecard.successes
            failures = scorecard.failures
            retry_successes = scorecard.retry_successes
            safety_incidents = scorecard.safety_incidents
            average_latency = scorecard.average_latency_ms
            avg_usefulness = scorecard.evidence_usefulness
            avg_token = scorecard.token_impact
            avg_cost = scorecard.cost_impact

        total += 1
        successes += 1 if result.status == "success" else 0
        failures += 1 if result.status != "success" else 0
        retry_successes += 1 if result.status == "success" and getattr(result, "provider_mode", "live") != "live" else 0
        safety_incidents += 1 if safety_incident else 0

        def average(previous: float, new_value: float) -> float:
            return ((previous * (total - 1)) + new_value) / total

        return ToolScorecard(
            version="1.0",
            tool_name=result.tool_id,
            variant=result.provider_mode,
            total_invocations=total,
            successes=successes,
            failures=failures,
            retry_successes=retry_successes,
            safety_incidents=safety_incidents,
            average_latency_ms=average(average_latency, latency_ms),
            evidence_usefulness=average(avg_usefulness, evidence_usefulness),
            token_impact=average(avg_token, token_impact),
            cost_impact=average(avg_cost, cost_impact),
            last_updated=utc_now(),
        )

    def recommend_mode(self, scorecard: ToolScorecard | None, risk_level: str, simulator_available: bool) -> str:
        """Prefer reliability for high stakes and cost for lower stakes when safe."""

        if risk_level == "high":
            return "live"
        if scorecard is None:
            return "simulator" if simulator_available else "live"
        reliability = 1.0 if scorecard.total_invocations == 0 else scorecard.successes / scorecard.total_invocations
        if reliability < 0.8:
            return "live"
        return "simulator" if simulator_available else "live"
