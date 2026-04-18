"""Task contract compilation."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.contracts.models import ContractDelta, TaskContract


@dataclass
class ContractCompiler:
    """Compile raw task input into typed contracts."""

    version: str = "1.0"

    def compile(
        self,
        goal: str,
        attachments: list[str],
        preferences: dict[str, str],
        prohibitions: list[str],
    ) -> TaskContract:
        normalized_goal = " ".join(goal.lower().split())
        deliverables = ["structured_summary"] if "summar" in normalized_goal else ["task_output"]
        hard_constraints = ["ground output in evidence", "respect explicit prohibitions"]
        if attachments:
            hard_constraints.append("use provided attachments before external lookup")
        soft_preferences = list(preferences.values()) if preferences else ["clear structure"]
        forbidden_actions = sorted(
            {
                text.strip().lower().rstrip(".")
                for text in prohibitions
                if text.strip()
            }
        )
        success_criteria = [
            "delivery cites evidence references",
            "delivery captures mandatory constraints",
        ]
        failure_conditions = [
            "required evidence missing",
            "permission lattice denies required action",
        ]
        evidence_requirements = ["one source node", "one extraction node", "supported claims"]
        risk_level = self._classify_risk(normalized_goal, forbidden_actions)
        approval_required = ["destructive_action"] if risk_level in {"moderate", "high"} else []
        tool_limits = ["file_retrieval"] if attachments else ["web_intelligence"]
        return TaskContract(
            version=self.version,
            contract_id=f"contract-{uuid4().hex[:10]}",
            user_goal=goal,
            normalized_goal=normalized_goal,
            deliverables=deliverables,
            hard_constraints=hard_constraints,
            soft_preferences=soft_preferences,
            forbidden_actions=forbidden_actions,
            success_criteria=success_criteria,
            failure_conditions=failure_conditions,
            evidence_requirements=evidence_requirements,
            risk_level=risk_level,
            approval_required=approval_required,
            budget_limits={"tool_calls": 4, "tokens": 0},
            time_limits={"seconds": 120},
            tool_limits=tool_limits,
            uncertainty_tolerance="low",
            memory_policy="episodic_first",
            checkpoint_policy="after_each_node",
            evolution_allowed_scope=[
                "prompt_profile",
                "planning_heuristic",
                "tool_routing",
                "validation_strategy",
                "skill_capsule",
                "memory_promotion_rule",
            ],
        )

    def recompile_from_failure(self, contract: TaskContract, failure_feedback: str) -> TaskContract:
        """Produce a refined contract after failure feedback."""

        refined = contract.to_dict()
        refined["version"] = f"{contract.version}.1"
        refined["success_criteria"] = contract.success_criteria + [failure_feedback]
        return TaskContract.from_dict(refined)

    def derive_subcontract(self, contract: TaskContract, objective: str) -> TaskContract:
        """Create a constrained subcontract from a root contract."""

        payload = contract.to_dict()
        payload["contract_id"] = f"{contract.contract_id}-sub-{uuid4().hex[:4]}"
        payload["user_goal"] = objective
        payload["normalized_goal"] = objective.lower()
        return TaskContract.from_dict(payload)

    def diff(self, previous: TaskContract, new: TaskContract, reason: str, author: str) -> ContractDelta:
        """Create a delta between two contract versions."""

        changed_fields = [
            key for key, value in new.to_dict().items() if previous.to_dict().get(key) != value
        ]
        return ContractDelta(
            version="1.0",
            delta_id=f"delta-{uuid4().hex[:8]}",
            contract_id=new.contract_id,
            previous_version=previous.version,
            new_version=new.version,
            changed_fields=changed_fields,
            reason=reason,
            author=author,
            timestamp=utc_now(),
        )

    def _classify_risk(self, goal: str, forbidden_actions: list[str]) -> str:
        if any(word in goal for word in ["delete", "destroy", "publish", "external"]):
            return "high"
        if forbidden_actions:
            return "moderate"
        return "low"
