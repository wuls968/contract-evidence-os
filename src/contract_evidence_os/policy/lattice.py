"""Policy-as-code permission lattice."""

from __future__ import annotations

from dataclasses import dataclass

from contract_evidence_os.agents.models import CapabilityPassport


@dataclass
class AuthorizationOutcome:
    """Result of a policy authorization check."""

    allowed: bool
    reason: str
    approval_required: bool = False


class PermissionLattice:
    """Enforce least-privilege, risk-aware tool and action use."""

    _risk_order = {"low": 0, "moderate": 1, "high": 2}

    def authorize(
        self,
        passport: CapabilityPassport,
        action: str,
        tool_name: str,
        risk_level: str,
    ) -> AuthorizationOutcome:
        if action == "destructive_action":
            return AuthorizationOutcome(False, "destructive actions require explicit approval", True)
        if tool_name in passport.forbidden_tools:
            return AuthorizationOutcome(False, f"{passport.role_name} forbids tool {tool_name}")
        if tool_name not in passport.allowed_tools:
            return AuthorizationOutcome(False, f"{passport.role_name} is not allowed to use {tool_name}")
        if self._risk_order.get(risk_level, 99) > self._risk_order.get(passport.max_risk_level, -1):
            return AuthorizationOutcome(False, f"risk level {risk_level} exceeds passport limit")
        if action not in passport.approval_scope and action not in {"read", "write"}:
            return AuthorizationOutcome(False, f"action {action} is outside passport scope")
        return AuthorizationOutcome(True, "authorized")
