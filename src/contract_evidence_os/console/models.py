"""Models for the browser-facing UX console."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from contract_evidence_os.base import SchemaModel, utc_now


@dataclass
class UserAccount(SchemaModel):
    """Human user account for the UX console."""

    version: str
    user_id: str
    email: str
    display_name: str
    status: str
    auth_source: str
    external_subject: str = ""
    created_at: datetime = field(default_factory=utc_now)
    last_login_at: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class UserPasswordCredential(SchemaModel):
    """Local password credential for a UX console user."""

    version: str
    credential_id: str
    user_id: str
    password_hash: str
    password_salt: str
    algorithm: str
    created_at: datetime = field(default_factory=utc_now)
    rotated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class UserRoleBinding(SchemaModel):
    """Role binding for a UX console user."""

    version: str
    binding_id: str
    user_id: str
    role_name: str
    scopes: list[str]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class BrowserSession(SchemaModel):
    """Cookie-backed browser session."""

    version: str
    session_id: str
    user_id: str
    scopes: list[str]
    status: str
    created_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    last_seen_at: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class OIDCProviderConfig(SchemaModel):
    """Generic OIDC provider configuration."""

    version: str
    provider_id: str
    display_name: str
    issuer: str
    client_id: str
    client_secret_env: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: list[str]
    enabled: bool
    preset_name: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class OIDCLoginState(SchemaModel):
    """Pending OIDC login state."""

    version: str
    state_id: str
    provider_id: str
    redirect_uri: str
    nonce: str
    created_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    next_path: str = "/dashboard"
    code_verifier: str = ""

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class DashboardPreference(SchemaModel):
    """Per-user dashboard preference."""

    version: str
    preference_id: str
    user_id: str
    preference_key: str
    value: dict[str, Any]
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class TokenUsageAggregate(SchemaModel):
    """Aggregated token usage across a time window."""

    version: str
    aggregate_id: str
    scope_key: str
    window_hours: int
    provider_name: str
    task_id: str
    total_tokens: int
    estimated_cost: float
    request_count: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ProviderUsageTrend(SchemaModel):
    """Windowed provider usage trend."""

    version: str
    trend_id: str
    provider_name: str
    window_hours: int
    points: list[dict[str, Any]]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class TaskUsageSummary(SchemaModel):
    """Task-level usage summary for the dashboard."""

    version: str
    summary_id: str
    task_id: str
    total_tokens: int
    estimated_cost: float
    request_count: int
    fallback_count: int
    provider_names: list[str]
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class UsageAlertRecord(SchemaModel):
    """Operator-visible usage alert."""

    version: str
    alert_id: str
    scope_key: str
    severity: str
    summary: str
    category: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ConfigValidationResult(SchemaModel):
    """Config validation or connection-test result."""

    version: str
    result_id: str
    validation_kind: str
    status: str
    messages: list[str]
    details: dict[str, Any]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()
