"""Contract lattice operations."""

from __future__ import annotations

from dataclasses import dataclass

from contract_evidence_os.contracts.models import ContractLattice, TaskContract


@dataclass
class ContractLatticeManager:
    """Manage root, derived, and conflicting contracts."""

    version: str = "1.0"

    def create_root(self, contract: TaskContract) -> ContractLattice:
        return ContractLattice(
            version=self.version,
            root_contract_id=contract.contract_id,
            contract_ids=[contract.contract_id],
            inheritance={contract.contract_id: []},
            conflicts=[],
        )

    def attach_subcontract(
        self,
        lattice: ContractLattice,
        parent: TaskContract,
        subcontract: TaskContract,
    ) -> ContractLattice:
        if subcontract.contract_id not in lattice.contract_ids:
            lattice.contract_ids.append(subcontract.contract_id)
        lattice.inheritance.setdefault(parent.contract_id, [])
        if subcontract.contract_id not in lattice.inheritance[parent.contract_id]:
            lattice.inheritance[parent.contract_id].append(subcontract.contract_id)
        return lattice

    def register_conflict(self, lattice: ContractLattice, contract_id: str) -> ContractLattice:
        if contract_id not in lattice.conflicts:
            lattice.conflicts.append(contract_id)
        return lattice

    def inherited_constraints(self, parent: TaskContract, child: TaskContract) -> list[str]:
        return sorted(set(parent.hard_constraints + child.hard_constraints))
