from pathlib import Path


def test_public_docs_and_metadata_match_the_current_runtime_story() -> None:
    root = Path(__file__).resolve().parents[2]
    readme = (root / "README.md").read_text(encoding="utf-8")
    future = (root / "docs" / "architecture" / "future-extension-path.md").read_text(encoding="utf-8")
    model_index = (root / "docs" / "schemas" / "model-index.md").read_text(encoding="utf-8")
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    manual = (root / "docs" / "manual" / "getting-started.md").read_text(encoding="utf-8")
    user_guide = (root / "docs" / "manual" / "user-guide.md").read_text(encoding="utf-8")
    team_runbook = (root / "docs" / "runbooks" / "small-team-best-practices.md").read_text(encoding="utf-8")
    api_manual = (root / "docs" / "api" / "operator-v1-user-manual.md").read_text(encoding="utf-8")

    assert "AMOS" in readme
    assert "software control fabric" in readme
    assert "0.9.0" in pyproject
    assert "operator api v1" in readme.lower()
    assert "trusted runtime" in readme.lower()
    assert "memory kernel" in future.lower()
    assert "software control" in future.lower()
    assert "MemoryWriteReceipt" in model_index
    assert "SoftwareActionReceipt" in model_index
    assert "API key" in manual
    assert "CEOS_OPERATOR_TOKEN" in manual
    assert "CEOS_API_KEY" in manual
    assert "ceos-server" in manual
    assert "Dashboard" in user_guide
    assert "OIDC" in user_guide
    assert "MCP" in user_guide
    assert "leases, branches, and handoffs" in user_guide
    assert "strategy control plane" in user_guide.lower()
    assert "audit" in user_guide.lower()
    assert "benchmark" in user_guide.lower()
    assert "small-team best practices" in team_runbook.lower()
    assert "owner" in team_runbook.lower()
    assert "reviewer" in team_runbook.lower()
    assert "lease" in team_runbook.lower()
    assert "handoff" in team_runbook.lower()
    assert "bearer" in api_manual.lower()
    assert "/v1/tasks/{task_id}/collaboration" in api_manual
    assert "/v1/strategy/overview" in api_manual
    assert "curl" in api_manual.lower()

    assert (root / "docs" / "api" / "operator-v1.md").exists()
    assert (root / "docs" / "api" / "operator-v1-user-manual.md").exists()
    assert (root / ".github" / "workflows" / "ci.yml").exists()
    assert (root / ".coveragerc").exists()
    assert (root / "LICENSE").exists()
    assert (root / "docs" / "manual" / "getting-started.md").exists()
    assert (root / "docs" / "manual" / "user-guide.md").exists()
    assert (root / "docs" / "runbooks" / "small-team-best-practices.md").exists()
