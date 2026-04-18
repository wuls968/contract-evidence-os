"""Evidence-layer models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from contract_evidence_os.base import SchemaModel


@dataclass
class SourceRecord(SchemaModel):
    """Metadata about a retrieved source."""

    version: str
    source_id: str
    source_type: str
    locator: str
    retrieved_at: datetime
    credibility: float
    time_relevance: float
    content_hash: str
    snippet: str

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class EvidenceNode(SchemaModel):
    """Atomic evidence item in the graph."""

    version: str
    node_id: str
    node_type: str
    content: str
    confidence: float
    created_at: datetime
    metadata: dict[str, str | int | float | bool | None]

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class EvidenceEdge(SchemaModel):
    """Relationship between evidence nodes."""

    version: str
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class EvidenceGraph(SchemaModel):
    """Trust graph that ties sources, claims, and tests together."""

    version: str
    graph_id: str
    nodes: list[EvidenceNode] = field(default_factory=list)
    edges: list[EvidenceEdge] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ClaimRecord(SchemaModel):
    """Normalized claim tied to supporting evidence."""

    version: str
    claim_id: str
    statement: str
    claim_type: str
    evidence_refs: list[str]
    status: str

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ValidationReport(SchemaModel):
    """Verifier output with findings and contradictions."""

    version: str
    report_id: str
    contract_id: str
    validator: str
    status: str
    confidence: float
    findings: list[str]
    contradictions: list[str]
    evidence_refs: list[str]

    def __post_init__(self) -> None:
        self.validate()
