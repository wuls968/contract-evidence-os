"""Shared console types and constants."""

from __future__ import annotations

from dataclasses import dataclass

from contract_evidence_os.console.models import BrowserSession, UserAccount


ROLE_SCOPES: dict[str, list[str]] = {
    "admin": ["viewer", "operator", "approver", "policy-admin", "runtime-admin", "evaluator"],
    "operator": ["viewer", "operator", "approver"],
    "reviewer": ["viewer", "approver", "evaluator"],
    "viewer": ["viewer"],
}


def _slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-") or "provider"


@dataclass
class SessionPrincipal:
    user: UserAccount
    roles: list[str]
    scopes: list[str]
    session: BrowserSession
