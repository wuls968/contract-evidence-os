"""Maintenance-role entrypoint for cleanup, restart recovery, and reindexing helpers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from dataclasses import is_dataclass
from datetime import datetime

from contract_evidence_os.config import RuntimeConfig
from contract_evidence_os.runtime.service import RuntimeService


def _formatter(prog: str) -> argparse.HelpFormatter:
    return argparse.HelpFormatter(prog, width=100)


def _serialize(value):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return value.__dict__
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ceos-maintenance", formatter_class=_formatter)
    parser.add_argument("--storage-root")
    parser.add_argument("--config")
    parser.add_argument("--restart-recovery", action="store_true")
    parser.add_argument("--maintenance-worker-id", default="maintenance-local")
    parser.add_argument("--host-id", default="host-local")
    parser.add_argument("--run-background-maintenance", action="store_true")
    parser.add_argument("--daemon-cycles", type=int, default=1)
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-interval-seconds", type=int, default=0)
    parser.add_argument("--heartbeat-seconds", type=int, default=30)
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--max-cycles", type=int, default=1)
    parser.add_argument("--interrupt-after")
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
    payload: dict[str, object] = {"status": "ok"}
    runtime.recover_stale_queue_leases(force_expire=True)
    runtime.reclaim_stale_workers(force_expire=True)
    if args.restart_recovery:
        payload["restart_recovery"] = runtime.restart_recovery()
    if args.run_background_maintenance or args.daemon or args.once:
        payload["maintenance_daemon"] = runtime.run_resident_maintenance_daemon(
            worker_id=args.maintenance_worker_id,
            host_id=args.host_id,
            actor="maintenance-main",
            daemon=args.daemon,
            once=args.once,
            poll_interval_seconds=args.poll_interval_seconds,
            heartbeat_seconds=args.heartbeat_seconds,
            lease_seconds=args.lease_seconds,
            max_cycles=args.max_cycles if args.max_cycles else args.daemon_cycles,
            interrupt_after=args.interrupt_after,
        )
    print(json.dumps(_serialize(payload.get("maintenance_daemon", payload)), ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
