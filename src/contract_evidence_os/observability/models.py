"""Observability models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from contract_evidence_os.base import SchemaModel, utc_now


@dataclass
class TelemetryEvent(SchemaModel):
    """Structured operational telemetry event."""

    version: str
    event_id: str
    task_id: str
    event_type: str
    payload: dict[str, Any]
    timestamp: datetime

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ObservabilityMetricSnapshot(SchemaModel):
    """Authoritative persisted operator metrics snapshot."""

    version: str
    snapshot_id: str
    scope_key: str
    runtime_summary: dict[str, Any]
    controller_versions: dict[str, str]
    maintenance_summary: dict[str, Any]
    software_control_summary: dict[str, Any]
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ObservabilityTrendReport(SchemaModel):
    """Windowed trend report derived from authoritative metrics snapshots."""

    version: str
    report_id: str
    scope_key: str
    window_hours: int
    snapshot_ids: list[str]
    counters: dict[str, float]
    latest_snapshot_at: datetime | None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class ObservabilityAlertRecord(SchemaModel):
    """Persisted operator-visible alert derived from observability thresholds."""

    version: str
    alert_id: str
    scope_key: str
    severity: str
    category: str
    summary: str
    created_at: datetime = field(default_factory=utc_now)
    status: str = "open"

    def __post_init__(self) -> None:
        self.validate()


@dataclass
class SoftwareControlTelemetryRecord(SchemaModel):
    """Persisted observability record for governed software-control behavior."""

    version: str
    telemetry_id: str
    scope_key: str
    harness_id: str
    action_receipt_id: str
    risk_level: str
    result_status: str
    replayable: bool
    failure_classification: str | None
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()
