"""Practical scoped authn/authz and replay protection for the control plane."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from contract_evidence_os.base import SchemaModel, utc_now


@dataclass
class AuthScope(SchemaModel):
    """Named authorization scope."""

    version: str
    scope_name: str
    description: str
    sensitive_actions: list[str]

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class AuthPrincipal(SchemaModel):
    """Authenticated actor identity."""

    version: str
    principal_id: str
    principal_name: str
    principal_type: str
    scopes: list[str]
    status: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class AuthCredential(SchemaModel):
    """Credential bound to a principal."""

    version: str
    credential_id: str
    principal_id: str
    token_hash: str
    scopes: list[str]
    status: str
    issued_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    description: str = ""

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class AuthSession(SchemaModel):
    """Authenticated request/session context."""

    version: str
    session_id: str
    principal_id: str
    credential_id: str
    scopes: list[str]
    request_id: str
    authenticated_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class AuthEvent(SchemaModel):
    """Audit-linked authentication or authorization event."""

    version: str
    event_id: str
    principal_id: str
    credential_id: str
    request_id: str
    action: str
    status: str
    reason: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class RevokedCredentialRecord(SchemaModel):
    """Revocation record for a previously-issued credential."""

    version: str
    revocation_id: str
    credential_id: str
    reason: str
    revoked_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ControlPlaneRequestRecord(SchemaModel):
    """Replay-protected control-plane request record."""

    version: str
    request_id: str
    principal_id: str
    action: str
    nonce: str
    idempotency_key: str
    sensitive: bool
    accepted: bool
    created_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ServicePrincipal(SchemaModel):
    """Typed service identity for runtime roles."""

    version: str
    principal_id: str
    service_name: str
    service_role: str
    scopes: list[str]
    status: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ServiceCredential(SchemaModel):
    """Credential bound to a service principal."""

    version: str
    credential_id: str
    principal_id: str
    token_hash: str
    scopes: list[str]
    status: str
    issued_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    rotated_from: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ServiceTrustRecord(SchemaModel):
    """Trust boundary for one service principal."""

    version: str
    trust_id: str
    principal_id: str
    allowed_hosts: list[str]
    allow_remote_registration: bool
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class CredentialRotationRecord(SchemaModel):
    """Rotation record between old and new credentials."""

    version: str
    rotation_id: str
    old_credential_id: str
    new_credential_id: str
    reason: str
    rotated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class AuthFailureEvent(SchemaModel):
    """Authentication or authorization failure event."""

    version: str
    event_id: str
    principal_id: str
    action: str
    failure_type: str
    reason: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class AuthDecision:
    """Authorization outcome for one action."""

    allowed: bool
    reason: str


@dataclass
class RequestGuardResult:
    """Replay-protection decision for one control-plane request."""

    accepted: bool
    reason: str


class AuthManager:
    """Issue credentials, authenticate callers, authorize actions, and prevent replay."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository
        self._ensure_default_scopes()

    def issue_credential(
        self,
        *,
        principal_name: str,
        principal_type: str,
        scopes: list[str],
        expires_at: datetime | None = None,
        token: str | None = None,
        description: str = "",
    ) -> tuple[AuthCredential, str]:
        principal = AuthPrincipal(
            version="1.0",
            principal_id=f"principal-{uuid4().hex[:10]}",
            principal_name=principal_name,
            principal_type=principal_type,
            scopes=scopes,
            status="active",
        )
        self.repository.save_auth_principal(principal)
        raw_token = token or secrets.token_urlsafe(24)
        credential = AuthCredential(
            version="1.0",
            credential_id=f"credential-{uuid4().hex[:10]}",
            principal_id=principal.principal_id,
            token_hash=self._hash(raw_token),
            scopes=scopes,
            status="active",
            expires_at=expires_at,
            description=description,
        )
        self.repository.save_auth_credential(credential)
        return credential, raw_token

    def bootstrap_credential(
        self,
        *,
        principal_name: str,
        principal_type: str,
        scopes: list[str],
        token: str,
    ) -> AuthCredential:
        existing = self.repository.load_auth_credential_by_hash(self._hash(token))
        if existing is not None:
            return existing
        credential, _ = self.issue_credential(
            principal_name=principal_name,
            principal_type=principal_type,
            scopes=scopes,
            token=token,
            description="bootstrap credential",
        )
        return credential

    def issue_service_credential(
        self,
        *,
        service_name: str,
        service_role: str,
        scopes: list[str],
        allowed_hosts: list[str] | None = None,
        expires_at: datetime | None = None,
        token: str | None = None,
        description: str = "",
    ) -> tuple[ServiceCredential, str]:
        principal = ServicePrincipal(
            version="1.0",
            principal_id=f"service-principal-{uuid4().hex[:10]}",
            service_name=service_name,
            service_role=service_role,
            scopes=scopes,
            status="active",
        )
        self.repository.save_service_principal(principal)
        auth_principal = AuthPrincipal(
            version="1.0",
            principal_id=principal.principal_id,
            principal_name=service_name,
            principal_type="service",
            scopes=scopes,
            status="active",
            created_at=principal.created_at,
        )
        self.repository.save_auth_principal(auth_principal)
        raw_token = token or secrets.token_urlsafe(24)
        credential = ServiceCredential(
            version="1.0",
            credential_id=f"service-credential-{uuid4().hex[:10]}",
            principal_id=principal.principal_id,
            token_hash=self._hash(raw_token),
            scopes=scopes,
            status="active",
            issued_at=utc_now(),
            expires_at=expires_at,
            description=description,
        )
        self.repository.save_service_credential(credential)
        self.repository.save_auth_credential(
            AuthCredential(
                version="1.0",
                credential_id=credential.credential_id,
                principal_id=credential.principal_id,
                token_hash=credential.token_hash,
                scopes=scopes,
                status="active",
                issued_at=credential.issued_at,
                expires_at=expires_at,
                description=description,
            )
        )
        self.repository.save_service_trust_record(
            ServiceTrustRecord(
                version="1.0",
                trust_id=f"service-trust-{uuid4().hex[:10]}",
                principal_id=principal.principal_id,
                allowed_hosts=[] if allowed_hosts is None else allowed_hosts,
                allow_remote_registration=service_role in {"worker", "dispatcher"},
                created_at=principal.created_at,
            )
        )
        return credential, raw_token

    def rotate_credential(
        self,
        credential_id: str,
        *,
        reason: str,
        expires_at: datetime | None = None,
    ) -> tuple[AuthCredential | ServiceCredential | None, str]:
        current = self.repository.load_auth_credential(credential_id)
        if current is None:
            return None, ""
        principal = self.repository.load_auth_principal(current.principal_id)
        if principal is None:
            return None, ""
        raw_token = secrets.token_urlsafe(24)
        if principal.principal_type == "service":
            service_principal = self.repository.load_service_principal(principal.principal_id)
            new_credential, raw_token = self.issue_service_credential(
                service_name=principal.principal_name,
                service_role="service" if service_principal is None else service_principal.service_role,
                scopes=current.scopes,
                expires_at=expires_at,
                token=raw_token,
                description=f"rotated from {credential_id}",
            )
            self.revoke_credential(credential_id, reason=reason)
            self.repository.save_credential_rotation_record(
                CredentialRotationRecord(
                    version="1.0",
                    rotation_id=f"credential-rotation-{uuid4().hex[:10]}",
                    old_credential_id=credential_id,
                    new_credential_id=new_credential.credential_id,
                    reason=reason,
                )
            )
            return new_credential, raw_token
        new_credential, raw_token = self.issue_credential(
            principal_name=principal.principal_name,
            principal_type=principal.principal_type,
            scopes=current.scopes,
            expires_at=expires_at,
            token=raw_token,
            description=f"rotated from {credential_id}",
        )
        self.revoke_credential(credential_id, reason=reason)
        self.repository.save_credential_rotation_record(
            CredentialRotationRecord(
                version="1.0",
                rotation_id=f"credential-rotation-{uuid4().hex[:10]}",
                old_credential_id=credential_id,
                new_credential_id=new_credential.credential_id,
                reason=reason,
            )
        )
        return new_credential, raw_token

    def authenticate(self, token: str, *, request_id: str, now: datetime | None = None) -> AuthSession | None:
        now = utc_now() if now is None else now
        credential = self.repository.load_auth_credential_by_hash(self._hash(token))
        if credential is None or credential.status != "active":
            self.repository.save_auth_failure_event(
                AuthFailureEvent(
                    version="1.0",
                    event_id=f"auth-failure-{uuid4().hex[:10]}",
                    principal_id="unknown",
                    action="authenticate",
                    failure_type="invalid_credential",
                    reason="credential missing or inactive",
                    created_at=now,
                )
            )
            return None
        if credential.expires_at is not None and credential.expires_at <= now:
            self.repository.save_auth_failure_event(
                AuthFailureEvent(
                    version="1.0",
                    event_id=f"auth-failure-{uuid4().hex[:10]}",
                    principal_id=credential.principal_id,
                    action="authenticate",
                    failure_type="expired_credential",
                    reason="credential expired",
                    created_at=now,
                )
            )
            return None
        if self.repository.load_revoked_credential(credential.credential_id) is not None:
            self.repository.save_auth_failure_event(
                AuthFailureEvent(
                    version="1.0",
                    event_id=f"auth-failure-{uuid4().hex[:10]}",
                    principal_id=credential.principal_id,
                    action="authenticate",
                    failure_type="revoked_credential",
                    reason="credential revoked",
                    created_at=now,
                )
            )
            return None
        session = AuthSession(
            version="1.0",
            session_id=f"auth-session-{uuid4().hex[:10]}",
            principal_id=credential.principal_id,
            credential_id=credential.credential_id,
            scopes=credential.scopes,
            request_id=request_id,
            authenticated_at=now,
            expires_at=credential.expires_at,
        )
        self.repository.save_auth_session(session)
        self.repository.save_auth_event(
            AuthEvent(
                version="1.0",
                event_id=f"auth-event-{uuid4().hex[:10]}",
                principal_id=session.principal_id,
                credential_id=session.credential_id,
                request_id=request_id,
                action="authenticate",
                status="accepted",
                reason="credential authenticated",
                created_at=now,
            )
        )
        return session

    def authorize(self, session: AuthSession, *, required_scopes: list[str], action: str) -> AuthDecision:
        allowed = any(scope in session.scopes for scope in required_scopes)
        missing = [scope for scope in required_scopes if scope not in session.scopes]
        decision = AuthDecision(allowed=allowed, reason="authorized" if allowed else f"missing scopes: {', '.join(missing)}")
        self.repository.save_auth_event(
            AuthEvent(
                version="1.0",
                event_id=f"auth-event-{uuid4().hex[:10]}",
                principal_id=session.principal_id,
                credential_id=session.credential_id,
                request_id=session.request_id,
                action=action,
                status="accepted" if decision.allowed else "forbidden",
                reason=decision.reason,
            )
        )
        if not decision.allowed:
            self.repository.save_auth_failure_event(
                AuthFailureEvent(
                    version="1.0",
                    event_id=f"auth-failure-{uuid4().hex[:10]}",
                    principal_id=session.principal_id,
                    action=action,
                    failure_type="forbidden",
                    reason=decision.reason,
                )
            )
        return decision

    def record_request(
        self,
        *,
        session: AuthSession,
        request_id: str,
        nonce: str,
        idempotency_key: str,
        action: str,
        sensitive: bool,
        now: datetime | None = None,
        replay_window_seconds: int = 300,
    ) -> RequestGuardResult:
        now = utc_now() if now is None else now
        if not request_id or (sensitive and not nonce):
            return RequestGuardResult(accepted=False, reason="missing_replay_protection")
        existing_request = self.repository.load_control_plane_request(request_id=request_id)
        existing_nonce = None if not nonce else self.repository.load_control_plane_request(nonce=nonce)
        existing_idempotency = None if not idempotency_key else self.repository.load_control_plane_request(idempotency_key=idempotency_key)
        if existing_request is not None or (sensitive and existing_nonce is not None) or (sensitive and existing_idempotency is not None):
            self.repository.save_auth_event(
                AuthEvent(
                    version="1.0",
                    event_id=f"auth-event-{uuid4().hex[:10]}",
                    principal_id=session.principal_id,
                    credential_id=session.credential_id,
                    request_id=request_id,
                    action=action,
                    status="rejected",
                    reason="replayed_request",
                    created_at=now,
                )
            )
            return RequestGuardResult(accepted=False, reason="replayed_request")
        self.repository.save_control_plane_request(
            ControlPlaneRequestRecord(
                version="1.0",
                request_id=request_id,
                principal_id=session.principal_id,
                action=action,
                nonce=nonce,
                idempotency_key=idempotency_key,
                sensitive=sensitive,
                accepted=True,
                created_at=now,
                expires_at=now + timedelta(seconds=replay_window_seconds),
            )
        )
        return RequestGuardResult(accepted=True, reason="accepted")

    def revoke_credential(self, credential_id: str, *, reason: str, revoked_at: datetime | None = None) -> RevokedCredentialRecord:
        revoked_at = utc_now() if revoked_at is None else revoked_at
        record = RevokedCredentialRecord(
            version="1.0",
            revocation_id=f"credential-revocation-{uuid4().hex[:10]}",
            credential_id=credential_id,
            reason=reason,
            revoked_at=revoked_at,
        )
        credential = self.repository.load_auth_credential(credential_id)
        if credential is not None:
            credential.status = "revoked"
            self.repository.save_auth_credential(credential)
        self.repository.save_revoked_credential(record)
        return record

    def _ensure_default_scopes(self) -> None:
        if self.repository.list_auth_scopes():
            return
        for scope_name, description, sensitive_actions in [
            ("viewer", "Read-only operator access", []),
            ("operator", "Operational control", ["pause_task"]),
            ("approver", "Approval decisions", ["approval_decision"]),
            ("policy-admin", "Policy promotion and rollback", ["policy_promote", "policy_rollback"]),
            ("runtime-admin", "Runtime and queue control", ["set_drain_mode", "disable_provider"]),
            ("evaluator", "Evaluation and benchmark actions", ["run_eval"]),
            ("worker-service", "Worker dispatch and heartbeat", ["queue_dispatch"]),
        ]:
            self.repository.save_auth_scope(
                AuthScope(
                    version="1.0",
                    scope_name=scope_name,
                    description=description,
                    sensitive_actions=sensitive_actions,
                )
            )

    def _hash(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
