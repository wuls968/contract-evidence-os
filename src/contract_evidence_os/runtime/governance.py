"""Runtime governance, routing policy, scorecards, and execution mode models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from contract_evidence_os.base import SchemaModel, utc_now


@dataclass
class ProviderScorecard(SchemaModel):
    """Persistent provider QoS and usefulness record."""

    version: str
    provider_name: str
    profile: str
    total_requests: int
    successes: int
    failures: int
    structured_output_successes: int
    retries: int
    fallbacks: int
    average_latency_ms: float
    average_cost_per_success: float
    verification_usefulness: float
    continuity_usefulness: float
    degraded_signals: int = 0
    last_updated: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()

    @property
    def reliability(self) -> float:
        total = max(self.total_requests, 1)
        return self.successes / total


@dataclass
class ToolScorecardView(SchemaModel):
    """Normalized tool scorecard used during routing decisions."""

    version: str = "1.0"
    tool_name: str = ""
    variant: str = ""
    reliability: float = 0.0
    average_latency_ms: float = 0.0
    evidence_usefulness: float = 0.0
    cost_impact: float = 0.0
    approval_friction: float = 0.0

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class RoutingContext(SchemaModel):
    """Context that influences provider and tool routing."""

    version: str = "1.0"
    role: str = ""
    workload: str = ""
    risk_level: str = "low"
    requires_structured_output: bool = False
    execution_mode: str = "standard"
    budget_remaining: float = 0.0
    role_budget_remaining: float = 0.0
    degraded_mode_active: bool = False
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderSelectionPolicy(SchemaModel):
    """Provider selection policy knobs."""

    version: str = "1.0"
    prefer_live: bool = True
    require_structured_output: bool = False
    verification_bias: bool = False
    prefer_low_cost: bool = False
    allow_degraded_fallback: bool = True

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ToolSelectionPolicy(SchemaModel):
    """Tool selection policy knobs."""

    version: str = "1.0"
    prefer_reliable_tools: bool = True
    prefer_evidence_rich_tools: bool = True
    allow_disabled_tools: bool = False

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class DegradedModePolicy(SchemaModel):
    """Policy used when providers or tools are degraded."""

    version: str = "1.0"
    max_disabled_providers: int = 1
    reduce_concurrency_to: int = 1
    require_low_cost_paths: bool = True

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class HighRiskExecutionPolicy(SchemaModel):
    """Policy overrides for high-risk tasks."""

    version: str = "1.0"
    force_verification_provider_bias: bool = True
    max_parallel_nodes: int = 1

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class LowCostExecutionPolicy(SchemaModel):
    """Policy overrides for low-cost mode."""

    version: str = "1.0"
    max_parallel_nodes: int = 2
    prefer_low_cost_provider: bool = True
    preserve_verification_reserve: bool = True

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class VerificationHeavyPolicy(SchemaModel):
    """Policy overrides for verification-heavy mode."""

    version: str = "1.0"
    require_structured_output: bool = True
    max_parallel_nodes: int = 1
    prefer_verifier_reliability: bool = True

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class RoutingDecisionRecord(SchemaModel):
    """Explainable routing decision for provider or tool selection."""

    version: str
    decision_id: str
    task_id: str
    plan_node_id: str
    decision_type: str
    chosen_provider: str = ""
    chosen_tool: str = ""
    chosen_variant: str = ""
    candidates_considered: list[str] = field(default_factory=list)
    reason: str = ""
    scorecard_signals: dict[str, Any] = field(default_factory=dict)
    policy_overrides: list[str] = field(default_factory=list)
    degraded_mode_active: bool = False
    execution_mode: str = "standard"
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ExecutionModeState(SchemaModel):
    """Persisted execution mode for a task."""

    version: str
    mode_id: str
    task_id: str
    mode_name: str
    reason: str
    active_constraints: list[str]
    deferred_opportunities: list[str]
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class GovernanceEvent(SchemaModel):
    """Governance state transition or guardrail event."""

    version: str
    event_id: str
    task_id: str
    event_type: str
    summary: str
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ConcurrencyState(SchemaModel):
    """Persisted bounded-concurrency controller state."""

    version: str
    concurrency_id: str
    task_id: str
    max_parallel_nodes: int
    role_limits: dict[str, int]
    provider_limits: dict[str, int]
    tool_limits: dict[str, int]
    active_nodes: list[str]
    last_batch_nodes: list[str]
    backpressure_active: bool
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class RoutingPolicy(SchemaModel):
    """Explicit routing policy combining provider, tool, and mode preferences."""

    version: str
    policy_id: str
    name: str
    execution_mode: str
    provider_policy: ProviderSelectionPolicy
    tool_policy: dict[str, Any]
    degraded_mode_policy: dict[str, Any]
    high_risk_policy: HighRiskExecutionPolicy = field(default_factory=HighRiskExecutionPolicy)
    low_cost_policy: LowCostExecutionPolicy = field(default_factory=LowCostExecutionPolicy)
    verification_heavy_policy: VerificationHeavyPolicy = field(default_factory=VerificationHeavyPolicy)

    def __post_init__(self) -> None:
        self.validate()

    def select_provider(
        self,
        *,
        context: RoutingContext,
        capabilities: dict[str, Any],
        provider_scorecards: dict[str, ProviderScorecard],
        tool_scorecards: dict[str, ToolScorecardView],
    ) -> RoutingDecisionRecord:
        scored: list[tuple[float, str, list[str], dict[str, Any]]] = []
        for provider_name, capability in capabilities.items():
            overrides: list[str] = []
            if getattr(capability, "availability_state", "available") != "available":
                continue
            if context.requires_structured_output and not getattr(capability, "supports_structured_output", False):
                continue
            scorecard = provider_scorecards.get(provider_name)
            reliability = 0.5 if scorecard is None else scorecard.reliability
            latency = 9999.0 if scorecard is None else scorecard.average_latency_ms
            cost = 1.0
            cost_hint = getattr(capability, "cost_characteristics", "medium")
            if cost_hint in {"low", "lower"}:
                cost = 0.2
            elif cost_hint == "higher":
                cost = 0.9
            elif cost_hint == "medium":
                cost = 0.5
            verification = 0.5 if scorecard is None else scorecard.verification_usefulness
            continuity = 0.5 if scorecard is None else scorecard.continuity_usefulness
            score = reliability * 0.6
            score += (1.0 / max(latency, 1.0)) * 40.0
            score += continuity * 0.1
            if self.execution_mode == "low_cost" or context.execution_mode == "low_cost":
                score += (1.0 - cost) * 1.25
                overrides.append("low_cost_bias")
            if self.provider_policy.verification_bias or context.workload == "verification":
                score += verification * 0.4
                overrides.append("verification_bias")
            if context.degraded_mode_active:
                score -= float(getattr(scorecard, "degraded_signals", 0) if scorecard is not None else 0)
                overrides.append("degraded_mode")
            scored.append(
                (
                    score,
                    provider_name,
                    overrides,
                    {
                        "reliability": reliability,
                        "latency_ms": latency,
                        "cost_hint": cost_hint,
                        "verification_usefulness": verification,
                        "continuity_usefulness": continuity,
                        "tool_candidates": list(tool_scorecards),
                    },
                )
            )
        if not scored:
            return RoutingDecisionRecord(
                version="1.0",
                decision_id="routing-decision-missing",
                task_id="",
                plan_node_id="",
                decision_type="provider",
                reason="no compatible providers",
                degraded_mode_active=context.degraded_mode_active,
                execution_mode=context.execution_mode,
            )
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, provider_name, overrides, signals = scored[0]
        reason_bits = [f"selected {provider_name} with score {best_score:.3f}"]
        if "low_cost_bias" in overrides:
            reason_bits.append("cost-aware policy favored the cheaper provider")
        if "verification_bias" in overrides:
            reason_bits.append("verification usefulness increased the score")
        if not overrides:
            reason_bits.append("reliability and latency dominated the choice")
        return RoutingDecisionRecord(
            version="1.0",
            decision_id="routing-decision-selected",
            task_id="",
            plan_node_id="",
            decision_type="provider",
            chosen_provider=provider_name,
            candidates_considered=[item[1] for item in scored],
            reason="; ".join(reason_bits),
            scorecard_signals=signals,
            policy_overrides=overrides,
            degraded_mode_active=context.degraded_mode_active,
            execution_mode=context.execution_mode,
        )

    def select_tool(
        self,
        *,
        context: RoutingContext,
        tool_name: str,
        candidates: list[ToolScorecardView],
    ) -> RoutingDecisionRecord:
        ranked = sorted(
            candidates,
            key=lambda item: (item.reliability, item.evidence_usefulness, -item.cost_impact),
            reverse=True,
        )
        best = ranked[0]
        return RoutingDecisionRecord(
            version="1.0",
            decision_id="tool-decision-selected",
            task_id="",
            plan_node_id="",
            decision_type="tool",
            chosen_tool=tool_name,
            chosen_variant=best.variant,
            candidates_considered=[item.variant for item in ranked],
            reason=f"selected {tool_name}:{best.variant} using tool scorecard and execution mode {context.execution_mode}",
            scorecard_signals={
                "reliability": best.reliability,
                "evidence_usefulness": best.evidence_usefulness,
                "cost_impact": best.cost_impact,
            },
            policy_overrides=[],
            degraded_mode_active=context.degraded_mode_active,
            execution_mode=context.execution_mode,
        )


class ProviderGovernanceManager:
    """Track provider scorecards from usage records."""

    def update(
        self,
        scorecard: ProviderScorecard | None,
        *,
        provider_name: str,
        profile: str,
        success: bool,
        structured_output_ok: bool,
        retry_count: int,
        fallback_used: bool,
        latency_ms: float,
        cost: float,
        verification_usefulness: float,
        continuity_usefulness: float,
        degraded_signal: bool = False,
    ) -> ProviderScorecard:
        if scorecard is None:
            total_requests = 0
            successes = 0
            failures = 0
            structured_output_successes = 0
            retries = 0
            fallbacks = 0
            average_latency_ms = 0.0
            average_cost_per_success = 0.0
            old_verification = 0.0
            old_continuity = 0.0
            degraded_signals = 0
        else:
            total_requests = scorecard.total_requests
            successes = scorecard.successes
            failures = scorecard.failures
            structured_output_successes = scorecard.structured_output_successes
            retries = scorecard.retries
            fallbacks = scorecard.fallbacks
            average_latency_ms = scorecard.average_latency_ms
            average_cost_per_success = scorecard.average_cost_per_success
            old_verification = scorecard.verification_usefulness
            old_continuity = scorecard.continuity_usefulness
            degraded_signals = scorecard.degraded_signals

        total_requests += 1
        successes += 1 if success else 0
        failures += 0 if success else 1
        structured_output_successes += 1 if structured_output_ok else 0
        retries += retry_count
        fallbacks += 1 if fallback_used else 0
        degraded_signals += 1 if degraded_signal else 0

        def average(previous: float, new_value: float) -> float:
            return ((previous * (total_requests - 1)) + new_value) / total_requests

        return ProviderScorecard(
            version="1.0",
            provider_name=provider_name,
            profile=profile,
            total_requests=total_requests,
            successes=successes,
            failures=failures,
            structured_output_successes=structured_output_successes,
            retries=retries,
            fallbacks=fallbacks,
            average_latency_ms=average(average_latency_ms, latency_ms),
            average_cost_per_success=average(average_cost_per_success, cost),
            verification_usefulness=average(old_verification, verification_usefulness),
            continuity_usefulness=average(old_continuity, continuity_usefulness),
            degraded_signals=degraded_signals,
            last_updated=utc_now(),
        )
