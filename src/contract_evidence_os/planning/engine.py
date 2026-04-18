"""Plan graph generation and local replanning."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from contract_evidence_os.contracts.models import TaskContract
from contract_evidence_os.planning.models import PlanEdge, PlanGraph, PlanNode


@dataclass
class PlanGraphEngine:
    """Create and adjust plan graphs from contracts."""

    version: str = "1.0"

    def generate(self, contract: TaskContract, attachments: list[str]) -> PlanGraph:
        """Generate a dependency-aware multi-node plan graph."""

        attachment_refs = attachments or ["unresolved-source"]
        retrieval_precondition = "attachment exists" if attachments else "source can be located"
        requires_delivery_approval = any(
            token in contract.normalized_goal
            for token in ["publish", "publication", "external", "delete", "destroy"]
        )

        nodes: list[PlanNode] = []
        edges: list[PlanEdge] = []
        extract_node_ids: list[str] = []
        for index, _attachment in enumerate(attachment_refs):
            retrieve_id = f"node-retrieve-source-{index}"
            extract_id = f"node-extract-source-{index}"
            nodes.append(
                PlanNode(
                    version="1.0",
                    node_id=retrieve_id,
                    objective=f"Retrieve evidence source {index + 1}",
                    role_owner="Researcher",
                    dependencies=[],
                    preconditions=[retrieval_precondition],
                    expected_outputs=["source_snapshot"],
                    validation_gate="source_integrity_check",
                    fallback_paths=["retry_with_recovery_engine"],
                    budget_cost=1.0,
                    status="pending",
                    checkpoint_required=True,
                    approval_gate=None,
                    node_category="research",
                    priority=10 + index,
                    attachment_ref=_attachment,
                    handler_name="retrieve_source",
                )
            )
            nodes.append(
                PlanNode(
                    version="1.0",
                    node_id=extract_id,
                    objective=f"Extract grounded constraints from source {index + 1}",
                    role_owner="Researcher",
                    dependencies=[retrieve_id],
                    preconditions=["source snapshot exists"],
                    expected_outputs=["constraint_extractions"],
                    validation_gate="shadow_evidence_coverage",
                    fallback_paths=["replan_recovery_branch"],
                    budget_cost=1.0,
                    status="pending",
                    checkpoint_required=True,
                    approval_gate=None,
                    node_category="research",
                    priority=20 + index,
                    attachment_ref=_attachment,
                    handler_name="extract_source",
                )
            )
            edges.append(self._edge(retrieve_id, extract_id, "depends_on"))
            extract_node_ids.append(extract_id)

        build_id = "node-build-delivery"
        verify_id = "node-verify-delivery"
        memory_id = "node-capture-learning"
        nodes.append(
            PlanNode(
                version="1.0",
                node_id=build_id,
                objective="Build a structured delivery packet from evidence",
                role_owner="Builder",
                dependencies=list(extract_node_ids),
                preconditions=["all extraction nodes completed"],
                expected_outputs=["delivery_packet"],
                validation_gate="builder_schema_check",
                fallback_paths=["replan_recovery_branch"],
                budget_cost=1.5,
                status="pending",
                checkpoint_required=True,
                approval_gate=None,
                node_category="build",
                priority=60,
                handler_name="build_delivery",
            )
        )
        for extract_node_id in extract_node_ids:
            edges.append(self._edge(extract_node_id, build_id, "depends_on"))

        nodes.append(
            PlanNode(
                version="1.0",
                node_id=verify_id,
                objective="Verify delivery against evidence and policy",
                role_owner="Verifier",
                dependencies=[build_id],
                preconditions=["delivery packet exists"],
                expected_outputs=["validation_report"],
                validation_gate="shadow_verification",
                fallback_paths=["branch_and_compare"],
                budget_cost=1.5,
                status="pending",
                checkpoint_required=True,
                approval_gate="governor_review" if requires_delivery_approval else None,
                node_category="verification",
                priority=80,
                handler_name="verify_delivery",
            )
        )
        edges.append(self._edge(build_id, verify_id, "depends_on"))

        nodes.append(
            PlanNode(
                version="1.0",
                node_id=memory_id,
                objective="Capture memory and evolution candidates from the verified trace",
                role_owner="Archivist",
                dependencies=[verify_id],
                preconditions=["validation report exists"],
                expected_outputs=["memory_record", "evolution_candidate"],
                validation_gate="memory_write_policy_check",
                fallback_paths=["skip_memory_capture"],
                budget_cost=0.5,
                status="pending",
                checkpoint_required=True,
                approval_gate=None,
                node_category="memory_evolution",
                priority=95,
                handler_name="capture_learning",
            )
        )
        edges.append(self._edge(verify_id, memory_id, "depends_on"))
        return PlanGraph(version="1.0", graph_id="plan-root", nodes=nodes, edges=edges)

    def replan_local(
        self,
        graph: PlanGraph,
        failed_node_id: str,
        fallback_objective: str,
        *,
        recovery_branch_id: str | None = None,
    ) -> PlanGraph:
        """Rewrite a failed node into an explicit recovery branch."""

        recovery_branch_id = recovery_branch_id or f"branch-recovery-{uuid4().hex[:6]}"
        failed_node = next(node for node in graph.nodes if node.node_id == failed_node_id)
        failed_node.status = "failed"
        recovery_node_id = f"{failed_node_id}-recovery"
        recovery_node = PlanNode(
            version=failed_node.version,
            node_id=recovery_node_id,
            objective=fallback_objective,
            role_owner=failed_node.role_owner,
            dependencies=list(failed_node.dependencies),
            preconditions=list(failed_node.preconditions),
            expected_outputs=list(failed_node.expected_outputs),
            validation_gate=failed_node.validation_gate,
            fallback_paths=list(failed_node.fallback_paths),
            budget_cost=failed_node.budget_cost,
            status="pending",
            checkpoint_required=failed_node.checkpoint_required,
            approval_gate=failed_node.approval_gate,
            node_category="recovery",
            priority=max(failed_node.priority - 5, 1),
            branch_id=recovery_branch_id,
            attachment_ref=failed_node.attachment_ref,
            handler_name=failed_node.handler_name or "recover_node",
        )
        rewritten_nodes: list[PlanNode] = []
        for node in graph.nodes:
            if failed_node_id in node.dependencies:
                dependencies = [recovery_node_id if dependency == failed_node_id else dependency for dependency in node.dependencies]
                node = PlanNode(
                    version=node.version,
                    node_id=node.node_id,
                    objective=node.objective,
                    role_owner=node.role_owner,
                    dependencies=dependencies,
                    preconditions=node.preconditions,
                    expected_outputs=node.expected_outputs,
                    validation_gate=node.validation_gate,
                    fallback_paths=node.fallback_paths,
                    budget_cost=node.budget_cost,
                    status="pending" if node.status == "blocked" else node.status,
                    checkpoint_required=node.checkpoint_required,
                    approval_gate=node.approval_gate,
                    node_category=node.node_category,
                    priority=node.priority,
                    branch_id=recovery_branch_id if node.branch_id == graph.active_branch_id else node.branch_id,
                    attachment_ref=node.attachment_ref,
                    handler_name=node.handler_name,
                )
            rewritten_nodes.append(node)
        rewritten_nodes.append(recovery_node)
        node_index = {node.node_id: node for node in rewritten_nodes}
        changed = True
        while changed:
            changed = False
            for node in rewritten_nodes:
                if node.node_id == recovery_node_id:
                    continue
                if any(node_index.get(dependency) is not None and node_index[dependency].branch_id == recovery_branch_id for dependency in node.dependencies):
                    if node.branch_id != recovery_branch_id:
                        node.branch_id = recovery_branch_id
                        if node.status not in {"completed", "failed"}:
                            node.status = "pending"
                        changed = True

        rewritten_edges = list(graph.edges)
        for dependency in recovery_node.dependencies:
            rewritten_edges.append(self._edge(dependency, recovery_node_id, "depends_on"))
        for node in rewritten_nodes:
            if recovery_node_id in node.dependencies:
                rewritten_edges.append(self._edge(recovery_node_id, node.node_id, "depends_on"))
        return PlanGraph(
            version=graph.version,
            graph_id=f"{graph.graph_id}-replanned",
            active_branch_id=recovery_branch_id,
            nodes=rewritten_nodes,
            edges=rewritten_edges,
        )

    def _edge(self, source_node_id: str, target_node_id: str, edge_type: str) -> PlanEdge:
        return PlanEdge(
            version="1.0",
            edge_id=f"edge-{source_node_id}-to-{target_node_id}",
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
        )
