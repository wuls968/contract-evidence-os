from pathlib import Path


def test_install_script_and_readme_present_a_clear_local_first_story() -> None:
    root = Path(__file__).resolve().parents[2]
    readme = (root / "README.md").read_text(encoding="utf-8").lower()
    install_script = root / "scripts" / "install.sh"
    uninstall_script = root / "scripts" / "uninstall.sh"

    assert install_script.exists()
    assert uninstall_script.exists()
    install_text = install_script.read_text(encoding="utf-8")
    uninstall_text = uninstall_script.read_text(encoding="utf-8")
    assert ".venv" in install_text
    assert ".local/bin" in install_text
    assert "ceos" in install_text
    assert "--init-config" in install_text
    assert "--config-path" in install_text
    assert "--env-path" in install_text
    assert "config.local.json" in install_text
    assert ".env.local" in install_text
    assert "ceos_operator_token" in install_text.lower()
    assert "ceos_api_key" in install_text.lower()
    assert "ceos_api_base_url" in install_text.lower()
    assert "read -r -p" in install_text
    assert "verify" in install_text.lower()
    assert "npm" in install_text.lower()
    assert "frontend" in install_text.lower()
    assert "--remove-venv" in uninstall_text
    assert "installed by contract-evidence os install.sh" in uninstall_text.lower()

    assert "auditable ai agent" in readme
    assert "agent operating system" in readme
    assert "long-term memory agent" in readme
    assert "desktop automation agent" in readme
    assert "self-hosted ai agent runtime" in readme
    assert "./scripts/install.sh" in readme
    assert "./scripts/uninstall.sh" in readme
    assert "git clone" in readme
    assert "```mermaid" in readme
    assert "see the system in one view" in readme
    assert "--init-config" in readme
    assert "dashboard" in readme
    assert "/setup" in readme
    assert "/login" in readme
    assert "/usage" in readme
    assert "config.local.json" in readme
    assert ".env.local" in readme
    assert "source runtime/.env.local" in readme
    assert "ceos_operator_token" in readme
    assert "ceos_api_key" in readme
    assert "memory scopes" in readme
    assert "strategy control plane" in readme
    assert "leases, branches, and handoff" in readme
    assert "architecture at a glance" in readme
    assert "feature comparison at a glance" in readme
    assert "small-team-best-practices.md" in readme
    assert "operator-v1-user-manual.md" in readme
    assert "getting-started.md" in readme
    assert "user-guide.md" in readme
    assert "trusted ai runtime" in readme
    assert "small teams" in readme or "small-team" in readme
