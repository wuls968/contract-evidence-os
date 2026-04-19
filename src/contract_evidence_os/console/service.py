"""Service layer for the browser-facing UX console."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from contract_evidence_os.api.operator import OperatorAPI
from contract_evidence_os.audit.models import AuditEvent, ExecutionReceipt
from contract_evidence_os.base import SchemaModel, utc_now
from contract_evidence_os.config import RuntimeConfig
from contract_evidence_os.console.models import (
    BrowserSession,
    ConfigValidationResult,
    DashboardPreference,
    OIDCLoginState,
    OIDCProviderConfig,
    ProviderUsageTrend,
    TaskUsageSummary,
    TokenUsageAggregate,
    UsageAlertRecord,
    UserAccount,
    UserPasswordCredential,
    UserRoleBinding,
)
from contract_evidence_os.contracts.models import TaskContract
from contract_evidence_os.evals.models import StrategyEvaluationReport
from contract_evidence_os.evidence.models import ClaimRecord, EvidenceSpan, SourceRecord, ValidationReport
from contract_evidence_os.planning.models import PlanNode
from contract_evidence_os.runtime.providers import ProviderUsageRecord
from contract_evidence_os.tools.anything_cli.models import HarnessManifest, SoftwareActionReceipt
from contract_evidence_os.trusted_runtime.models import (
    AuditEventBundle,
    AuditLogEntry,
    AuditTrendReport,
    BenchmarkArtifact,
    BenchmarkCase,
    BenchmarkRun,
    BenchmarkSuite,
    BenchmarkSummaryView,
    CollaborationSummaryView,
    EvidenceTraceView,
    HumanReviewCase,
    HumanReviewDecision,
    MCPInvocationRecord,
    MCPPermissionDecision,
    MCPResourceRecord,
    MCPServerRecord,
    MCPToolRecord,
    PlaybookRecord,
    PlaybookStep,
    ReproBundle,
    ReproEvalRun,
    SessionAuditRecord,
    StructuredSchemaRecord,
    TaskCollaborationBinding,
    TaskReviewerAssignment,
    TaskTimelineView,
    WorkspaceInvitation,
)


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


class ConsoleService:
    """Provide browser-oriented UX console behavior on top of OperatorAPI."""

    def __init__(
        self,
        *,
        api: OperatorAPI,
        config_path: Path,
        env_path: Path,
    ) -> None:
        self.api = api
        self.repository = api.repository
        self.config_path = Path(config_path)
        self.env_path = Path(env_path)

    # ------------------------------------------------------------------
    # Generic runtime-state persistence helpers
    # ------------------------------------------------------------------
    def _save_model(self, record_type: str, record_id: str, scope_key: str | None, created_at: str, model: Any) -> None:
        self.repository._save_runtime_state_record(record_type, record_id, scope_key, created_at, model)  # noqa: SLF001

    def _load_model(self, record_type: str, record_id: str, model_cls: type[Any]) -> Any | None:
        return self.repository._load_runtime_state_record(record_type, record_id, model_cls)  # noqa: SLF001

    def _list_models(self, record_type: str, model_cls: type[Any], scope_key: str | None = None) -> list[Any]:
        return self.repository._list_runtime_state_records(record_type, model_cls, scope_key=scope_key)  # noqa: SLF001

    # ------------------------------------------------------------------
    # Password / session helpers
    # ------------------------------------------------------------------
    def _hash_password(self, password: str, *, salt: str | None = None) -> tuple[str, str]:
        salt_bytes = secrets.token_bytes(16) if salt is None else bytes.fromhex(salt)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt_bytes, n=2**14, r=8, p=1)
        return base64.b64encode(digest).decode("ascii"), salt_bytes.hex()

    def _verify_password(self, password: str, credential: UserPasswordCredential) -> bool:
        digest, _ = self._hash_password(password, salt=credential.password_salt)
        return secrets.compare_digest(digest, credential.password_hash)

    def _env_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        if not self.env_path.exists():
            return values
        for raw_line in self.env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        return values

    def _write_env_values(self, updates: dict[str, str]) -> None:
        merged = self._env_values()
        for key, value in updates.items():
            if value == "":
                merged.pop(key, None)
            else:
                merged[key] = value
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{key}={value}" for key, value in sorted(merged.items())]
        self.env_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _load_config_payload(self) -> dict[str, Any]:
        payload = RuntimeConfig(). __dict__.copy()
        if self.config_path.exists():
            payload.update(json.loads(self.config_path.read_text(encoding="utf-8")))
        return payload

    def _write_config_payload(self, payload: dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _runtime_config(self) -> RuntimeConfig:
        return RuntimeConfig.load(config_path=self.config_path)

    # ------------------------------------------------------------------
    # Account lifecycle
    # ------------------------------------------------------------------
    def list_user_accounts(self) -> list[UserAccount]:
        return self._list_models("console_user_account", UserAccount)

    def list_user_role_bindings(self, user_id: str | None = None) -> list[UserRoleBinding]:
        return self._list_models("console_user_role_binding", UserRoleBinding, scope_key=user_id)

    def _user_by_email(self, email: str) -> UserAccount | None:
        normalized = email.strip().lower()
        for user in self.list_user_accounts():
            if user.email.lower() == normalized and user.status == "active":
                return user
        return None

    def _password_credential_for_user(self, user_id: str) -> UserPasswordCredential | None:
        records = self._list_models("console_password_credential", UserPasswordCredential, scope_key=user_id)
        return None if not records else records[0]

    def has_admin_account(self) -> bool:
        for user in self.list_user_accounts():
            roles = [binding.role_name for binding in self.list_user_role_bindings(user.user_id)]
            if user.status == "active" and "admin" in roles:
                return True
        return False

    def bootstrap_state(self) -> dict[str, Any]:
        config = self._runtime_config()
        admin_exists = self.has_admin_account()
        oidc_configs = self.list_oidc_provider_configs()
        return {
            "setup_required": not admin_exists,
            "admin_exists": admin_exists,
            "config_path": str(self.config_path),
            "env_path": str(self.env_path),
            "provider": {
                "kind": config.provider.get("kind", "deterministic"),
                "default_model": config.provider.get("default_model", ""),
                "base_url": config.provider.get("resolved_base_url", config.provider.get("base_url", "")),
                "api_key_present": bool(config.provider.get("api_key_present", False)),
            },
            "oidc_enabled": any(item.enabled for item in oidc_configs),
            "oidc_presets": self.oidc_presets(),
        }

    def bootstrap_admin(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.has_admin_account():
            raise ValueError("bootstrap admin already exists")
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        display_name = str(payload.get("display_name", "")).strip() or email
        if not email or "@" not in email:
            raise ValueError("a valid admin email is required")
        if len(password) < 10:
            raise ValueError("admin password must be at least 10 characters")

        user = UserAccount(
            version="1.0",
            user_id=f"user-{uuid4().hex[:10]}",
            email=email,
            display_name=display_name,
            status="active",
            auth_source="local",
        )
        password_hash, salt = self._hash_password(password)
        credential = UserPasswordCredential(
            version="1.0",
            credential_id=f"password-{uuid4().hex[:10]}",
            user_id=user.user_id,
            password_hash=password_hash,
            password_salt=salt,
            algorithm="scrypt",
        )
        binding = UserRoleBinding(
            version="1.0",
            binding_id=f"role-{uuid4().hex[:10]}",
            user_id=user.user_id,
            role_name="admin",
            scopes=list(ROLE_SCOPES["admin"]),
        )
        self._save_model("console_user_account", user.user_id, user.email, user.created_at.isoformat(), user)
        self._save_model("console_password_credential", credential.credential_id, user.user_id, credential.created_at.isoformat(), credential)
        self._save_model("console_user_role_binding", binding.binding_id, user.user_id, binding.created_at.isoformat(), binding)
        self._record_session_audit(
            session_id="bootstrap",
            user_id=user.user_id,
            action="bootstrap_admin_created",
            actor=user.email,
            details={"role": "admin"},
        )
        self.apply_setup_payload(payload)
        return {
            "account": user.to_dict(),
            "roles": [binding.to_dict()],
            "bootstrap_state": self.bootstrap_state(),
        }

    def create_user_account(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
        role_name: str = "viewer",
    ) -> dict[str, Any]:
        if role_name not in ROLE_SCOPES:
            raise ValueError(f"unsupported role: {role_name}")
        if self._user_by_email(email) is not None:
            raise ValueError("user already exists")
        user = UserAccount(
            version="1.0",
            user_id=f"user-{uuid4().hex[:10]}",
            email=email.strip().lower(),
            display_name=display_name.strip() or email.strip().lower(),
            status="active",
            auth_source="local",
        )
        password_hash, salt = self._hash_password(password)
        credential = UserPasswordCredential(
            version="1.0",
            credential_id=f"password-{uuid4().hex[:10]}",
            user_id=user.user_id,
            password_hash=password_hash,
            password_salt=salt,
            algorithm="scrypt",
        )
        binding = UserRoleBinding(
            version="1.0",
            binding_id=f"role-{uuid4().hex[:10]}",
            user_id=user.user_id,
            role_name=role_name,
            scopes=list(ROLE_SCOPES[role_name]),
        )
        self._save_model("console_user_account", user.user_id, user.email, user.created_at.isoformat(), user)
        self._save_model("console_password_credential", credential.credential_id, user.user_id, credential.created_at.isoformat(), credential)
        self._save_model("console_user_role_binding", binding.binding_id, user.user_id, binding.created_at.isoformat(), binding)
        self._record_session_audit(
            session_id="account-change",
            user_id=user.user_id,
            action="user_account_created",
            actor=user.email,
            details={"role": role_name},
        )
        return {"account": user.to_dict(), "roles": [binding.to_dict()]}

    def authenticate_local(self, *, email: str, password: str) -> SessionPrincipal:
        user = self._user_by_email(email)
        if user is None:
            raise ValueError("invalid email or password")
        credential = self._password_credential_for_user(user.user_id)
        if credential is None or not self._verify_password(password, credential):
            raise ValueError("invalid email or password")
        roles = self.list_user_role_bindings(user.user_id)
        scopes = sorted({scope for role in roles for scope in role.scopes})
        session = BrowserSession(
            version="1.0",
            session_id=f"browser-session-{uuid4().hex[:10]}",
            user_id=user.user_id,
            scopes=scopes,
            status="active",
            expires_at=utc_now() + timedelta(days=7),
            last_seen_at=utc_now(),
        )
        user.last_login_at = utc_now()
        self._save_model("console_browser_session", session.session_id, user.user_id, session.created_at.isoformat(), session)
        self._save_model("console_user_account", user.user_id, user.email, user.created_at.isoformat(), user)
        self._record_session_audit(
            session_id=session.session_id,
            user_id=user.user_id,
            action="login",
            actor=user.email,
            details={"auth_source": "local"},
        )
        return SessionPrincipal(
            user=user,
            roles=[item.role_name for item in roles],
            scopes=scopes,
            session=session,
        )

    def resolve_session(self, session_id: str) -> SessionPrincipal | None:
        session = self._load_model("console_browser_session", session_id, BrowserSession)
        if session is None or session.status != "active":
            return None
        if session.expires_at is not None and session.expires_at <= utc_now():
            session.status = "expired"
            self._save_model("console_browser_session", session.session_id, session.user_id, session.created_at.isoformat(), session)
            return None
        user = self._load_model("console_user_account", session.user_id, UserAccount)
        if user is None or user.status != "active":
            return None
        roles = self.list_user_role_bindings(user.user_id)
        session.last_seen_at = utc_now()
        self._save_model("console_browser_session", session.session_id, session.user_id, session.created_at.isoformat(), session)
        return SessionPrincipal(
            user=user,
            roles=[item.role_name for item in roles],
            scopes=sorted({scope for role in roles for scope in role.scopes}),
            session=session,
        )

    def logout_session(self, session_id: str) -> None:
        session = self._load_model("console_browser_session", session_id, BrowserSession)
        if session is None:
            return
        session.status = "revoked"
        self._save_model("console_browser_session", session.session_id, session.user_id, session.created_at.isoformat(), session)
        self._record_session_audit(
            session_id=session.session_id,
            user_id=session.user_id,
            action="logout",
            actor=session.user_id,
            details={"status": session.status},
        )

    def list_browser_sessions(self) -> list[BrowserSession]:
        return self._list_models("console_browser_session", BrowserSession)

    def list_workspace_invitations(self) -> list[WorkspaceInvitation]:
        return self._list_models("console_workspace_invitation", WorkspaceInvitation)

    def create_workspace_invitation(self, *, email: str, role_name: str, invited_by: str) -> dict[str, Any]:
        if role_name not in ROLE_SCOPES:
            raise ValueError(f"unsupported role: {role_name}")
        invitation = WorkspaceInvitation(
            version="1.0",
            invitation_id=f"invite-{uuid4().hex[:10]}",
            email=email.strip().lower(),
            role_name=role_name,
            invited_by=invited_by,
            status="pending",
        )
        self._save_model(
            "console_workspace_invitation",
            invitation.invitation_id,
            invitation.email,
            invitation.created_at.isoformat(),
            invitation,
        )
        return {"invitation": invitation.to_dict()}

    def _record_session_audit(
        self,
        *,
        session_id: str,
        user_id: str,
        action: str,
        actor: str,
        details: dict[str, Any],
    ) -> SessionAuditRecord:
        record = SessionAuditRecord(
            version="1.0",
            session_audit_id=f"session-audit-{uuid4().hex[:10]}",
            session_id=session_id,
            user_id=user_id,
            action=action,
            actor=actor,
            details=details,
        )
        self._save_model("console_session_audit", record.session_audit_id, session_id, record.created_at.isoformat(), record)
        return record

    def _default_actor_email(self) -> str:
        accounts = self.list_user_accounts()
        if accounts:
            return accounts[0].email
        return "runtime-system"

    # ------------------------------------------------------------------
    # OIDC
    # ------------------------------------------------------------------
    def oidc_presets(self) -> list[dict[str, Any]]:
        return [
            {
                "preset_name": "github",
                "display_name": "GitHub",
                "issuer": "https://github.com",
                "authorize_url": "https://github.com/login/oauth/authorize",
                "token_url": "https://github.com/login/oauth/access_token",
                "userinfo_url": "https://api.github.com/user",
                "scopes": ["read:user", "user:email"],
            },
            {
                "preset_name": "google",
                "display_name": "Google",
                "issuer": "https://accounts.google.com",
                "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_url": "https://oauth2.googleapis.com/token",
                "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
                "scopes": ["openid", "email", "profile"],
            },
        ]

    def list_oidc_provider_configs(self) -> list[OIDCProviderConfig]:
        return self._list_models("console_oidc_provider", OIDCProviderConfig)

    def save_oidc_provider_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        provider_id = str(payload.get("provider_id") or _slugify(str(payload.get("display_name", "provider"))))
        client_secret = str(payload.get("client_secret", ""))
        client_secret_env = str(payload.get("client_secret_env") or f"CEOS_OIDC_{provider_id.upper()}_CLIENT_SECRET")
        record = OIDCProviderConfig(
            version="1.0",
            provider_id=provider_id,
            display_name=str(payload.get("display_name", provider_id)),
            issuer=str(payload.get("issuer", "")),
            client_id=str(payload.get("client_id", "")),
            client_secret_env=client_secret_env,
            authorize_url=str(payload.get("authorize_url", "")),
            token_url=str(payload.get("token_url", "")),
            userinfo_url=str(payload.get("userinfo_url", "")),
            scopes=[str(item) for item in payload.get("scopes", ["openid", "email", "profile"])],
            enabled=bool(payload.get("enabled", True)),
            preset_name=str(payload.get("preset_name", "")),
            updated_at=utc_now(),
        )
        created_at = record.updated_at or utc_now()
        self._save_model("console_oidc_provider", record.provider_id, record.provider_id, created_at.isoformat(), record)
        if client_secret:
            self._write_env_values({client_secret_env: client_secret})
        return {
            "provider": record.to_dict(),
            "client_secret_present": bool(self._env_values().get(client_secret_env)),
        }

    def test_oidc_provider_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        messages: list[str] = []
        status = "ok"
        if not payload.get("authorize_url"):
            status = "invalid"
            messages.append("authorize_url is required")
        if not payload.get("token_url"):
            status = "invalid"
            messages.append("token_url is required")
        if not payload.get("userinfo_url"):
            status = "invalid"
            messages.append("userinfo_url is required")
        if not payload.get("client_id"):
            status = "invalid"
            messages.append("client_id is required")
        result = ConfigValidationResult(
            version="1.0",
            result_id=f"config-check-{uuid4().hex[:10]}",
            validation_kind="oidc",
            status=status,
            messages=messages or ["OIDC configuration shape looks valid."],
            details={"provider_id": payload.get("provider_id", ""), "display_name": payload.get("display_name", "")},
        )
        self._save_model("console_config_validation", result.result_id, "oidc", result.created_at.isoformat(), result)
        return result.to_dict()

    def start_oidc_login(self, provider_id: str, *, redirect_uri: str, next_path: str = "/dashboard") -> str:
        configs = {item.provider_id: item for item in self.list_oidc_provider_configs() if item.enabled}
        provider = configs.get(provider_id)
        if provider is None:
            raise KeyError(provider_id)
        state = OIDCLoginState(
            version="1.0",
            state_id=secrets.token_urlsafe(24),
            provider_id=provider_id,
            redirect_uri=redirect_uri,
            nonce=secrets.token_urlsafe(16),
            expires_at=utc_now() + timedelta(minutes=10),
            next_path=next_path,
        )
        self._save_model("console_oidc_login_state", state.state_id, provider_id, state.created_at.isoformat(), state)
        query = urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": provider.client_id,
                "redirect_uri": redirect_uri,
                "scope": " ".join(provider.scopes),
                "state": state.state_id,
            }
        )
        return f"{provider.authorize_url}?{query}"

    def finish_oidc_login(self, *, state_id: str, code: str) -> SessionPrincipal:
        state = self._load_model("console_oidc_login_state", state_id, OIDCLoginState)
        if state is None:
            raise ValueError("unknown oidc state")
        if state.expires_at is not None and state.expires_at <= utc_now():
            raise ValueError("expired oidc state")
        provider = {item.provider_id: item for item in self.list_oidc_provider_configs()}.get(state.provider_id)
        if provider is None:
            raise ValueError("oidc provider configuration not found")
        client_secret = self._env_values().get(provider.client_secret_env, "")
        token_request = urllib.request.Request(
            provider.token_url,
            data=urllib.parse.urlencode(
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": state.redirect_uri,
                    "client_id": provider.client_id,
                    "client_secret": client_secret,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(token_request, timeout=5) as response:
                token_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:  # pragma: no cover - network dependent
            raise ValueError(f"oidc token exchange failed: {exc.reason}") from exc
        access_token = str(token_payload.get("access_token", ""))
        if not access_token:
            raise ValueError("oidc provider did not return an access token")
        userinfo_request = urllib.request.Request(
            provider.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(userinfo_request, timeout=5) as response:
                profile = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:  # pragma: no cover - network dependent
            raise ValueError(f"oidc userinfo fetch failed: {exc.reason}") from exc
        email = str(profile.get("email") or profile.get("login") or f"{profile.get('sub', 'user')}@oidc.local").strip().lower()
        display_name = str(profile.get("name") or profile.get("login") or email)
        external_subject = str(profile.get("sub") or profile.get("id") or email)
        user = self._user_by_email(email)
        if user is None:
            created = self.create_user_account(email=email, password=secrets.token_urlsafe(24), display_name=display_name, role_name="viewer")
            user = UserAccount.from_dict(created["account"])
            user.auth_source = "oidc"
            user.external_subject = external_subject
        else:
            user.auth_source = "oidc"
            user.external_subject = external_subject
        user.last_login_at = utc_now()
        self._save_model("console_user_account", user.user_id, user.email, user.created_at.isoformat(), user)
        roles = self.list_user_role_bindings(user.user_id)
        scopes = sorted({scope for role in roles for scope in role.scopes})
        session = BrowserSession(
            version="1.0",
            session_id=f"browser-session-{uuid4().hex[:10]}",
            user_id=user.user_id,
            scopes=scopes,
            status="active",
            expires_at=utc_now() + timedelta(days=7),
            last_seen_at=utc_now(),
        )
        self._save_model("console_browser_session", session.session_id, user.user_id, session.created_at.isoformat(), session)
        self._record_session_audit(
            session_id=session.session_id,
            user_id=user.user_id,
            action="login",
            actor=user.email,
            details={"auth_source": "oidc", "provider_id": provider.provider_id},
        )
        return SessionPrincipal(user=user, roles=[item.role_name for item in roles], scopes=scopes, session=session)

    # ------------------------------------------------------------------
    # Config / setup
    # ------------------------------------------------------------------
    def apply_setup_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        config_payload = self._load_config_payload()
        provider_payload = dict(payload.get("provider", {}))
        provider_kind = str(provider_payload.get("kind", "deterministic"))
        provider_api_key = str(provider_payload.get("api_key", ""))
        provider_base_url = str(provider_payload.get("base_url", "")) or config_payload.get("provider", {}).get("base_url", "https://api.openai.com/v1")
        config_payload["service"] = {
            **dict(config_payload.get("service", {})),
            "host": str(dict(payload.get("service", {})).get("host", "127.0.0.1")),
            "port": int(dict(payload.get("service", {})).get("port", 8080)),
            "token_env": "CEOS_OPERATOR_TOKEN",
        }
        config_payload["provider"] = {
            **dict(config_payload.get("provider", {})),
            "kind": provider_kind,
            "base_url": provider_base_url,
            "default_model": str(provider_payload.get("default_model", config_payload.get("provider", {}).get("default_model", "gpt-4.1-mini"))),
            "api_key_env": "CEOS_API_KEY",
            "base_url_env": "CEOS_API_BASE_URL",
        }
        config_payload["observability"] = {
            **dict(config_payload.get("observability", {})),
            "enabled": bool(payload.get("observability_enabled", True)),
        }
        config_payload["software_control"] = {
            **dict(config_payload.get("software_control", {})),
            "repo_path": str(payload.get("software_control_repo_path", "")),
        }
        self._write_config_payload(config_payload)
        env_updates = {
            "CEOS_OPERATOR_TOKEN": self._env_values().get("CEOS_OPERATOR_TOKEN", secrets.token_urlsafe(24)),
            "CEOS_PROVIDER_KIND": provider_kind,
            "CEOS_API_BASE_URL": provider_base_url,
            "CEOS_DEFAULT_MODEL": str(config_payload["provider"]["default_model"]),
        }
        if provider_api_key:
            env_updates["CEOS_API_KEY"] = provider_api_key
        self._write_env_values(env_updates)
        return {"config_path": str(self.config_path), "env_path": str(self.env_path)}

    def config_effective(self) -> dict[str, Any]:
        config = RuntimeConfig.load(config_path=self.config_path)
        env_values = self._env_values()
        oidc_providers = self.list_oidc_provider_configs()
        return {
            "effective": config.audit_summary(),
            "paths": {"config_path": str(self.config_path), "env_path": str(self.env_path)},
            "env_overrides": {
                "operator_token_present": bool(env_values.get("CEOS_OPERATOR_TOKEN")),
                "api_key_present": bool(env_values.get("CEOS_API_KEY")),
                "configured_env_keys": sorted(env_values),
            },
            "oidc_providers": [
                {
                    **item.to_dict(),
                    "client_secret_present": bool(env_values.get(item.client_secret_env)),
                }
                for item in oidc_providers
            ],
        }

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        config_payload = self._load_config_payload()
        if "service" in payload:
            config_payload["service"] = {**dict(config_payload.get("service", {})), **dict(payload["service"])}
        if "provider" in payload:
            provider_payload = {**dict(config_payload.get("provider", {})), **dict(payload["provider"])}
            secret_api_key = str(provider_payload.pop("api_key", ""))
            config_payload["provider"] = provider_payload
            if secret_api_key:
                self._write_env_values({"CEOS_API_KEY": secret_api_key})
        if "observability" in payload:
            config_payload["observability"] = {**dict(config_payload.get("observability", {})), **dict(payload["observability"])}
        if "software_control" in payload:
            config_payload["software_control"] = {**dict(config_payload.get("software_control", {})), **dict(payload["software_control"])}
        self._write_config_payload(config_payload)
        return self.config_effective()

    def test_provider_connection(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        provider = {**self._runtime_config().provider, **(payload or {})}
        kind = str(provider.get("kind", "deterministic"))
        messages: list[str] = []
        status = "ok"
        details: dict[str, Any] = {
            "kind": kind,
            "base_url": provider.get("resolved_base_url", provider.get("base_url", "")),
            "default_model": provider.get("default_model", ""),
        }
        if kind == "deterministic":
            messages.append("Deterministic provider is active; live API connectivity is not required.")
        else:
            api_key = str(provider.get("api_key") or provider.get("resolved_api_key") or self._env_values().get("CEOS_API_KEY", ""))
            if not api_key:
                status = "invalid"
                messages.append("Missing API key for live provider.")
            base_url = str(provider.get("base_url") or provider.get("resolved_base_url") or "")
            if not base_url:
                status = "invalid"
                messages.append("Missing provider base URL.")
            elif status == "ok":
                request = urllib.request.Request(
                    base_url,
                    headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
                    method="GET",
                )
                try:
                    with urllib.request.urlopen(request, timeout=5) as response:
                        details["http_status"] = getattr(response, "status", 200)
                    messages.append("Provider endpoint responded successfully.")
                except urllib.error.HTTPError as exc:
                    details["http_status"] = exc.code
                    messages.append(f"Provider endpoint responded with HTTP {exc.code}; network path is reachable.")
                except urllib.error.URLError as exc:
                    status = "error"
                    messages.append(f"Provider connectivity failed: {exc.reason}")
        result = ConfigValidationResult(
            version="1.0",
            result_id=f"config-check-{uuid4().hex[:10]}",
            validation_kind="provider",
            status=status,
            messages=messages or ["Provider settings look valid."],
            details=details,
        )
        self._save_model("console_config_validation", result.result_id, "provider", result.created_at.isoformat(), result)
        return result.to_dict()

    # ------------------------------------------------------------------
    # Trusted runtime core
    # ------------------------------------------------------------------
    def schema_registry(self) -> dict[str, Any]:
        schema_specs: list[tuple[str, str, type[SchemaModel], list[str]]] = [
            ("contract-input", "Contract input schema", TaskContract, ["Structured contract payloads remain JSON-schema governed."]),
            ("evidence-source", "Evidence source schema", SourceRecord, ["Source metadata is the anchor for evidence spans."]),
            ("evidence-span", "Evidence span schema", EvidenceSpan, ["Claims and validation reports can point at exact source spans."]),
            ("claim-record", "Claim record schema", ClaimRecord, ["Claims must remain evidence-linked and span-addressable."]),
            ("validation-report", "Validation report schema", ValidationReport, ["Verifier output stays evidence-bound and reviewable."]),
            ("audit-log-entry", "Audit log entry schema", AuditLogEntry, ["The audit ledger is append-only and human-readable."]),
            ("playbook-record", "Playbook schema", PlaybookRecord, ["High-value delivery paths become explicit playbooks."]),
            ("human-review-case", "Human review schema", HumanReviewCase, ["Approvals, evidence review, and benchmark sign-off share one review model."]),
            ("benchmark-run", "Benchmark run schema", BenchmarkRun, ["Benchmark and repro-eval summaries stay structured and exportable."]),
            ("mcp-tool-record", "MCP tool descriptor schema", MCPToolRecord, ["MCP tools must publish structured descriptors and permission modes."]),
        ]
        items: list[dict[str, Any]] = []
        for schema_id, title, model_cls, notes in schema_specs:
            record = StructuredSchemaRecord(
                version="1.0",
                schema_id=schema_id,
                schema_kind=model_cls.__name__,
                title=title,
                json_schema=model_cls.json_schema(),
                compatibility_notes=notes,
            )
            self._save_model("trusted_schema_record", record.schema_id, schema_id, record.created_at.isoformat(), record)
            items.append(record.to_dict())
        return {"items": items}

    def _synthesized_evidence_spans(self, task_id: str) -> list[EvidenceSpan]:
        sources = self.repository.list_source_records(task_id)
        spans: list[EvidenceSpan] = []
        for source in sources:
            text = source.snippet.strip() or source.locator
            span = EvidenceSpan(
                version="1.0",
                span_id=f"span-{source.source_id}",
                source_id=source.source_id,
                locator=source.locator,
                label=source.source_type,
                start_offset=0,
                end_offset=len(text),
                text=text,
                metadata={"credibility": source.credibility, "time_relevance": source.time_relevance},
                created_at=source.retrieved_at,
            )
            self._save_model("trusted_evidence_span", span.span_id, task_id, span.created_at.isoformat(), span)
            spans.append(span)
        return spans

    def _audit_log_entries(self, task_id: str | None = None) -> list[AuditLogEntry]:
        entries: list[AuditLogEntry] = []
        tasks = [task_id] if task_id else [str(item["task_id"]) for item in self.repository.list_tasks()]
        for current_task_id in tasks:
            for event in self.repository.query_audit(task_id=current_task_id):
                entry = AuditLogEntry(
                    version="1.0",
                    entry_id=f"audit-log-{event.event_id}",
                    task_id=event.task_id,
                    event_type=event.event_type,
                    actor=event.actor,
                    status=event.result,
                    summary=event.why,
                    evidence_refs=list(event.evidence_refs),
                    evidence_span_refs=[],
                    related_refs=list(event.tool_refs) + list(event.approval_refs),
                    created_at=event.timestamp,
                    risk_level=event.risk_level,
                )
                self._save_model("trusted_audit_log_entry", entry.entry_id, current_task_id, entry.created_at.isoformat(), entry)
                entries.append(entry)
            for receipt in self.repository.list_execution_receipts(current_task_id):
                entry = AuditLogEntry(
                    version="1.0",
                    entry_id=f"audit-log-{receipt.receipt_id}",
                    task_id=current_task_id,
                    event_type="execution_receipt",
                    actor=receipt.actor,
                    status=receipt.status,
                    summary=receipt.output_summary,
                    evidence_refs=list(receipt.evidence_refs),
                    evidence_span_refs=[],
                    related_refs=list(receipt.artifacts) + list(receipt.validation_refs) + list(receipt.approval_refs),
                    created_at=receipt.timestamp,
                )
                self._save_model("trusted_audit_log_entry", entry.entry_id, current_task_id, entry.created_at.isoformat(), entry)
                entries.append(entry)
        entries.sort(key=lambda item: item.created_at)
        return entries

    def _audit_trend(self, task_id: str | None = None) -> AuditTrendReport:
        buckets: dict[str, int] = {}
        entries = self._audit_log_entries(task_id)
        for entry in entries:
            bucket = entry.created_at.replace(minute=0, second=0, microsecond=0).isoformat()
            buckets[bucket] = buckets.get(bucket, 0) + 1
        report = AuditTrendReport(
            version="1.0",
            report_id=f"audit-trend-{uuid4().hex[:10]}",
            points=[{"timestamp": key, "count": value} for key, value in sorted(buckets.items())],
            summary={"total_events": len(entries), "task_id": task_id or "all"},
        )
        self._save_model("trusted_audit_trend", report.report_id, task_id or "all", report.created_at.isoformat(), report)
        return report

    def _synthesized_playbook(self, task_id: str) -> PlaybookRecord:
        plan = self.repository.load_plan(task_id)
        task = self.repository.get_task(task_id) or {"status": "draft"}
        steps: list[PlaybookStep] = []
        if plan is not None and plan.nodes:
            for node in plan.nodes:
                steps.append(
                    PlaybookStep(
                        version="1.0",
                        step_id=f"playbook-step-{node.node_id}",
                        playbook_id=f"playbook-{task_id}",
                        title=node.objective[:80],
                        description=node.objective,
                        status=node.status,
                        evidence_required=node.node_category in {"collect", "extract", "validate"},
                        checkpoint_required=node.checkpoint_required or node.node_category in {"checkpoint", "deliver"},
                        human_review_required=bool(node.approval_gate),
                        related_plan_node_id=node.node_id,
                    )
                )
        else:
            defaults = [
                ("Compile contract", "Normalize task constraints and success criteria.", "completed"),
                ("Collect evidence", "Gather source-backed material before synthesis.", "completed"),
                ("Validate delivery", "Run verifier and contradiction checks.", "completed" if task.get("status") == "delivered" else "in_progress"),
                ("Human review", "Surface approvals or review cases before publication.", "needs_review" if task.get("status") == "awaiting_approval" else "completed"),
            ]
            for index, (title, description, status) in enumerate(defaults, start=1):
                steps.append(
                    PlaybookStep(
                        version="1.0",
                        step_id=f"playbook-step-{task_id}-{index}",
                        playbook_id=f"playbook-{task_id}",
                        title=title,
                        description=description,
                        status=status,
                        evidence_required=index in {2, 3},
                        checkpoint_required=index in {1, 4},
                        human_review_required=index == 4,
                    )
                )
        playbook = PlaybookRecord(
            version="1.0",
            playbook_id=f"playbook-{task_id}",
            task_id=task_id,
            title=f"Trusted delivery playbook for {task_id}",
            status="needs_review" if task.get("status") == "awaiting_approval" else str(task.get("status", "draft")),
            rationale="Critical outputs stay tied to evidence, checkpoints, and human review requirements.",
            steps=steps,
        )
        self._save_model("trusted_playbook", playbook.playbook_id, task_id, playbook.created_at.isoformat(), playbook)
        return playbook

    def _review_cases(self, task_id: str | None = None) -> list[HumanReviewCase]:
        cases: list[HumanReviewCase] = []
        approvals = self.repository.list_approval_requests(status="pending")
        for approval in approvals:
            if task_id and approval.task_id != task_id:
                continue
            decision = HumanReviewDecision(
                version="1.0",
                decision_id=f"review-decision-placeholder-{approval.request_id}",
                case_id=f"review-case-{approval.request_id}",
                actor="pending",
                decision="pending",
                rationale="Awaiting operator decision.",
                evidence_refs=list(approval.relevant_evidence),
            )
            cases.append(
                HumanReviewCase(
                    version="1.0",
                    case_id=f"review-case-{approval.request_id}",
                    task_id=approval.task_id,
                    review_kind="runtime_approval",
                    status=approval.status,
                    summary=approval.action_summary or approval.reason,
                    assignee="approver",
                    evidence_refs=list(approval.relevant_evidence),
                    decisions=[decision],
                )
            )
        tasks = [task_id] if task_id else [str(item["task_id"]) for item in self.repository.list_tasks()]
        for current_task_id in tasks:
            report = self.repository.load_latest_validation_report(current_task_id)
            if report is None:
                continue
            if report.status not in {"blocked", "failed"}:
                continue
            cases.append(
                HumanReviewCase(
                    version="1.0",
                    case_id=f"review-case-validation-{report.report_id}",
                    task_id=current_task_id,
                    review_kind="evidence_review",
                    status="pending",
                    summary="Validation report requires human review before trusted publication.",
                    assignee="reviewer",
                    evidence_refs=list(report.evidence_refs),
                    decisions=[],
                )
            )
        for case in cases:
            self._save_model("trusted_human_review_case", case.case_id, case.task_id, case.created_at.isoformat(), case)
        return cases

    def _benchmark_summary(self) -> BenchmarkSummaryView:
        suites: list[dict[str, Any]] = []
        latest_runs: list[dict[str, Any]] = []
        repro_runs: list[dict[str, Any]] = []
        candidates = self.repository.list_evolution_candidates()
        for candidate in candidates:
            suite = BenchmarkSuite(
                version="1.0",
                suite_id=f"benchmark-suite-{candidate.candidate_id}",
                title=candidate.target_component,
                description=candidate.hypothesis,
                benchmark_kind=candidate.candidate_type,
            )
            suites.append(suite.to_dict())
            for evaluation in self.repository.list_evaluation_runs(candidate.candidate_id):
                latest_runs.append(
                    BenchmarkRun(
                        version="1.0",
                        run_id=evaluation.run_id,
                        suite_id=suite.suite_id,
                        case_id=evaluation.suite_name,
                        task_id="",
                        status=evaluation.status,
                        score=float(evaluation.metrics.get("gain", evaluation.metrics.get("score", 0.0))),
                        summary=f"Evaluation suite {evaluation.suite_name}",
                        created_at=evaluation.completed_at,
                    ).to_dict()
                )
            for canary in self.repository.list_canary_runs(candidate.candidate_id):
                repro_runs.append(
                    ReproEvalRun(
                        version="1.0",
                        repro_run_id=f"repro-{canary.run_id}",
                        task_id="",
                        status=canary.status,
                        summary=f"Canary scope {canary.scope}",
                        created_at=canary.completed_at,
                    ).to_dict()
                )
        if not suites:
            suites.append(
                BenchmarkSuite(
                    version="1.0",
                    suite_id="benchmark-suite-runtime-health",
                    title="Runtime trust baseline",
                    description="No explicit evolution candidates yet; trusted-runtime baseline is active.",
                    benchmark_kind="baseline",
                ).to_dict()
            )
        summary = BenchmarkSummaryView(
            version="1.0",
            summary_id=f"benchmark-summary-{uuid4().hex[:10]}",
            suites=suites,
            latest_runs=sorted(latest_runs, key=lambda item: item.get("created_at", ""), reverse=True),
            repro_runs=sorted(repro_runs, key=lambda item: item.get("created_at", ""), reverse=True),
        )
        self._save_model("trusted_benchmark_summary", summary.summary_id, "global", summary.created_at.isoformat(), summary)
        return summary

    def _ensure_task_collaboration_binding(self, task_id: str) -> TaskCollaborationBinding:
        existing = self._list_models("trusted_task_collaboration", TaskCollaborationBinding, scope_key=task_id)
        if existing:
            return existing[0]
        pending = self.repository.list_approval_requests(task_id=task_id, status="pending")
        owner = self._default_actor_email()
        binding = TaskCollaborationBinding(
            version="1.0",
            binding_id=f"task-collaboration-{task_id}",
            task_id=task_id,
            owner=owner,
            reviewer="reviewer@example.com" if any(role.role_name == "reviewer" for role in self.list_user_role_bindings()) else owner,
            watchers=[user.email for user in self.list_user_accounts() if user.email != owner][:3],
            approval_assignee="approver" if pending else "",
            blocked_by="approval" if pending else "",
            waiting_for="human review" if pending else "",
            recent_activity=[f"{task_id} currently in {self.api.task_status(task_id)['status']}"],
        )
        self._save_model("trusted_task_collaboration", binding.binding_id, task_id, binding.updated_at.isoformat(), binding)
        return binding

    def collaboration_summary(self) -> CollaborationSummaryView:
        task_bindings = [self._ensure_task_collaboration_binding(str(task["task_id"])).to_dict() for task in self.repository.list_tasks()]
        summary = CollaborationSummaryView(
            version="1.0",
            summary_id=f"collaboration-summary-{uuid4().hex[:10]}",
            users=[user.to_dict() for user in self.list_user_accounts()],
            role_bindings=[binding.to_dict() for binding in self.list_user_role_bindings()],
            sessions=[session.to_dict() for session in self.list_browser_sessions()],
            task_bindings=task_bindings,
            invitations=[item.to_dict() for item in self.list_workspace_invitations()],
        )
        self._save_model("trusted_collaboration_summary", summary.summary_id, "global", summary.created_at.isoformat(), summary)
        return summary

    def _task_timeline(self, task_id: str) -> TaskTimelineView:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        events: list[dict[str, Any]] = []
        request = dict(task.get("request", {}))
        created_at = str(request.get("created_at", ""))
        if created_at:
            events.append({"timestamp": created_at, "lane": "contract", "label": "Contract compiled", "kind": "contract"})
        for node in (self.repository.load_plan(task_id).nodes if self.repository.load_plan(task_id) else []):
            events.append(
                {
                    "timestamp": created_at,
                    "lane": "plan",
                    "label": node.objective[:80],
                    "kind": node.node_category,
                    "status": node.status,
                }
            )
        for receipt in self.repository.list_execution_receipts(task_id):
            events.append(
                {
                    "timestamp": receipt.timestamp.isoformat(),
                    "lane": "execution",
                    "label": receipt.tool_used,
                    "kind": "execution_receipt",
                    "status": receipt.status,
                }
            )
        for checkpoint in self.repository.list_checkpoints(task_id):
            events.append(
                {
                    "timestamp": checkpoint.created_at.isoformat(),
                    "lane": "checkpoint",
                    "label": str(checkpoint.metadata.get("label", checkpoint.plan_node_id or checkpoint.checkpoint_id)),
                    "kind": "checkpoint",
                    "status": str(checkpoint.metadata.get("status", "recorded")),
                }
            )
        for approval in self.repository.list_approval_requests(task_id=task_id):
            events.append(
                {
                    "timestamp": approval.expiry_at.isoformat() if approval.expiry_at is not None else created_at,
                    "lane": "review",
                    "label": approval.action_summary or approval.reason,
                    "kind": "approval",
                    "status": approval.status,
                }
            )
        for usage in self.repository.list_provider_usage_records(task_id):
            events.append(
                {
                    "timestamp": usage.created_at.isoformat(),
                    "lane": "usage",
                    "label": usage.provider_name,
                    "kind": "provider_usage",
                    "status": usage.status,
                    "total_tokens": usage.total_tokens,
                }
            )
        events.sort(key=lambda item: item["timestamp"])
        timeline = TaskTimelineView(
            version="1.0",
            task_id=task_id,
            events=events,
            summary={
                "status": task["status"],
                "current_phase": task["current_phase"],
                "event_count": len(events),
                "approval_waits": sum(1 for item in events if item["kind"] == "approval" and item["status"] == "pending"),
            },
        )
        self._save_model("trusted_task_timeline", task_id, task_id, timeline.generated_at.isoformat(), timeline)
        return timeline

    def _evidence_trace(self, task_id: str) -> EvidenceTraceView:
        sources = self.repository.list_source_records(task_id)
        spans = self._synthesized_evidence_spans(task_id)
        claims = self.repository.load_claims(task_id)
        report = self.repository.load_latest_validation_report(task_id)
        trace_edges: list[dict[str, Any]] = []
        claim_dicts = [claim.to_dict() for claim in claims]
        for claim in claims:
            for ref in claim.evidence_refs:
                trace_edges.append({"from": ref, "to": claim.claim_id, "kind": "supports"})
        if report is not None:
            for ref in report.evidence_refs:
                trace_edges.append({"from": ref, "to": report.report_id, "kind": "validated_by"})
        trace = EvidenceTraceView(
            version="1.0",
            task_id=task_id,
            sources=[source.to_dict() for source in sources],
            spans=[span.to_dict() for span in spans],
            claims=claim_dicts,
            validations=[] if report is None else [report.to_dict()],
            trace_edges=trace_edges,
        )
        self._save_model("trusted_evidence_trace", task_id, task_id, trace.generated_at.isoformat(), trace)
        return trace

    def audit_overview(self) -> dict[str, Any]:
        trend = self._audit_trend()
        entries = self._audit_log_entries()
        return {
            "summary": trend.summary,
            "trend": trend.to_dict(),
            "items": [item.to_dict() for item in entries[-50:]],
            "bundles": [
                AuditEventBundle(
                    version="1.0",
                    bundle_id=f"audit-bundle-{task_id}",
                    task_id=task_id,
                    entries=[item for item in entries if item.task_id == task_id],
                ).to_dict()
                for task_id in sorted({item.task_id for item in entries})
            ],
        }

    def playbooks_overview(self) -> dict[str, Any]:
        items = [self._synthesized_playbook(str(task["task_id"])).to_dict() for task in self.repository.list_tasks()]
        return {"items": items, "review_cases": [item.to_dict() for item in self._review_cases()]}

    def benchmarks_overview(self) -> dict[str, Any]:
        summary = self._benchmark_summary()
        return {"summary": summary.to_dict()}

    def mcp_overview(self) -> dict[str, Any]:
        builtin_server = MCPServerRecord(
            version="1.0",
            server_id="mcp-server-ceos-runtime",
            display_name="CEOS Trusted Runtime",
            transport="in-process",
            endpoint="ceos://runtime",
            direction="server",
            enabled=True,
            status="ready",
        )
        self._save_model("trusted_mcp_server", builtin_server.server_id, builtin_server.direction, builtin_server.created_at.isoformat(), builtin_server)
        builtin_tools = [
            MCPToolRecord(version="1.0", tool_id="mcp-tool-task-inspection", server_id=builtin_server.server_id, tool_name="task_inspection", display_name="Task Inspection", description="Read-only task inspection.", permission_mode="read-only", schema_ref="contract-input"),
            MCPToolRecord(version="1.0", tool_id="mcp-tool-evidence-query", server_id=builtin_server.server_id, tool_name="evidence_query", display_name="Evidence Query", description="Query evidence traces and source spans.", permission_mode="read-only", schema_ref="evidence-source"),
            MCPToolRecord(version="1.0", tool_id="mcp-tool-audit-query", server_id=builtin_server.server_id, tool_name="audit_log_query", display_name="Audit Log Query", description="Query append-only audit events.", permission_mode="read-only", schema_ref="audit-log-entry"),
            MCPToolRecord(version="1.0", tool_id="mcp-tool-benchmark-query", server_id=builtin_server.server_id, tool_name="benchmark_query", display_name="Benchmark Query", description="Read benchmark and repro-eval state.", permission_mode="read-only", schema_ref="benchmark-run"),
            MCPToolRecord(version="1.0", tool_id="mcp-tool-playbook-query", server_id=builtin_server.server_id, tool_name="playbook_query", display_name="Playbook Query", description="Inspect trusted playbooks.", permission_mode="read-only", schema_ref="playbook-record"),
            MCPToolRecord(version="1.0", tool_id="mcp-tool-governed-action", server_id=builtin_server.server_id, tool_name="governed_action_submission", display_name="Governed Action Submission", description="Submit a governed action through the control plane.", permission_mode="approval-gated", schema_ref="mcp-tool-record"),
        ]
        for tool in builtin_tools:
            self._save_model("trusted_mcp_tool", tool.tool_id, tool.server_id, tool.created_at.isoformat(), tool)
        return {
            "schema_registry": self.schema_registry(),
            "server_surface": {
                "server": builtin_server.to_dict(),
                "tools": [tool.to_dict() for tool in builtin_tools],
            },
            "connected_servers": [item.to_dict() for item in self._list_models("trusted_mcp_server", MCPServerRecord) if item.server_id != builtin_server.server_id],
            "recent_invocations": [item.to_dict() for item in self._list_models("trusted_mcp_invocation", MCPInvocationRecord)][-20:],
            "permission_decisions": [item.to_dict() for item in self._list_models("trusted_mcp_permission", MCPPermissionDecision)][-20:],
        }

    def register_mcp_server(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = MCPServerRecord(
            version="1.0",
            server_id=str(payload.get("server_id") or f"mcp-server-{uuid4().hex[:10]}"),
            display_name=str(payload.get("display_name", "MCP Server")),
            transport=str(payload.get("transport", "stdio")),
            endpoint=str(payload.get("endpoint", "")),
            direction=str(payload.get("direction", "client")),
            enabled=bool(payload.get("enabled", True)),
            status=str(payload.get("status", "configured")),
            updated_at=utc_now(),
        )
        self._save_model("trusted_mcp_server", record.server_id, record.direction, (record.updated_at or record.created_at).isoformat(), record)
        return {"server": record.to_dict()}

    def register_mcp_tool(self, server_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = MCPToolRecord(
            version="1.0",
            tool_id=str(payload.get("tool_id") or f"mcp-tool-{uuid4().hex[:10]}"),
            server_id=server_id,
            tool_name=str(payload.get("tool_name", "tool")),
            display_name=str(payload.get("display_name", payload.get("tool_name", "tool"))),
            description=str(payload.get("description", "")),
            permission_mode=str(payload.get("permission_mode", "read-only")),
            schema_ref=str(payload.get("schema_ref", "")),
        )
        self._save_model("trusted_mcp_tool", record.tool_id, server_id, record.created_at.isoformat(), record)
        return {"tool": record.to_dict()}

    def invoke_mcp_tool(self, server_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        tool_name = str(payload.get("tool_name", "tool"))
        actor = str(payload.get("actor", self._default_actor_email()))
        task_id = str(payload.get("task_id", ""))
        arguments = dict(payload.get("arguments", {}))
        permission_mode = "approval_required" if tool_name in {"governed_action_submission"} else "allowed"
        invocation = MCPInvocationRecord(
            version="1.0",
            invocation_id=f"mcp-invocation-{uuid4().hex[:10]}",
            server_id=server_id,
            task_id=task_id,
            tool_name=tool_name,
            actor=actor,
            status="recorded",
            arguments=arguments,
            result_summary=f"Recorded invocation for {tool_name}",
            approval_required=permission_mode == "approval_required",
        )
        permission = MCPPermissionDecision(
            version="1.0",
            decision_id=f"mcp-permission-{uuid4().hex[:10]}",
            invocation_id=invocation.invocation_id,
            actor=actor,
            decision="approval_required" if invocation.approval_required else "allowed",
            rationale="Sensitive or policy-bound MCP actions remain governed." if invocation.approval_required else "Read-only MCP action allowed.",
        )
        self._save_model("trusted_mcp_invocation", invocation.invocation_id, server_id, invocation.created_at.isoformat(), invocation)
        self._save_model("trusted_mcp_permission", permission.decision_id, invocation.invocation_id, permission.created_at.isoformat(), permission)
        if task_id:
            self._save_model("trusted_task_collaboration", self._ensure_task_collaboration_binding(task_id).binding_id, task_id, utc_now().isoformat(), self._ensure_task_collaboration_binding(task_id))
        return {"invocation": invocation.to_dict(), "permission": permission.to_dict()}

    # ------------------------------------------------------------------
    # Usage
    # ------------------------------------------------------------------
    def _all_provider_usage_records(self) -> list[ProviderUsageRecord]:
        records: list[ProviderUsageRecord] = []
        for task in self.repository.list_tasks():
            records.extend(self.repository.list_provider_usage_records(str(task["task_id"])))
        records.sort(key=lambda item: item.created_at)
        return records

    def _parse_window_hours(self, window: str) -> int:
        normalized = window.strip().lower()
        if normalized.endswith("h"):
            return int(normalized[:-1])
        if normalized.endswith("d"):
            return int(normalized[:-1]) * 24
        return int(normalized)

    def _aggregate_usage(self, records: Iterable[ProviderUsageRecord], *, window_hours: int) -> dict[str, Any]:
        cutoff = utc_now() - timedelta(hours=window_hours)
        filtered = [item for item in records if item.created_at >= cutoff]
        provider_totals: dict[str, dict[str, Any]] = {}
        task_totals: dict[str, dict[str, Any]] = {}
        for item in filtered:
            provider_bucket = provider_totals.setdefault(
                item.provider_name,
                {"provider_name": item.provider_name, "total_tokens": 0, "estimated_cost": 0.0, "request_count": 0},
            )
            provider_bucket["total_tokens"] += item.total_tokens
            provider_bucket["estimated_cost"] += item.estimated_cost
            provider_bucket["request_count"] += 1
            task_bucket = task_totals.setdefault(
                item.task_id,
                {
                    "task_id": item.task_id,
                    "total_tokens": 0,
                    "estimated_cost": 0.0,
                    "request_count": 0,
                    "fallback_count": 0,
                    "provider_names": set(),
                },
            )
            task_bucket["total_tokens"] += item.total_tokens
            task_bucket["estimated_cost"] += item.estimated_cost
            task_bucket["request_count"] += 1
            task_bucket["fallback_count"] += 1 if item.fallback_used else 0
            task_bucket["provider_names"].add(item.provider_name)
        totals = {
            "request_count": sum(item["request_count"] for item in provider_totals.values()),
            "total_tokens": sum(item["total_tokens"] for item in provider_totals.values()),
            "estimated_cost": round(sum(item["estimated_cost"] for item in provider_totals.values()), 6),
        }
        provider_rows = sorted(provider_totals.values(), key=lambda item: item["total_tokens"], reverse=True)
        task_rows = []
        for task_id, row in task_totals.items():
            summary = TaskUsageSummary(
                version="1.0",
                summary_id=f"task-usage-{uuid4().hex[:10]}",
                task_id=task_id,
                total_tokens=int(row["total_tokens"]),
                estimated_cost=float(round(row["estimated_cost"], 6)),
                request_count=int(row["request_count"]),
                fallback_count=int(row["fallback_count"]),
                provider_names=sorted(str(item) for item in row["provider_names"]),
            )
            self._save_model("console_task_usage_summary", summary.summary_id, task_id, summary.updated_at.isoformat(), summary)
            task_rows.append(summary.to_dict())
        for provider_name, row in provider_totals.items():
            aggregate = TokenUsageAggregate(
                version="1.0",
                aggregate_id=f"usage-aggregate-{uuid4().hex[:10]}",
                scope_key="global",
                window_hours=window_hours,
                provider_name=provider_name,
                task_id="",
                total_tokens=int(row["total_tokens"]),
                estimated_cost=float(round(row["estimated_cost"], 6)),
                request_count=int(row["request_count"]),
            )
            self._save_model("console_token_usage_aggregate", aggregate.aggregate_id, "global", aggregate.created_at.isoformat(), aggregate)
        trends = self._build_provider_trends(filtered, window_hours=window_hours)
        alerts = self._usage_alerts(provider_rows, totals)
        return {
            "window_hours": window_hours,
            "totals": totals,
            "providers": provider_rows,
            "tasks": sorted(task_rows, key=lambda item: item["total_tokens"], reverse=True),
            "trends": [item.to_dict() for item in trends],
            "alerts": [item.to_dict() for item in alerts],
        }

    def _build_provider_trends(self, records: list[ProviderUsageRecord], *, window_hours: int) -> list[ProviderUsageTrend]:
        buckets: dict[tuple[str, str], dict[str, Any]] = {}
        for item in records:
            hour_bucket = item.created_at.replace(minute=0, second=0, microsecond=0).isoformat()
            key = (item.provider_name, hour_bucket)
            bucket = buckets.setdefault(key, {"timestamp": hour_bucket, "total_tokens": 0, "estimated_cost": 0.0})
            bucket["total_tokens"] += item.total_tokens
            bucket["estimated_cost"] += item.estimated_cost
        by_provider: dict[str, list[dict[str, Any]]] = {}
        for (provider_name, _), payload in buckets.items():
            by_provider.setdefault(provider_name, []).append(payload)
        trends: list[ProviderUsageTrend] = []
        for provider_name, points in by_provider.items():
            trend = ProviderUsageTrend(
                version="1.0",
                trend_id=f"provider-trend-{uuid4().hex[:10]}",
                provider_name=provider_name,
                window_hours=window_hours,
                points=sorted(points, key=lambda item: item["timestamp"]),
            )
            self._save_model("console_provider_usage_trend", trend.trend_id, provider_name, trend.created_at.isoformat(), trend)
            trends.append(trend)
        return trends

    def _usage_alerts(self, provider_rows: list[dict[str, Any]], totals: dict[str, Any]) -> list[UsageAlertRecord]:
        alerts: list[UsageAlertRecord] = []
        if totals["total_tokens"] >= 100000:
            alerts.append(
                UsageAlertRecord(
                    version="1.0",
                    alert_id=f"usage-alert-{uuid4().hex[:10]}",
                    scope_key="global",
                    severity="warning",
                    summary="High token consumption in the current window.",
                    category="high-spend",
                )
            )
        if any(row["request_count"] >= 10 and row["total_tokens"] >= 10000 for row in provider_rows):
            alerts.append(
                UsageAlertRecord(
                    version="1.0",
                    alert_id=f"usage-alert-{uuid4().hex[:10]}",
                    scope_key="global",
                    severity="warning",
                    summary="One or more providers show elevated request volume.",
                    category="provider-spike",
                )
            )
        for alert in alerts:
            self._save_model("console_usage_alert", alert.alert_id, alert.scope_key, alert.created_at.isoformat(), alert)
        return alerts

    def usage_summary(self, *, window: str = "24h") -> dict[str, Any]:
        return self._aggregate_usage(self._all_provider_usage_records(), window_hours=self._parse_window_hours(window))

    def task_usage_summary(self, task_id: str, *, window: str = "24h") -> dict[str, Any]:
        records = [item for item in self.repository.list_provider_usage_records(task_id) if item.created_at >= utc_now() - timedelta(hours=self._parse_window_hours(window))]
        total_tokens = sum(item.total_tokens for item in records)
        total_cost = round(sum(item.estimated_cost for item in records), 6)
        return {
            "task_id": task_id,
            "request_count": len(records),
            "total_tokens": total_tokens,
            "estimated_cost": total_cost,
            "providers": sorted({item.provider_name for item in records}),
            "records": [item.to_dict() for item in records],
        }

    # ------------------------------------------------------------------
    # UI read models
    # ------------------------------------------------------------------
    def dashboard_summary(self) -> dict[str, Any]:
        system = self.api.system_report()
        usage = self.usage_summary(window="24h")
        audit = self.audit_overview()
        benchmark_summary = self.benchmarks_overview()["summary"]
        collaboration = self.collaboration_summary()
        recent_tasks = []
        for task in self.repository.list_tasks()[:8]:
            task_detail = self.repository.get_task(str(task["task_id"]))
            recent_tasks.append(
                {
                    "task_id": str(task["task_id"]),
                    "status": task["status"],
                    "current_phase": task["current_phase"],
                    "latest_checkpoint_id": task["latest_checkpoint_id"],
                    "goal": "" if task_detail is None else str(task_detail["request"].get("goal", "")),
                    "blocked_reason": "approval pending" if task["status"] == "awaiting_approval" else "",
                }
            )
        approvals = [item.to_dict() for item in self.repository.list_approval_requests(status="pending")]
        maintenance = self.api.maintenance_report()
        maintenance_report = maintenance.get("report", {})
        return {
            "system": system,
            "recent_tasks": recent_tasks,
            "approvals": approvals,
            "maintenance": maintenance,
            "usage": usage,
            "audit": audit["summary"],
            "benchmarks": benchmark_summary,
            "collaboration": {
                "user_count": len(collaboration.users),
                "session_count": len(collaboration.sessions),
                "task_binding_count": len(collaboration.task_bindings),
            },
            "health_badges": {
                "setup_required": not self.has_admin_account(),
                "provider_fallback": any(int(item.get("fallback_count", 0)) > 0 for item in usage["tasks"]),
                "maintenance_incidents": len(maintenance_report.get("incidents", [])),
            },
        }

    def task_cockpit(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task": task,
            "status": self.api.task_status(task_id),
            "handoff": self.api.handoff_packet_for_task(task_id),
            "checkpoints": self.api.checkpoints(task_id),
            "open_questions": self.api.open_questions(task_id),
            "next_actions": self.api.next_actions(task_id),
            "approvals": [item.to_dict() for item in self.api.approval_inbox(task_id=task_id)],
            "memory": self.api.memory_kernel_state(task_id),
            "timeline": self._task_timeline(task_id).to_dict(),
            "evidence_trace": self._evidence_trace(task_id).to_dict(),
            "playbook": self._synthesized_playbook(task_id).to_dict(),
            "review_cases": [item.to_dict() for item in self._review_cases(task_id)],
            "collaboration": self._ensure_task_collaboration_binding(task_id).to_dict(),
            "usage": self.task_usage_summary(task_id),
            "software": self.api.software_action_receipts(task_id=task_id, with_replay_diagnostics=True),
            "replay": self.api.trace_bundle(task_id),
        }

    def memory_overview(self) -> dict[str, Any]:
        tasks = self.repository.list_tasks()
        task_cards = []
        for task in tasks[:8]:
            task_id = str(task["task_id"])
            kernel = self.api.memory_kernel_state(task_id)
            task_cards.append(
                {
                    "task_id": task_id,
                    "timeline_view": kernel["timeline_view"],
                    "project_state_view": kernel["project_state_view"],
                    "maintenance_mode": self.api.memory_maintenance_mode(task_id),
                }
            )
        return {"items": task_cards}

    def software_overview(self) -> dict[str, Any]:
        harnesses = self.api.list_cli_anything_harnesses()
        return {
            "harnesses": [item.to_dict() for item in harnesses],
            "report": self.api.software_control_report(),
            "failure_clusters": self.api.software_failure_clusters()["items"],
            "recovery_hints": self.api.software_recovery_hints()["items"],
        }

    def maintenance_overview(self) -> dict[str, Any]:
        tasks = self.repository.list_tasks()
        task_payloads = []
        for task in tasks[:8]:
            task_id = str(task["task_id"])
            task_payloads.append(
                {
                    "task_id": task_id,
                    "mode": self.api.memory_maintenance_mode(task_id),
                    "incidents": self.api.memory_maintenance_incidents(task_id)["items"],
                    "recommendations": self.api.memory_maintenance_recommendation(task_id)["recommendation"],
                    "daemon": self.api.maintenance_daemon_state(task_id),
                }
            )
        return {"items": task_payloads}

    def approvals_inbox(self) -> dict[str, Any]:
        requests = [item.to_dict() for item in self.repository.list_approval_requests(status="pending")]
        return {"items": requests}

    def decide_approval(self, *, request_id: str, approver: str, status: str, rationale: str) -> dict[str, Any]:
        decision = self.api.decide_approval(
            request_id=request_id,
            approver=approver,
            status=status,
            rationale=rationale,
        )
        return decision.to_dict()

    def doctor_report(self) -> dict[str, Any]:
        startup = self.api.startup_validation()
        system = self.api.system_report()
        config = self.config_effective()
        provider_check = self.test_provider_connection()
        audit = self.audit_overview()
        benchmarks = self.benchmarks_overview()["summary"]
        frontend_dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
        frontend_index = frontend_dist / "index.html"
        frontend_assets = frontend_dist / "assets"
        frontend_status = "ready" if frontend_index.exists() else "missing-build"
        return {
            "startup": startup,
            "system": system["summary"],
            "config": config,
            "provider_check": provider_check,
            "admin_exists": self.has_admin_account(),
            "setup_required": not self.has_admin_account(),
            "audit_ledger": {
                "status": "healthy" if audit["summary"]["total_events"] > 0 else "empty",
                "event_count": audit["summary"]["total_events"],
            },
            "benchmark_reproducibility": {
                "status": "ready" if benchmarks["suites"] else "baseline-only",
                "suite_count": len(benchmarks["suites"]),
                "run_count": len(benchmarks["latest_runs"]),
                "repro_run_count": len(benchmarks["repro_runs"]),
            },
            "oidc_readiness": {
                "configured_provider_count": len(self.list_oidc_provider_configs()),
                "status": "configured" if self.list_oidc_provider_configs() else "optional-not-configured",
            },
            "frontend": {
                "status": frontend_status,
                "dist_path": str(frontend_dist),
                "index_present": frontend_index.exists(),
                "assets_present": frontend_assets.exists(),
                "recommended_action": None
                if frontend_index.exists()
                else "Run ./scripts/install.sh again or build the frontend with `cd frontend && npm install && npm run build`.",
            },
            "oidc_providers": [item.to_dict() for item in self.list_oidc_provider_configs()],
        }

    def event_stream_payloads(self) -> list[tuple[str, dict[str, Any]]]:
        return [
            ("dashboard", self.dashboard_summary()),
            ("usage", self.usage_summary(window="24h")),
            ("maintenance", self.maintenance_overview()),
            ("approvals", self.approvals_inbox()),
            ("audit", self.audit_overview()),
            ("benchmarks", self.benchmarks_overview()),
        ]
