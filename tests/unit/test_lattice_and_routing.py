from contract_evidence_os.contracts.compiler import ContractCompiler
from contract_evidence_os.contracts.lattice import ContractLatticeManager
from contract_evidence_os.runtime.model_routing import ModelRouter


def test_contract_lattice_tracks_root_and_subcontracts() -> None:
    compiler = ContractCompiler()
    root = compiler.compile(
        goal="Read the attachment and summarize the mandatory constraints.",
        attachments=["/tmp/requirements.txt"],
        preferences={},
        prohibitions=["do not delete audit history"],
    )
    sub = compiler.derive_subcontract(root, "Retrieve primary source evidence.")

    manager = ContractLatticeManager()
    lattice = manager.create_root(root)
    lattice = manager.attach_subcontract(lattice, root, sub)

    assert root.contract_id in lattice.contract_ids
    assert sub.contract_id in lattice.contract_ids
    assert sub.contract_id in lattice.inheritance[root.contract_id]
    assert "ground output in evidence" in manager.inherited_constraints(root, sub)


def test_model_router_selects_cost_quality_profile_by_role_and_risk() -> None:
    router = ModelRouter()

    extraction_route = router.route(role="Researcher", workload="extraction", risk_level="low")
    verification_route = router.route(role="Verifier", workload="critique", risk_level="high")

    assert extraction_route.profile == "fast-extractor"
    assert extraction_route.cost_tier == "low"
    assert verification_route.profile == "deep-verifier"
    assert verification_route.cost_tier == "high"
