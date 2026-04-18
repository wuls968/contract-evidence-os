"""Context compaction and tiered continuity loading."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.continuity.models import (
    ContextCompaction,
    ContextTier,
    PromptBudgetAllocation,
)
from contract_evidence_os.continuity.models import NextAction, OpenQuestion
from contract_evidence_os.contracts.models import TaskContract
from contract_evidence_os.planning.models import PlanGraph
from contract_evidence_os.policy.models import ApprovalRequest


@dataclass
class ContinuityLoadingPolicy:
    """Policy-driven context loading rules."""

    total_budget: int = 800

    def allocate(self, role_name: str, contradictions: int, evidence_items: int, approvals: int) -> PromptBudgetAllocation:
        total = self.total_budget
        contract_budget = max(120, total // 5)
        active_plan_budget = max(120, total // 5)
        contradictions_budget = max(80, contradictions * 30)
        evidence_budget = max(120, min(total // 3, evidence_items * 25))
        approvals_budget = max(60, approvals * 25)
        used = contract_budget + active_plan_budget + contradictions_budget + evidence_budget + approvals_budget
        memory_budget = max(40, total - used)
        return PromptBudgetAllocation(
            version="1.0",
            allocation_id=f"budget-{uuid4().hex[:10]}",
            task_id="",
            role_name=role_name,
            total_budget=total,
            contract_budget=contract_budget,
            active_plan_budget=active_plan_budget,
            contradictions_budget=contradictions_budget,
            evidence_budget=evidence_budget,
            approvals_budget=approvals_budget,
            memory_budget=memory_budget,
            created_at=utc_now(),
        )


class ContextCompactor:
    """Compress long execution history into typed continuity packets."""

    def __init__(self, loading_policy: ContinuityLoadingPolicy | None = None) -> None:
        self.loading_policy = loading_policy or ContinuityLoadingPolicy()

    def compact(
        self,
        task_id: str,
        role_name: str,
        contract: TaskContract,
        plan: PlanGraph,
        evidence_delta_summary: str,
        open_questions: list[OpenQuestion],
        next_actions: list[NextAction],
        pending_approvals: list[ApprovalRequest],
        pending_risks: list[str],
        memory_candidates: list[str],
    ) -> tuple[ContextCompaction, PromptBudgetAllocation]:
        contradictions = sum(1 for question in open_questions if "contradiction" in question.why_it_matters.lower())
        budget = self.loading_policy.allocate(
            role_name=role_name,
            contradictions=contradictions,
            evidence_items=len(evidence_delta_summary.splitlines()),
            approvals=len(pending_approvals),
        )
        budget.task_id = task_id

        hot_summary = self._hot_summary(contract, plan, open_questions, next_actions, pending_approvals)
        warm_summary = self._warm_summary(evidence_delta_summary, pending_risks, memory_candidates)
        cold_summary = self._cold_summary(contract, plan)

        compaction = ContextCompaction(
            version="1.0",
            context_id=f"context-{uuid4().hex[:10]}",
            task_id=task_id,
            recent_execution_summary=f"{len([node for node in plan.nodes if node.status == 'completed'])} nodes completed.",
            evidence_summary=evidence_delta_summary,
            unresolved_issues_summary="; ".join(question.why_it_matters for question in open_questions) or "None",
            decision_rationale_summary="; ".join(action.action_summary for action in next_actions[:3]) or "Continue active plan.",
            pending_risks=pending_risks,
            memory_candidates=memory_candidates,
            hot_context=ContextTier(
                version="1.0",
                tier_name="hot",
                summary=hot_summary,
                record_refs=[contract.contract_id, plan.graph_id, *[question.question_id for question in open_questions]],
                token_estimate=min(budget.contract_budget + budget.active_plan_budget, budget.total_budget // 2),
            ),
            warm_context=ContextTier(
                version="1.0",
                tier_name="warm",
                summary=warm_summary,
                record_refs=[*pending_risks, *memory_candidates],
                token_estimate=min(budget.evidence_budget + budget.approvals_budget, budget.total_budget // 3),
            ),
            cold_context=ContextTier(
                version="1.0",
                tier_name="cold",
                summary=cold_summary,
                record_refs=[node.node_id for node in plan.nodes],
                token_estimate=budget.memory_budget,
            ),
            created_at=utc_now(),
        )
        return compaction, budget

    def shape_for_role(self, compaction: ContextCompaction, role_name: str) -> tuple[ContextTier, ContextTier]:
        """Return hot/warm role-shaped tiers."""

        if role_name == "Strategist":
            hot = ContextTier(
                version="1.0",
                tier_name="hot",
                summary=f"Contract and plan deltas: {compaction.hot_context.summary}",
                record_refs=compaction.hot_context.record_refs,
                token_estimate=compaction.hot_context.token_estimate,
            )
            warm = ContextTier(
                version="1.0",
                tier_name="warm",
                summary=f"Rationale and pending risks: {compaction.warm_context.summary}",
                record_refs=compaction.warm_context.record_refs,
                token_estimate=compaction.warm_context.token_estimate,
            )
            return hot, warm
        if role_name == "Researcher":
            return (
                ContextTier(
                    version="1.0",
                    tier_name="hot",
                    summary=f"Evidence frontier and questions: {compaction.evidence_summary} | {compaction.unresolved_issues_summary}",
                    record_refs=compaction.hot_context.record_refs,
                    token_estimate=compaction.hot_context.token_estimate,
                ),
                compaction.warm_context,
            )
        if role_name == "Builder":
            return (
                ContextTier(
                    version="1.0",
                    tier_name="hot",
                    summary=f"Active task slice: {compaction.recent_execution_summary} | {compaction.decision_rationale_summary}",
                    record_refs=compaction.hot_context.record_refs,
                    token_estimate=compaction.hot_context.token_estimate,
                ),
                ContextTier(
                    version="1.0",
                    tier_name="warm",
                    summary=f"Artifacts and risks: {compaction.warm_context.summary}",
                    record_refs=compaction.warm_context.record_refs,
                    token_estimate=compaction.warm_context.token_estimate,
                ),
            )
        if role_name in {"Critic", "Verifier"}:
            return (
                ContextTier(
                    version="1.0",
                    tier_name="hot",
                    summary=f"Claims and unresolved issues: {compaction.evidence_summary} | {compaction.unresolved_issues_summary}",
                    record_refs=compaction.hot_context.record_refs,
                    token_estimate=compaction.hot_context.token_estimate,
                ),
                compaction.warm_context,
            )
        if role_name == "Governor":
            return (
                ContextTier(
                    version="1.0",
                    tier_name="hot",
                    summary=f"Risks and approvals: {compaction.warm_context.summary}",
                    record_refs=compaction.warm_context.record_refs,
                    token_estimate=compaction.hot_context.token_estimate,
                ),
                compaction.cold_context,
            )
        if role_name == "Archivist":
            return (
                ContextTier(
                    version="1.0",
                    tier_name="hot",
                    summary=f"Memory candidates: {', '.join(compaction.memory_candidates) or 'None'}",
                    record_refs=compaction.warm_context.record_refs,
                    token_estimate=compaction.hot_context.token_estimate,
                ),
                compaction.cold_context,
            )
        return compaction.hot_context, compaction.warm_context

    def _hot_summary(
        self,
        contract: TaskContract,
        plan: PlanGraph,
        open_questions: list[OpenQuestion],
        next_actions: list[NextAction],
        pending_approvals: list[ApprovalRequest],
    ) -> str:
        active_nodes = [node.objective for node in plan.nodes if node.status != "completed"]
        return (
            f"Constraints: {', '.join(contract.hard_constraints[:3])}. "
            f"Active nodes: {', '.join(active_nodes[:3]) or 'none'}. "
            f"Open questions: {len(open_questions)}. "
            f"Next actions: {', '.join(action.action_summary for action in next_actions[:2]) or 'none'}. "
            f"Pending approvals: {len(pending_approvals)}."
        )

    def _warm_summary(
        self,
        evidence_delta_summary: str,
        pending_risks: list[str],
        memory_candidates: list[str],
    ) -> str:
        return (
            f"Evidence delta: {evidence_delta_summary}. "
            f"Pending risks: {', '.join(pending_risks) or 'none'}. "
            f"Memory candidates: {', '.join(memory_candidates) or 'none'}."
        )

    def _cold_summary(self, contract: TaskContract, plan: PlanGraph) -> str:
        return (
            f"Goal: {contract.normalized_goal}. "
            f"Plan nodes tracked: {', '.join(node.node_id for node in plan.nodes)}."
        )
