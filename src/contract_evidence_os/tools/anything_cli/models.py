"""Typed models for governed CLI-Anything software control."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from contract_evidence_os.base import SchemaModel, utc_now


@dataclass
class SoftwareHarnessRecord(SchemaModel):
    """Registered software harness generated or managed through CLI-Anything."""

    version: str
    harness_id: str
    source_kind: str
    software_name: str
    executable_name: str
    executable_path: str
    harness_root: str
    skill_path: str
    discovery_mode: str
    status: str
    supports_json: bool
    supports_repl: bool
    default_risk_level: str
    command_count: int
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SoftwareCommandDescriptor(SchemaModel):
    """One discovered command path for a software harness."""

    version: str
    command_id: str
    harness_id: str
    command_path: list[str]
    description: str
    risk_level: str
    approval_required: bool
    supports_json: bool
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SoftwareControlPolicy(SchemaModel):
    """Governance policy for a registered software harness."""

    version: str
    policy_id: str
    harness_id: str
    source_kind: str
    require_json_output: bool
    allow_repl: bool
    high_risk_patterns: list[str]
    destructive_patterns: list[str]
    blocked_patterns: list[str]
    default_timeout_seconds: int
    evidence_capture_mode: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()

    def classify(self, command_path: list[str]) -> tuple[str, bool, bool]:
        """Return risk level, approval requirement, and blocked state."""

        lowered = " ".join(command_path).lower()
        if any(pattern.lower() in lowered for pattern in self.blocked_patterns):
            return "blocked", True, True
        if any(pattern.lower() in lowered for pattern in self.destructive_patterns):
            return "destructive", True, False
        if any(pattern.lower() in lowered for pattern in self.high_risk_patterns):
            return "high", True, False
        return "low", False, False


@dataclass
class SoftwareHarnessValidation(SchemaModel):
    """Validation result for one registered software harness."""

    version: str
    validation_id: str
    harness_id: str
    status: str
    checks: dict[str, bool]
    issues: list[str]
    executable_version: str
    validated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SoftwareRiskClass(SchemaModel):
    """Stable description of one governed software action risk class."""

    version: str
    risk_level: str
    approval_required: bool
    blocked: bool
    description: str

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class AppCapabilityRecord(SchemaModel):
    """Machine-readable capability summary for one governed app harness."""

    version: str
    capability_id: str
    harness_id: str
    software_name: str
    supports_json: bool
    supports_replay: bool
    command_count: int
    approval_required_count: int
    destructive_count: int
    evidence_capture_mode: str
    capability_taxonomy: list[str] = field(default_factory=list)
    supported_modes: list[str] = field(default_factory=list)
    risk_families: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class HarnessManifest(SchemaModel):
    """Stable manifest for a governed software harness."""

    version: str
    manifest_id: str
    harness_id: str
    software_name: str
    harness: SoftwareHarnessRecord
    commands: list[SoftwareCommandDescriptor]
    policy: SoftwareControlPolicy
    risk_classes: list[SoftwareRiskClass]
    app_capability: AppCapabilityRecord
    validation_status: str
    automation_tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SoftwareActionReceipt(SchemaModel):
    """Auditable receipt for one governed software control action."""

    version: str
    action_id: str
    task_id: str
    harness_id: str
    software_name: str
    command_path: list[str]
    arguments: list[str]
    risk_level: str
    approval_request_ids: list[str]
    invocation_id: str
    result_status: str
    execution_receipt_id: str
    evidence_refs: list[str]
    artifact_refs: list[str]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SoftwareReplayRecord(SchemaModel):
    """Replay-oriented record for a governed software action."""

    version: str
    replay_id: str
    action_receipt_id: str
    task_id: str
    harness_id: str
    command_signature: str
    status: str
    created_at: datetime = field(default_factory=utc_now)
    last_result_status: str = ""

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SoftwareFailurePattern(SchemaModel):
    """Aggregated failure pattern for repeated governed software actions."""

    version: str
    pattern_id: str
    harness_id: str
    software_name: str
    command_signature: str
    failure_classification: str
    occurrence_count: int
    recent_receipt_ids: list[str]
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SoftwareAutomationMacro(SchemaModel):
    """Governed multi-step automation macro for one registered harness."""

    version: str
    macro_id: str
    harness_id: str
    software_name: str
    name: str
    description: str
    steps: list[dict[str, Any]]
    approval_required: bool
    automation_tags: list[str]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SoftwareReplayDiagnostic(SchemaModel):
    """Operator-visible explanation for whether a software action is replayable."""

    version: str
    diagnostic_id: str
    task_id: str
    harness_id: str
    replay_id: str
    action_receipt_id: str
    reproducibility: str
    explanation: str
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SoftwareRecoveryHint(SchemaModel):
    """Recovery or workaround hint derived from governed software traces."""

    version: str
    hint_id: str
    harness_id: str
    software_name: str
    trigger_signature: str
    recommendation: str
    source_receipt_ids: list[str]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SoftwareFailureCluster(SchemaModel):
    """Higher-level operator-visible grouping of repeated software failures."""

    version: str
    cluster_id: str
    harness_id: str
    software_name: str
    failure_classification: str
    command_signatures: list[str]
    occurrence_count: int
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SoftwareControlBridgeConfig(SchemaModel):
    """Configuration for a CLI-Anything builder bridge."""

    version: str
    bridge_id: str
    source_kind: str
    repo_path: str
    codex_skill_path: str
    enabled: bool
    builder_capabilities: list[str]
    last_synced_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SoftwareBuildRequest(SchemaModel):
    """Tracked build/refine/validate request against a CLI-Anything repository."""

    version: str
    build_request_id: str
    source_kind: str
    target: str
    mode: str
    focus: str
    repo_path: str
    status: str
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()
