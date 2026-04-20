"""Authentication, account, and OIDC lifecycle for the browser console."""

from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from typing import Any
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.console._base import ConsoleSubservice
from contract_evidence_os.console.common import ROLE_SCOPES, SessionPrincipal, _slugify
from contract_evidence_os.console.models import (
    BrowserSession,
    OIDCLoginState,
    OIDCProviderConfig,
    UserAccount,
    UserPasswordCredential,
    UserRoleBinding,
)
from contract_evidence_os.trusted_runtime.models import SessionAuditRecord, WorkspaceInvitation


class ConsoleAuthService(ConsoleSubservice):
    """Own account, session, invitation, and OIDC behavior."""

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
        result = self._new_config_validation_result(
            validation_kind="oidc",
            status=status,
            messages=messages or ["OIDC configuration shape looks valid."],
            details={"provider_id": payload.get("provider_id", ""), "display_name": payload.get("display_name", "")},
        )
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
