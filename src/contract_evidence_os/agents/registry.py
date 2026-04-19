"""Default specialist role passports."""

from __future__ import annotations

from contract_evidence_os.agents.models import CapabilityPassport


def default_passports() -> dict[str, CapabilityPassport]:
    """Return the built-in specialist passports."""

    passports = {
        "Strategist": CapabilityPassport(
            version="1.0",
            role_name="Strategist",
            allowed_tools=["file_retrieval", "web_intelligence"],
            forbidden_tools=["destructive_shell", "self_modify_core"],
            max_risk_level="moderate",
            approval_scope=["read", "plan"],
            memory_access_scope=["episodic", "semantic", "procedural"],
            prompt_profile="goal-normalization-and-plan-synthesis",
            validation_responsibility="plan coherence",
            output_schema={"type": "object", "required": ["plan_summary"]},
        ),
        "Researcher": CapabilityPassport(
            version="1.0",
            role_name="Researcher",
            allowed_tools=["file_retrieval", "web_intelligence"],
            forbidden_tools=["destructive_shell", "publication"],
            max_risk_level="moderate",
            approval_scope=["read", "execute_low_risk"],
            memory_access_scope=["episodic", "semantic"],
            prompt_profile="evidence-collection-and-source-ranking",
            validation_responsibility="source triangulation",
            output_schema={"type": "object", "required": ["sources"]},
        ),
        "Builder": CapabilityPassport(
            version="1.0",
            role_name="Builder",
            allowed_tools=["shell_patch", "sandbox_exec", "file_retrieval"],
            forbidden_tools=["policy_change", "audit_delete"],
            max_risk_level="moderate",
            approval_scope=["read", "write", "execute_low_risk"],
            memory_access_scope=["episodic", "procedural"],
            prompt_profile="artifact-construction",
            validation_responsibility="artifact assembly",
            output_schema={"type": "object", "required": ["artifacts"]},
        ),
        "Critic": CapabilityPassport(
            version="1.0",
            role_name="Critic",
            allowed_tools=["file_retrieval", "sandbox_exec"],
            forbidden_tools=["shell_patch", "publication"],
            max_risk_level="low",
            approval_scope=["read"],
            memory_access_scope=["episodic", "semantic"],
            prompt_profile="counterexample-search-and-weakness-analysis",
            validation_responsibility="challenge assumptions",
            output_schema={"type": "object", "required": ["concerns"]},
        ),
        "Verifier": CapabilityPassport(
            version="1.0",
            role_name="Verifier",
            allowed_tools=["file_retrieval", "sandbox_exec", "verification_toolchain"],
            forbidden_tools=["shell_patch", "publication"],
            max_risk_level="moderate",
            approval_scope=["read", "execute_low_risk"],
            memory_access_scope=["episodic", "semantic", "policy"],
            prompt_profile="shadow-verification",
            validation_responsibility="fact and evidence validation",
            output_schema={"type": "object", "required": ["validation_report"]},
        ),
        "Archivist": CapabilityPassport(
            version="1.0",
            role_name="Archivist",
            allowed_tools=["file_retrieval"],
            forbidden_tools=["destructive_shell", "publication"],
            max_risk_level="low",
            approval_scope=["read", "memory_promote"],
            memory_access_scope=["episodic", "semantic", "procedural", "policy"],
            prompt_profile="audit-and-memory-curation",
            validation_responsibility="lineage preservation",
            output_schema={"type": "object", "required": ["ledger_refs"]},
        ),
        "Governor": CapabilityPassport(
            version="1.0",
            role_name="Governor",
            allowed_tools=["policy_eval", "file_retrieval"],
            forbidden_tools=["shell_patch", "publication", "self_modify_core"],
            max_risk_level="high",
            approval_scope=["approve", "deny", "policy_read"],
            memory_access_scope=["policy", "semantic"],
            prompt_profile="risk-and-approval-control",
            validation_responsibility="permission and approval decisions",
            output_schema={"type": "object", "required": ["decision"]},
        ),
    }
    return passports
