"""Worker-role entrypoint for self-pulling queue execution."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from contract_evidence_os.config import RuntimeConfig
from contract_evidence_os.runtime.coordination import WorkerCapabilityRecord
from contract_evidence_os.runtime.service import RuntimeService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ceos-worker")
    parser.add_argument("--storage-root")
    parser.add_argument("--config")
    parser.add_argument("--worker-id", default=os.environ.get("CEOS_WORKER_ID", "worker-local"))
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--drain", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = RuntimeConfig.load(
        config_path=None if args.config is None else Path(args.config),
        overrides={} if args.storage_root is None else {"storage_root": args.storage_root},
    )
    runtime = RuntimeService(storage_root=Path(config.storage_root), **config.runtime_kwargs())
    runtime.register_worker(
        worker_id=args.worker_id,
        worker_role="worker",
        process_identity=args.worker_id,
        capabilities=WorkerCapabilityRecord(
            version="1.0",
            worker_id=args.worker_id,
            provider_access=list(runtime.provider_manager.providers),
            tool_access=[tool_name for tool_name, enabled in config.tool_matrix.items() if enabled],
            role_specialization=["Researcher", "Builder", "Verifier", "Strategist", "Archivist"],
            supports_degraded_mode=True,
            supports_high_risk=True,
            max_parallel_tasks=1,
        ),
        host_id=os.environ.get("CEOS_HOST_ID", "host-local"),
        service_identity="worker-service",
        endpoint_address=os.environ.get("CEOS_WORKER_ENDPOINT", f"worker://{os.environ.get('CEOS_HOST_ID', 'host-local')}/{args.worker_id}"),
    )
    if args.drain:
        runtime.coordination.set_worker_mode(args.worker_id, mode_name="drain", shutdown_state="draining")
        return 0
    for _ in range(max(args.iterations, 1)):
        result = runtime.dispatch_next_queued_task(worker_id=args.worker_id)
        if result["status"] == "idle":
            break
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
