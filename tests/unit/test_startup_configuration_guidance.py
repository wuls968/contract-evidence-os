import json
from pathlib import Path

import pytest

from contract_evidence_os.api.server_main import main as server_main


def test_server_startup_error_tells_user_how_to_load_local_env(tmp_path: Path) -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.delenv("CEOS_OPERATOR_TOKEN", raising=False)
    config_path = tmp_path / "config.local.json"
    config_path.write_text(
        json.dumps(
            {
                "storage_root": str(tmp_path / "runtime"),
                "service": {
                    "host": "127.0.0.1",
                    "port": 8080,
                    "token_env": "CEOS_OPERATOR_TOKEN",
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as excinfo:
        server_main(["--config", str(config_path)])

    message = str(excinfo.value)
    assert "CEOS_OPERATOR_TOKEN" in message
    assert "source runtime/.env.local" in message
    monkeypatch.undo()
