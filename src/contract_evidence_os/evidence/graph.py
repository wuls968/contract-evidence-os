"""Evidence graph construction helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.evidence.models import (
    ClaimRecord,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    SourceRecord,
)


@dataclass
class EvidenceBuilder:
    """Build and extend evidence graphs from tool outputs."""

    graph: EvidenceGraph = field(
        default_factory=lambda: EvidenceGraph(version="1.0", graph_id="evidence-root")
    )
    claims: list[ClaimRecord] = field(default_factory=list)

    def add_source(self, source: SourceRecord) -> EvidenceNode:
        node = EvidenceNode(
            version="1.0",
            node_id=f"evidence-{uuid4().hex[:10]}",
            node_type="source",
            content=source.locator,
            confidence=source.credibility,
            created_at=utc_now(),
            metadata={"source_id": source.source_id},
        )
        self.graph.nodes.append(node)
        return node

    def add_extractions(self, source_node: EvidenceNode, statements: list[str]) -> list[EvidenceNode]:
        extraction_nodes: list[EvidenceNode] = []
        for statement in statements:
            extraction_node = EvidenceNode(
                version="1.0",
                node_id=f"evidence-{uuid4().hex[:10]}",
                node_type="extraction",
                content=statement,
                confidence=0.9,
                created_at=utc_now(),
                metadata={"source_node_id": source_node.node_id},
            )
            edge = EvidenceEdge(
                version="1.0",
                edge_id=f"eedge-{uuid4().hex[:10]}",
                source_node_id=source_node.node_id,
                target_node_id=extraction_node.node_id,
                edge_type="derived_from",
            )
            claim = ClaimRecord(
                version="1.0",
                claim_id=f"claim-{uuid4().hex[:10]}",
                statement=statement,
                claim_type="fact",
                evidence_refs=[extraction_node.node_id],
                status="supported",
            )
            self.graph.nodes.append(extraction_node)
            self.graph.edges.append(edge)
            self.claims.append(claim)
            extraction_nodes.append(extraction_node)
        return extraction_nodes
