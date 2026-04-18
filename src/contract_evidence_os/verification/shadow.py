"""Shadow verification lane."""

from __future__ import annotations

from uuid import uuid4

from contract_evidence_os.contracts.models import TaskContract
from contract_evidence_os.evidence.models import EvidenceGraph, ValidationReport


class ShadowVerifier:
    """Challenge the main lane before delivery."""

    def verify(
        self,
        contract: TaskContract,
        evidence_graph: EvidenceGraph | None,
        delivery_claims: list[dict[str, object]],
    ) -> ValidationReport:
        findings: list[str] = []
        contradictions: list[str] = []
        evidence_refs: list[str] = []

        if evidence_graph is None or not evidence_graph.nodes:
            findings.append("No evidence graph available for validation.")
            return ValidationReport(
                version="1.0",
                report_id=f"validation-{uuid4().hex[:10]}",
                contract_id=contract.contract_id,
                validator="ShadowVerifier",
                status="blocked",
                confidence=0.0,
                findings=findings,
                contradictions=contradictions,
                evidence_refs=evidence_refs,
            )

        node_types = [node.node_type for node in evidence_graph.nodes]
        if "source" not in node_types:
            findings.append("Required source evidence is missing.")
        if any("extraction" in requirement for requirement in contract.evidence_requirements) and "extraction" not in node_types:
            findings.append("Required extraction evidence is missing.")

        for claim in delivery_claims:
            refs = claim.get("evidence_refs", [])
            if not refs:
                contradictions.append(f"Claim lacks evidence refs: {claim.get('statement', '<unknown>')}")
            else:
                evidence_refs.extend(str(ref) for ref in refs)

        status = "passed" if not findings and not contradictions else "blocked"
        if status == "passed":
            findings.append("Evidence coverage satisfied.")
        return ValidationReport(
            version="1.0",
            report_id=f"validation-{uuid4().hex[:10]}",
            contract_id=contract.contract_id,
            validator="ShadowVerifier",
            status=status,
            confidence=0.9 if status == "passed" else 0.3,
            findings=findings,
            contradictions=contradictions,
            evidence_refs=sorted(set(evidence_refs)),
        )
