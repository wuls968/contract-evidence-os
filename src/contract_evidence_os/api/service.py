"""Minimal service facade exposing required entry points."""

from __future__ import annotations

from pathlib import Path

from contract_evidence_os.runtime.service import RuntimeService


class ContractEvidenceAPI(RuntimeService):
    """Thin API façade over the runtime service."""

    def __init__(self, storage_root: Path, **kwargs) -> None:
        super().__init__(storage_root=storage_root, **kwargs)
