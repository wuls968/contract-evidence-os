"""Recovery-layer models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from contract_evidence_os.base import SchemaModel


@dataclass
class CheckpointRecord(SchemaModel):
    """Checkpoint metadata for execution recovery."""

    version: str
    checkpoint_id: str
    task_id: str
    plan_node_id: str
    state_ref: str
    created_at: datetime
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class IncidentReport(SchemaModel):
    """Structured failure or anomaly record."""

    version: str
    incident_id: str
    task_id: str
    incident_type: str
    severity: str
    summary: str
    recovery_attempted: bool
    resolution: str
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()
