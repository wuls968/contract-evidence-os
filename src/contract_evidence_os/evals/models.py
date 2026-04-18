"""Evaluation report models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StrategyEvaluationReport:
    """Aggregate benchmark report for one routing strategy or candidate."""

    strategy_name: str
    metrics: dict[str, float]
    case_results: list[dict[str, float]] = field(default_factory=list)
