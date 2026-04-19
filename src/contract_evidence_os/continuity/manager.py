"""Long-horizon continuity generation and reconstruction."""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.continuity.compactor import ContextCompactor
from contract_evidence_os.continuity.models import (
    ContinuityWorkingSet,
    EvidenceDeltaSummary,
    HandoffPacket,
    HandoffPacketVersion,
    HandoffSummarySection,
    NextAction,
    OpenQuestion,
    WorkspaceSnapshot,
)
from contract_evidence_os.contracts.models import ContractLattice, TaskContract
from contract_evidence_os.evidence.models import ClaimRecord, EvidenceGraph, ValidationReport
from contract_evidence_os.memory.models import MemoryRecord
from contract_evidence_os.planning.models import PlanGraph
from contract_evidence_os.policy.models import ApprovalRequest
from contract_evidence_os.storage.repository import SQLiteRepository


@dataclass
class ContinuityManager:
    """Create continuity artifacts and reconstruct execution-ready state."""

    repository: SQLiteRepository
    storage_root: Path
    compactor: ContextCompactor = field(default_factory=ContextCompactor)

    def generate_evidence_delta(
        self,
        task_id: str,
        checkpoint_id: str,
        claims: list[ClaimRecord],
        evidence_graph: EvidenceGraph,
        validation_report: ValidationReport | None,
        receipts: list[str],
    ) -> EvidenceDeltaSummary:
        previous = self.repository.latest_evidence_delta(task_id)
        previous_facts = set() if previous is None else set(previous.new_facts_established)
        current_facts = {claim.statement for claim in claims}
        new_facts = sorted(current_facts - previous_facts)
        strengthened = sorted(statement for statement in current_facts if statement in previous_facts)
        contradictions = sorted(
            node.content for node in evidence_graph.nodes if node.node_type == "contradiction"
        )
        delta = EvidenceDeltaSummary(
            version="1.0",
            delta_id=f"delta-summary-{uuid4().hex[:10]}",
            task_id=task_id,
            checkpoint_id=checkpoint_id,
            new_facts_established=new_facts,
            claims_strengthened=strengthened,
            claims_weakened=[],
            contradictions_discovered=contradictions,
            tests_passed=[] if validation_report is None or validation_report.status != "passed" else [validation_report.report_id],
            tests_failed=[] if validation_report is None or validation_report.status == "passed" else [validation_report.report_id],
            important_artifacts=receipts,
            created_at=utc_now(),
        )
        self.repository.save_evidence_delta(delta)
        return delta

    def refresh_ledgers(
        self,
        task_id: str,
        contract: TaskContract,
        plan: PlanGraph,
        evidence_delta: EvidenceDeltaSummary,
        pending_approvals: list[ApprovalRequest],
        validation_report: ValidationReport | None = None,
    ) -> tuple[list[OpenQuestion], list[NextAction]]:
        open_questions: list[OpenQuestion] = []
        next_actions: list[NextAction] = []

        for node in plan.nodes:
            if node.status == "blocked":
                open_questions.append(
                    OpenQuestion(
                        version="1.0",
                        question_id=f"question-{uuid4().hex[:10]}",
                        contract_id=contract.contract_id,
                        related_plan_node=node.node_id,
                        why_it_matters=f"Blocked node needs resolution: {node.objective}",
                        current_known_evidence=evidence_delta.new_facts_established,
                        missing_evidence=node.expected_outputs,
                        blocking_severity="high",
                        owner_role=node.role_owner,
                        status="open",
                        resolution_notes="",
                    )
                )

        for contradiction in evidence_delta.contradictions_discovered:
            open_questions.append(
                OpenQuestion(
                    version="1.0",
                    question_id=f"question-{uuid4().hex[:10]}",
                    contract_id=contract.contract_id,
                    related_plan_node=None,
                    why_it_matters=f"Contradiction requires adjudication: {contradiction}",
                    current_known_evidence=evidence_delta.new_facts_established,
                    missing_evidence=["contradiction resolution"],
                    blocking_severity="moderate",
                    owner_role="Critic",
                    status="open",
                    resolution_notes="",
                )
            )

        if validation_report is not None and validation_report.status != "passed":
            open_questions.append(
                OpenQuestion(
                    version="1.0",
                    question_id=f"question-{uuid4().hex[:10]}",
                    contract_id=contract.contract_id,
                    related_plan_node="node-reconcile-delivery",
                    why_it_matters="Validation did not pass; delivery remains unsafe.",
                    current_known_evidence=validation_report.findings,
                    missing_evidence=validation_report.contradictions or ["resolution"],
                    blocking_severity="high",
                    owner_role="Verifier",
                    status="open",
                    resolution_notes="",
                )
            )

        for approval in pending_approvals:
            open_questions.append(
                OpenQuestion(
                    version="1.0",
                    question_id=f"question-{uuid4().hex[:10]}",
                    contract_id=contract.contract_id,
                    related_plan_node=approval.plan_node_id,
                    why_it_matters=f"Pending approval blocks action: {approval.action_summary or approval.action}",
                    current_known_evidence=approval.relevant_evidence,
                    missing_evidence=["operator decision"],
                    blocking_severity="high",
                    owner_role="Governor",
                    status="open",
                    resolution_notes="",
                )
            )

        for node in plan.nodes:
            if node.status != "completed":
                next_actions.append(
                    NextAction(
                        version="1.0",
                        action_id=f"action-{uuid4().hex[:10]}",
                        contract_id=contract.contract_id,
                        related_plan_node=node.node_id,
                        action_summary=f"Advance node: {node.objective}",
                        prerequisites=node.preconditions,
                        suggested_role=node.role_owner,
                        suggested_toolchain=node.expected_outputs,
                        confidence=0.8,
                        urgency="high" if node.dependencies else "medium",
                        status="pending",
                    )
                )
                break

        if pending_approvals:
            next_actions.insert(
                0,
                NextAction(
                    version="1.0",
                    action_id=f"action-{uuid4().hex[:10]}",
                    contract_id=contract.contract_id,
                    related_plan_node=pending_approvals[0].plan_node_id,
                    action_summary="Resolve pending approval request",
                    prerequisites=["operator review"],
                    suggested_role="Governor",
                    suggested_toolchain=["approval_inbox"],
                    confidence=1.0,
                    urgency="high",
                    status="pending",
                ),
            )

        self.repository.save_open_questions(task_id, open_questions)
        self.repository.save_next_actions(task_id, next_actions)
        return open_questions, next_actions

    def snapshot_workspace(
        self,
        task_id: str,
        audit_refs: list[str],
        evidence_refs: list[str],
        memory_refs: list[str],
        recent_tool_outputs: list[str],
    ) -> WorkspaceSnapshot:
        snapshot = WorkspaceSnapshot(
            version="1.0",
            snapshot_id=f"snapshot-{uuid4().hex[:10]}",
            task_id=task_id,
            active_artifacts=[str(self.storage_root / "contract_evidence_os.sqlite3")],
            key_generated_files=[],
            recent_tool_outputs=recent_tool_outputs,
            environment_metadata={
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "storage_root": str(self.storage_root),
            },
            audit_refs=audit_refs,
            evidence_refs=evidence_refs,
            memory_refs=memory_refs,
            created_at=utc_now(),
        )
        self.repository.save_workspace_snapshot(snapshot)
        return snapshot

    def generate_handoff_packet(
        self,
        task_id: str,
        contract: TaskContract,
        plan: PlanGraph,
        lattice: ContractLattice,
        evidence_delta: EvidenceDeltaSummary,
        open_questions: list[OpenQuestion],
        next_actions: list[NextAction],
        pending_approvals: list[ApprovalRequest],
        pending_memories: list[MemoryRecord],
        recommended_strategy: str,
    ) -> HandoffPacket:
        completed_nodes = [node.node_id for node in plan.nodes if node.status == "completed"]
        blocked_nodes = [node.node_id for node in plan.nodes if node.status == "blocked"]
        sections = [
            HandoffSummarySection(
                version="1.0",
                section_id=f"section-{uuid4().hex[:10]}",
                title="State",
                content=f"Completed nodes: {', '.join(completed_nodes) or 'none'}; blocked nodes: {', '.join(blocked_nodes) or 'none'}.",
                priority=1,
            ),
            HandoffSummarySection(
                version="1.0",
                section_id=f"section-{uuid4().hex[:10]}",
                title="Evidence Delta",
                content=f"New facts: {', '.join(evidence_delta.new_facts_established) or 'none'}.",
                priority=2,
            ),
            HandoffSummarySection(
                version="1.0",
                section_id=f"section-{uuid4().hex[:10]}",
                title="Next Actions",
                content=", ".join(action.action_summary for action in next_actions[:3]) or "none",
                priority=3,
            ),
        ]
        packet = HandoffPacket(
            version="1.0",
            packet_id=f"handoff-{uuid4().hex[:10]}",
            task_id=task_id,
            contract_id=contract.contract_id,
            contract_version=contract.version,
            plan_graph_id=plan.graph_id,
            completed_nodes=completed_nodes,
            blocked_nodes=blocked_nodes,
            next_recommended_actions=[action.action_summary for action in next_actions[:3]],
            open_question_ids=[question.question_id for question in open_questions],
            unresolved_contradictions=evidence_delta.contradictions_discovered,
            key_evidence_delta_id=evidence_delta.delta_id,
            current_risk_state=contract.risk_level,
            pending_approval_ids=[approval.request_id for approval in pending_approvals],
            pending_memory_ids=[memory.memory_id for memory in pending_memories],
            recommended_strategy=recommended_strategy,
            summary_sections=sections,
            created_at=utc_now(),
        )
        version = HandoffPacketVersion(
            version="1.0",
            packet_version_id=f"handoff-version-{uuid4().hex[:10]}",
            packet_id=packet.packet_id,
            task_id=task_id,
            contract_version=contract.version,
            created_at=utc_now(),
        )
        self.repository.save_handoff_packet(packet, version, sections)
        return packet

    def compact_context(
        self,
        task_id: str,
        role_name: str,
        contract: TaskContract,
        plan: PlanGraph,
        evidence_delta: EvidenceDeltaSummary,
        open_questions: list[OpenQuestion],
        next_actions: list[NextAction],
        pending_approvals: list[ApprovalRequest],
        pending_memories: list[MemoryRecord],
        recommended_strategy: str,
    ):
        compaction, budget = self.compactor.compact(
            task_id=task_id,
            role_name=role_name,
            contract=contract,
            plan=plan,
            evidence_delta_summary=self._format_evidence_delta(evidence_delta),
            open_questions=open_questions,
            next_actions=next_actions,
            pending_approvals=pending_approvals,
            pending_risks=[contract.risk_level],
            memory_candidates=[memory.summary for memory in pending_memories],
        )
        self.repository.save_context_compaction(compaction)
        self.repository.save_prompt_budget_allocation(budget)
        return compaction, budget

    def reconstruct_working_set(self, task_id: str, role_name: str) -> ContinuityWorkingSet:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        contract = self.repository.load_contract(str(task["contract_id"]))
        plan = self.repository.load_plan(task_id)
        handoff = self.repository.latest_handoff_packet(task_id)
        compaction = self.repository.latest_context_compaction(task_id)
        if plan is None or handoff is None or compaction is None:
            raise KeyError(f"missing continuity state for {task_id}")
        open_questions = self.repository.list_open_questions(task_id)
        next_actions = self.repository.list_next_actions(task_id)
        approvals = self.repository.list_approval_requests(task_id=task_id, status="pending")
        hot, warm = self.compactor.shape_for_role(compaction, role_name)
        evidence_graph = self.repository.load_evidence_graph(task_id)
        evidence_frontier_ids = [node.node_id for node in evidence_graph.nodes[-5:]]
        working_set = ContinuityWorkingSet(
            version="1.0",
            working_set_id=f"working-set-{uuid4().hex[:10]}",
            task_id=task_id,
            contract_id=contract.contract_id,
            plan_graph_id=plan.graph_id,
            handoff_packet_id=handoff.packet_id,
            active_plan_nodes=[node.node_id for node in plan.nodes if node.status != "completed"],
            blocked_plan_nodes=[node.node_id for node in plan.nodes if node.status == "blocked"],
            evidence_frontier_ids=evidence_frontier_ids,
            open_question_ids=[question.question_id for question in open_questions],
            next_action_ids=[action.action_id for action in next_actions],
            pending_approval_ids=[approval.request_id for approval in approvals],
            pending_risks=[contract.risk_level],
            recommended_strategy=handoff.recommended_strategy,
            hot_context=hot,
            warm_context=warm,
            created_at=utc_now(),
        )
        self.repository.save_continuity_working_set(working_set)
        return working_set

    def _format_evidence_delta(self, delta: EvidenceDeltaSummary) -> str:
        return (
            f"new_facts={len(delta.new_facts_established)}; "
            f"strengthened={len(delta.claims_strengthened)}; "
            f"contradictions={len(delta.contradictions_discovered)}; "
            f"tests_passed={len(delta.tests_passed)}; "
            f"tests_failed={len(delta.tests_failed)}"
        )
