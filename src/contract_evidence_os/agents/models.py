"""Role and capability models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contract_evidence_os.base import SchemaModel


@dataclass
class CapabilityPassport(SchemaModel):
    """Least-privilege capability envelope for a specialist role."""

    version: str
    role_name: str
    allowed_tools: list[str]
    forbidden_tools: list[str]
    max_risk_level: str
    approval_scope: list[str]
    memory_access_scope: list[str]
    prompt_profile: str
    validation_responsibility: str
    output_schema: dict[str, Any]

    def __post_init__(self) -> None:
        self.validate()
