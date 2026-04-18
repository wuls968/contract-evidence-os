"""Stronger service trust mode with HMAC-signed requests."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4

from contract_evidence_os.base import SchemaModel, utc_now
from contract_evidence_os.runtime.shared_state import NetworkIdentityRecord


@dataclass
class ServiceTrustPolicy(SchemaModel):
    version: str
    policy_id: str
    trust_mode: str
    require_nonce: bool
    max_clock_skew_seconds: int
    signed_headers: list[str]
    allowed_networks: list[str]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class TrustBoundaryDescriptor(SchemaModel):
    version: str
    boundary_id: str
    boundary_name: str
    trusted_proxy_headers: list[str]
    enforce_loopback_admin: bool
    allow_service_assertion: bool
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class CredentialBindingRecord(SchemaModel):
    version: str
    binding_id: str
    credential_id: str
    principal_id: str
    trust_policy_id: str
    status: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SecurityIncidentRecord(SchemaModel):
    version: str
    incident_id: str
    principal_id: str
    credential_id: str
    incident_type: str
    summary: str
    source_address: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class TrustReplayRecord(SchemaModel):
    version: str
    replay_id: str
    credential_id: str
    request_id: str
    nonce: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class TrustDecision:
    accepted: bool
    reason: str


class HMACTrustManager:
    """Bind service credentials to HMAC policies and verify signed requests."""

    def __init__(self, *, repository: Any, now_factory: Callable[[], datetime] = utc_now) -> None:
        self.repository = repository
        self.now_factory = now_factory

    def bind_service_credential(
        self,
        *,
        credential_id: str,
        principal_id: str,
        trust_policy: ServiceTrustPolicy,
    ) -> CredentialBindingRecord:
        self.repository.save_service_trust_policy(trust_policy)
        binding = CredentialBindingRecord(
            version="1.0",
            binding_id=f"credential-binding-{uuid4().hex[:10]}",
            credential_id=credential_id,
            principal_id=principal_id,
            trust_policy_id=trust_policy.policy_id,
            status="active",
            created_at=self.now_factory(),
        )
        self.repository.save_credential_binding_record(binding)
        return binding

    def sign_request(
        self,
        *,
        credential_id: str,
        secret: str,
        method: str,
        path: str,
        request_id: str,
        nonce: str,
        timestamp: datetime,
        body: bytes,
    ) -> dict[str, str]:
        timestamp_text = timestamp.isoformat()
        signature = self._signature(
            key=self._hash_secret(secret),
            method=method,
            path=path,
            request_id=request_id,
            nonce=nonce,
            timestamp=timestamp_text,
            body=body,
            credential_id=credential_id,
        )
        return {
            "x-request-id": request_id,
            "x-request-nonce": nonce,
            "x-request-timestamp": timestamp_text,
            "x-service-signature": signature,
        }

    def verify_request(
        self,
        *,
        credential_id: str,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes,
        source_address: str,
    ) -> TrustDecision:
        now = self.now_factory()
        credential = self.repository.load_service_credential(credential_id)
        binding = self.repository.load_credential_binding_record(credential_id)
        if credential is None or binding is None or credential.status != "active":
            self._incident("unknown", credential_id, "invalid_credential_binding", "credential binding missing or inactive", source_address)
            return TrustDecision(False, "invalid_credential_binding")
        if self.repository.load_revoked_credential(credential_id) is not None:
            self._incident(credential.principal_id, credential_id, "revoked_credential", "revoked credential used for trust request", source_address)
            return TrustDecision(False, "revoked_credential")
        if credential.expires_at is not None and credential.expires_at <= now:
            self._incident(credential.principal_id, credential_id, "expired_credential", "expired credential used for trust request", source_address)
            return TrustDecision(False, "expired_credential")
        policy = self.repository.load_service_trust_policy(binding.trust_policy_id)
        if policy is None:
            self._incident(credential.principal_id, credential_id, "missing_policy", "service trust policy missing", source_address)
            return TrustDecision(False, "missing_policy")
        request_id = headers.get("x-request-id", "")
        nonce = headers.get("x-request-nonce", "")
        timestamp_text = headers.get("x-request-timestamp", "")
        signature = headers.get("x-service-signature", "")
        if not request_id or not signature or (policy.require_nonce and not nonce):
            self._incident(credential.principal_id, credential_id, "missing_headers", "signed headers missing", source_address)
            return TrustDecision(False, "missing_signed_headers")
        if self.repository.load_trust_replay_record(request_id=request_id) is not None or (nonce and self.repository.load_trust_replay_record(nonce=nonce) is not None):
            self._incident(credential.principal_id, credential_id, "replayed_request", "replayed trust request rejected", source_address)
            return TrustDecision(False, "replayed_request")
        try:
            timestamp = datetime.fromisoformat(timestamp_text)
        except ValueError:
            self._incident(credential.principal_id, credential_id, "invalid_timestamp", "request timestamp invalid", source_address)
            return TrustDecision(False, "invalid_timestamp")
        if abs((now - timestamp).total_seconds()) > policy.max_clock_skew_seconds:
            self._incident(credential.principal_id, credential_id, "timestamp_skew", "request timestamp outside trust window", source_address)
            return TrustDecision(False, "timestamp_skew")
        if not self._allowed_source(source_address, policy.allowed_networks):
            self._incident(credential.principal_id, credential_id, "untrusted_network", "source address outside trusted boundary", source_address)
            return TrustDecision(False, "untrusted_network")
        expected = self._signature(
            key=credential.token_hash,
            method=method,
            path=path,
            request_id=request_id,
            nonce=nonce,
            timestamp=timestamp_text,
            body=body,
            credential_id=credential_id,
        )
        if not hmac.compare_digest(signature, expected):
            self._incident(credential.principal_id, credential_id, "invalid_signature", "service signature mismatch", source_address)
            return TrustDecision(False, "invalid_signature")
        self.repository.save_network_identity_record(
            NetworkIdentityRecord(
                version="1.0",
                network_identity_id=f"network-identity-{uuid4().hex[:10]}",
                principal_id=credential.principal_id,
                source_address=source_address,
                asserted_identity=credential.principal_id,
                trust_mode=policy.trust_mode,
                status="accepted",
                created_at=now,
            )
        )
        self.repository.save_trust_replay_record(
            TrustReplayRecord(
                version="1.0",
                replay_id=f"trust-replay-{uuid4().hex[:10]}",
                credential_id=credential_id,
                request_id=request_id,
                nonce=nonce,
                created_at=now,
            )
        )
        return TrustDecision(True, "accepted")

    def _incident(self, principal_id: str, credential_id: str, incident_type: str, summary: str, source_address: str) -> None:
        self.repository.save_security_incident(
            SecurityIncidentRecord(
                version="1.0",
                incident_id=f"security-incident-{uuid4().hex[:10]}",
                principal_id=principal_id,
                credential_id=credential_id,
                incident_type=incident_type,
                summary=summary,
                source_address=source_address,
                created_at=self.now_factory(),
            )
        )

    def _signature(
        self,
        *,
        key: str,
        method: str,
        path: str,
        request_id: str,
        nonce: str,
        timestamp: str,
        body: bytes,
        credential_id: str,
    ) -> str:
        payload = "\n".join(
            [
                method.upper(),
                path,
                credential_id,
                request_id,
                nonce,
                timestamp,
                hashlib.sha256(body).hexdigest(),
            ]
        )
        return hmac.new(key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def _hash_secret(self, secret: str) -> str:
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    def _allowed_source(self, source_address: str, allowed_networks: list[str]) -> bool:
        if not allowed_networks:
            return True
        try:
            address = ipaddress.ip_address(source_address)
        except ValueError:
            return False
        for network in allowed_networks:
            try:
                if address in ipaddress.ip_network(network, strict=False):
                    return True
            except ValueError:
                continue
        return False
