from pathlib import Path


def test_release_engineering_assets_cover_build_and_container_defaults() -> None:
    root = Path(__file__).resolve().parents[2]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")

    entrypoint = root / "scripts" / "docker-entrypoint.sh"

    assert "build>=" in pyproject
    assert "pytest-cov>=" in pyproject
    assert "python -m build --sdist --wheel" in ci
    assert "pip install dist/*.whl" in ci
    assert entrypoint.exists()
    assert 'ENTRYPOINT ["scripts/docker-entrypoint.sh"]' in dockerfile
    entrypoint_text = entrypoint.read_text(encoding="utf-8")
    assert "ceos-server --host 0.0.0.0" in entrypoint_text
    assert "CEOS_OPERATOR_TOKEN" in entrypoint_text
    assert "dist/" in gitignore
    assert "build/" in gitignore
    assert "/runtime/" in gitignore


def test_python_package_subpackages_are_explicit_packages() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "contract_evidence_os"
    expected = [
        "agents",
        "api",
        "audit",
        "continuity",
        "contracts",
        "evals",
        "evidence",
        "evolution",
        "memory",
        "observability",
        "planning",
        "policy",
        "recovery",
        "runtime",
        "tools",
        "tools/anything_cli",
        "tools/connectors",
        "tools/files",
        "tools/gui",
        "tools/sandbox",
        "tools/shell",
        "tools/verification",
        "tools/web",
        "verification",
    ]

    for package in expected:
        assert (root / package / "__init__.py").exists(), package
