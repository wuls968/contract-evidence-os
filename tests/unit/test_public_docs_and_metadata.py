from pathlib import Path


def test_public_docs_and_metadata_match_the_current_runtime_story() -> None:
    root = Path(__file__).resolve().parents[2]
    readme = (root / "README.md").read_text(encoding="utf-8")
    future = (root / "docs" / "architecture" / "future-extension-path.md").read_text(encoding="utf-8")
    model_index = (root / "docs" / "schemas" / "model-index.md").read_text(encoding="utf-8")
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")

    assert "AMOS" in readme
    assert "software control fabric" in readme
    assert "0.9.0" in pyproject
    assert "operator api v1" in readme.lower()
    assert "memory kernel" in future.lower()
    assert "software control" in future.lower()
    assert "MemoryWriteReceipt" in model_index
    assert "SoftwareActionReceipt" in model_index

    assert (root / "docs" / "api" / "operator-v1.md").exists()
    assert (root / ".github" / "workflows" / "ci.yml").exists()
    assert (root / ".coveragerc").exists()
    assert (root / "LICENSE").exists()
