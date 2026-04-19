"""Version-safe payload migration hooks."""

from __future__ import annotations

from typing import Any


def migrate_payload(table: str, payload: dict[str, Any], record_version: str) -> dict[str, Any]:
    """Upgrade persisted payloads into the current in-memory schema."""

    migrated = dict(payload)
    if table == "audit_events":
        migrated.setdefault("risk_level", "low")
        migrated["version"] = "1.0"
    if table == "tool_invocations":
        migrated.setdefault("idempotency_key", "")
        migrated.setdefault("attempt", 1)
        migrated.setdefault("simulator_used", False)
        migrated.setdefault("mock_used", False)
        migrated["version"] = "1.0"
    if table == "tool_results":
        migrated.setdefault("provenance", {})
        migrated.setdefault("confidence", None)
        migrated.setdefault("provider_mode", "live")
        migrated.setdefault("deterministic", False)
        migrated["version"] = "1.0"
    return migrated
