"""Model routing policy."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelRoute:
    """Selected model profile for a given role and workload."""

    role: str
    workload: str
    risk_level: str
    profile: str
    cost_tier: str
    rationale: str
    provider_order: list[str] = field(default_factory=lambda: ["primary", "fallback"])
    model_name: str = "deterministic-default"
    strategy_name: str = "default"
    retry_budget: int = 2


class ModelRouter:
    """Route workloads to lightweight or deep profiles."""

    def route(
        self,
        role: str,
        workload: str,
        risk_level: str,
        strategy_name: str | None = None,
    ) -> ModelRoute:
        if strategy_name == "economy":
            if workload == "extraction":
                return ModelRoute(
                    role,
                    workload,
                    risk_level,
                    "economy-extractor",
                    "low",
                    "economy strategy favors cheaper extraction",
                    model_name="deterministic-economy",
                    strategy_name="economy",
                    retry_budget=2,
                )
            return ModelRoute(
                role,
                workload,
                risk_level,
                "economy-verifier",
                "medium",
                "economy strategy uses lighter verification",
                model_name="deterministic-economy",
                strategy_name="economy",
                retry_budget=2,
            )
        if strategy_name == "quality":
            if workload == "extraction":
                return ModelRoute(
                    role,
                    workload,
                    risk_level,
                    "quality-extractor",
                    "high",
                    "quality strategy maximizes evidence capture",
                    model_name="deterministic-quality",
                    strategy_name="quality",
                    retry_budget=2,
                )
            return ModelRoute(
                role,
                workload,
                risk_level,
                "quality-verifier",
                "high",
                "quality strategy emphasizes stronger verification",
                model_name="deterministic-quality",
                strategy_name="quality",
                retry_budget=2,
            )
        if role == "Researcher" and workload == "extraction" and risk_level == "low":
            return ModelRoute(role, workload, risk_level, "fast-extractor", "low", "cheap extraction path")
        if role in {"Verifier", "Critic"} or risk_level == "high":
            return ModelRoute(role, workload, risk_level, "deep-verifier", "high", "risk-sensitive verification path")
        if role == "Builder":
            return ModelRoute(role, workload, risk_level, "balanced-builder", "medium", "artifact construction path")
        return ModelRoute(role, workload, risk_level, "balanced-generalist", "medium", "default routing path")
