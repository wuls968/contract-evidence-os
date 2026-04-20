from __future__ import annotations

import json
from pathlib import Path


def test_frontend_console_exposes_trusted_runtime_pages_and_charts() -> None:
    repo = Path("/Users/a0000/contract-evidence-os")
    app_source = (repo / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    package_json = json.loads((repo / "frontend" / "package.json").read_text(encoding="utf-8"))

    assert "echarts" in package_json["dependencies"]
    assert 'path="/audit"' in app_source
    assert 'path="/benchmarks"' in app_source
    assert 'path="/playbooks"' in app_source
    assert 'path="/collaboration"' in app_source
    assert 'path="/mcp"' in app_source
    assert "buildTimelineOption" in app_source
    assert "buildUsageTrendOption" in app_source
    assert 'requestJson(`/ui/tasks/${taskId}/leases`' in app_source
    assert 'requestJson(`/ui/tasks/${taskId}/branches`' in app_source
    assert 'requestJson(`/ui/tasks/${taskId}/handoff`' in app_source
    assert 'requestJson(`/ui/tasks/${taskId}/strategy/candidates`' in app_source
