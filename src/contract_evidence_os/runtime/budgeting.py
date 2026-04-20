"""Budget governance for runtime execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from contract_evidence_os.base import SchemaModel, utc_now


@dataclass
class BudgetPolicy(SchemaModel):
    """Typed budget policy for a task."""

    version: str
    policy_id: str
    task_id: str
    total_budget: float
    verification_reserve: float
    recovery_reserve: float
    continuity_reserve: float
    role_budgets: dict[str, float]
    provider_budgets: dict[str, float]
    tool_budgets: dict[str, float]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class BudgetLedger(SchemaModel):
    """Current budget ledger state for a task."""

    version: str
    ledger_id: str
    task_id: str
    policy_id: str
    spent_total: float
    spent_verification: float
    spent_recovery: float
    spent_continuity: float
    remaining_budget: float
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class BudgetAllocation(SchemaModel):
    """Budget allocation for one category of work."""

    version: str
    allocation_id: str
    task_id: str
    category: str
    allocated_budget: float
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class BudgetEvent(SchemaModel):
    """Budget governance event."""

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
class BudgetConsumptionRecord(SchemaModel):
    """One budget consumption record."""

    version: str
    consumption_id: str
    task_id: str
    category: str
    ref_id: str
    estimated_cost: float
    actual_cost: float
    justification: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


class BudgetManager:
    """Manage task budget policies, ledgers, and cost checks."""

    def initialize_policy(self, task_id: str, preferences: dict[str, str]) -> tuple[BudgetPolicy, BudgetLedger]:
        total_budget = float(preferences.get("max_cost", "1.0"))
        verification_reserve = max(total_budget * 0.2, 0.01)
        recovery_reserve = max(total_budget * 0.15, 0.01)
        continuity_reserve = max(total_budget * 0.1, 0.005)
        policy = BudgetPolicy(
            version="1.0",
            policy_id=f"budget-policy-{uuid4().hex[:10]}",
            task_id=task_id,
            total_budget=total_budget,
            verification_reserve=verification_reserve,
            recovery_reserve=recovery_reserve,
            continuity_reserve=continuity_reserve,
            role_budgets={"Researcher": total_budget * 0.4, "Builder": total_budget * 0.2, "Verifier": total_budget * 0.25},
            provider_budgets={},
            tool_budgets={"file_retrieval": total_budget * 0.1},
        )
        ledger = BudgetLedger(
            version="1.0",
            ledger_id=f"budget-ledger-{uuid4().hex[:10]}",
            task_id=task_id,
            policy_id=policy.policy_id,
            spent_total=0.0,
            spent_verification=0.0,
            spent_recovery=0.0,
            spent_continuity=0.0,
            remaining_budget=total_budget,
        )
        return policy, ledger

    def can_spend(
        self,
        *,
        ledger: BudgetLedger,
        policy: BudgetPolicy,
        estimated_cost: float,
        category: str,
    ) -> tuple[bool, str]:
        remaining_after = ledger.remaining_budget - estimated_cost
        floor = 0.0
        if category not in {"verification", "recovery", "continuity"}:
            floor = policy.verification_reserve + policy.recovery_reserve + policy.continuity_reserve
        if remaining_after < floor:
            return False, "budget_guardrail_blocked"
        return True, "budget_ok"

    def consume(
        self,
        *,
        ledger: BudgetLedger,
        category: str,
        actual_cost: float,
    ) -> BudgetLedger:
        spent_verification = ledger.spent_verification + (actual_cost if category == "verification" else 0.0)
        spent_recovery = ledger.spent_recovery + (actual_cost if category == "recovery" else 0.0)
        spent_continuity = ledger.spent_continuity + (actual_cost if category == "continuity" else 0.0)
        return BudgetLedger(
            version=ledger.version,
            ledger_id=ledger.ledger_id,
            task_id=ledger.task_id,
            policy_id=ledger.policy_id,
            spent_total=ledger.spent_total + actual_cost,
            spent_verification=spent_verification,
            spent_recovery=spent_recovery,
            spent_continuity=spent_continuity,
            remaining_budget=max(ledger.remaining_budget - actual_cost, 0.0),
            updated_at=utc_now(),
        )

    def make_consumption_record(
        self,
        *,
        task_id: str,
        category: str,
        ref_id: str,
        estimated_cost: float,
        actual_cost: float,
        justification: str,
    ) -> BudgetConsumptionRecord:
        return BudgetConsumptionRecord(
            version="1.0",
            consumption_id=f"budget-consumption-{uuid4().hex[:10]}",
            task_id=task_id,
            category=category,
            ref_id=ref_id,
            estimated_cost=estimated_cost,
            actual_cost=actual_cost,
            justification=justification,
        )

    def make_event(self, *, task_id: str, event_type: str, summary: str, payload: dict[str, Any]) -> BudgetEvent:
        return BudgetEvent(
            version="1.0",
            event_id=f"budget-event-{uuid4().hex[:10]}",
            task_id=task_id,
            event_type=event_type,
            summary=summary,
            payload=payload,
        )
