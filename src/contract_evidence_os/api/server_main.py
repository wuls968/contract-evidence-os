"""Package entrypoint for the remote operator service."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from contract_evidence_os.api.server import RemoteOperatorService
from contract_evidence_os.config import RuntimeConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ceos-server")
    parser.add_argument("--storage-root")
    parser.add_argument("--config")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--token")
    parser.add_argument("--backend-kind")
    parser.add_argument("--backend-url")
    parser.add_argument("--shared-state-kind")
    parser.add_argument("--shared-state-url")
    parser.add_argument("--trust-mode")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = RuntimeConfig.load(
        config_path=None if args.config is None else Path(args.config),
        overrides={} if args.storage_root is None else {"storage_root": args.storage_root},
    )
    token = args.token
    if not token:
        token_env = str(config.service.get("token_env", "CEOS_OPERATOR_TOKEN"))
        token = os.environ.get(token_env, "")
    if not token:
        raise SystemExit(
            "operator token is required via --token or "
            f"{config.service.get('token_env', 'CEOS_OPERATOR_TOKEN')}. "
            "If you used ./scripts/install.sh --init-config, run: source runtime/.env.local"
        )
    service = RemoteOperatorService(
        storage_root=Path(config.storage_root),
        token=token,
        host=str(args.host or config.service.get("host", "127.0.0.1")),
        port=int(args.port or config.service.get("port", 8080)),
        bootstrap_scopes=[str(item) for item in config.auth.get("bootstrap_scopes", [])],
        max_request_bytes=int(config.auth.get("max_request_bytes", 65536)),
        admin_allowlist=[str(item) for item in config.auth.get("admin_allowlist", ["127.0.0.1", "::1"])],
        queue_backend_kind=str(args.backend_kind or config.external_backend.get("kind", "sqlite")),
        coordination_backend_kind=str(args.backend_kind or config.external_backend.get("kind", "sqlite")),
        external_backend_url=str(args.backend_url or config.external_backend.get("url", "")) or None,
        external_backend_namespace=str(config.external_backend.get("namespace", "ceos")),
        shared_state_backend_kind=str(args.shared_state_kind or config.shared_state_backend.get("kind", "sqlite")),
        shared_state_backend_url=str(args.shared_state_url or config.shared_state_backend.get("url", "")) or None,
        trust_mode=str(args.trust_mode or config.trust.get("mode", "standard")),
        cli_anything_repo_path=str(config.software_control.get("repo_path", "")) or None,
        provider_settings=dict(config.provider),
    )
    service.serve_forever()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
