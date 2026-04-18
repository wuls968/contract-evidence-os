"""Dispatcher-role entrypoint for queue and worker-pool supervision."""

from __future__ import annotations

import argparse
from pathlib import Path

from contract_evidence_os.config import RuntimeConfig
from contract_evidence_os.runtime.service import RuntimeService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ceos-dispatcher")
    parser.add_argument("--storage-root")
    parser.add_argument("--config")
    parser.add_argument("--reclaim-stale-workers", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = RuntimeConfig.load(
        config_path=None if args.config is None else Path(args.config),
        overrides={} if args.storage_root is None else {"storage_root": args.storage_root},
    )
    backend_kind = str(config.external_backend.get("kind", "sqlite"))
    backend_url = str(config.external_backend.get("url", "")) or None
    runtime = RuntimeService(
        storage_root=Path(config.storage_root),
        queue_backend_kind=backend_kind,
        coordination_backend_kind=backend_kind,
        external_backend_url=backend_url,
        external_backend_namespace=str(config.external_backend.get("namespace", "ceos")),
        shared_state_backend_kind=str(config.shared_state_backend.get("kind", "sqlite")),
        shared_state_backend_url=str(config.shared_state_backend.get("url", "")) or None,
        trust_mode=str(config.trust.get("mode", "standard")),
        cli_anything_repo_path=str(config.software_control.get("repo_path", "")) or None,
    )
    runtime.recover_stale_queue_leases(force_expire=args.reclaim_stale_workers)
    runtime.reclaim_stale_workers(force_expire=args.reclaim_stale_workers)
    runtime.provider_pool.pressure_snapshot()
    runtime.repository.save_provider_pool_state(runtime.provider_pool.pool_state())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
