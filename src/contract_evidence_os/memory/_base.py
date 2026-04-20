"""Shared memory subservice behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from contract_evidence_os.memory.matrix import MemoryMatrix


class MemorySubservice:
    """Base class for decomposed memory-matrix subservices."""

    def __init__(self, owner: "MemoryMatrix") -> None:
        self.owner = owner

    def __getattr__(self, name: str) -> Any:
        return getattr(self.owner, name)

    @property
    def repository(self) -> Any:
        return self.owner.repository

    @property
    def artifact_root(self) -> Any:
        return self.owner.artifact_root

    @property
    def shared_artifact_root(self) -> Any:
        return self.owner.shared_artifact_root
