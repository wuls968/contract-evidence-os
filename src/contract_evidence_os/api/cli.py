"""Operator CLI entrypoints."""

from __future__ import annotations

import argparse
import json
from dataclasses import is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from contract_evidence_os.api.operator import OperatorAPI
from contract_evidence_os.console.service import ConsoleService
from contract_evidence_os.config import RuntimeConfig


def _formatter(prog: str) -> argparse.HelpFormatter:
    return argparse.HelpFormatter(prog, width=100)


def _serialize(value: Any) -> Any:
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
    parser = argparse.ArgumentParser(
        prog="ceos",
        usage="%(prog)s [-h] [--storage-root STORAGE_ROOT] [--config CONFIG] COMMAND ...",
        formatter_class=_formatter,
    )
    parser.add_argument("--storage-root", required=False)
    parser.add_argument("--config")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-task")
    create.add_argument("--goal", required=True)
    create.add_argument("--attachment", action="append", default=[])
    create.add_argument("--preference", action="append", default=[])
    create.add_argument("--prohibition", action="append", default=[])

    inspect = subparsers.add_parser("inspect-task")
    inspect.add_argument("--task-id", required=True)

    resume = subparsers.add_parser("resume-task")
    resume.add_argument("--task-id", required=True)
    resume.add_argument("--interrupt-after")

    checkpoint = subparsers.add_parser("checkpoint-task")
    checkpoint.add_argument("--task-id", required=True)
    checkpoint.add_argument("--plan-node-id", required=True)
    checkpoint.add_argument("--phase", required=True)

    replay = subparsers.add_parser("replay-task")
    replay.add_argument("--task-id", required=True)

    audit = subparsers.add_parser("query-audit")
    audit.add_argument("--task-id")

    evidence = subparsers.add_parser("query-evidence")
    evidence.add_argument("--task-id", required=True)
    evidence.add_argument("--node-id", required=True)

    memory = subparsers.add_parser("query-memory")
    memory.add_argument("--memory-type")
    memory.add_argument("--state")

    handoff = subparsers.add_parser("inspect-handoff")
    handoff.add_argument("--task-id", required=True)

    questions = subparsers.add_parser("inspect-open-questions")
    questions.add_argument("--task-id", required=True)

    actions = subparsers.add_parser("inspect-next-actions")
    actions.add_argument("--task-id", required=True)

    decide = subparsers.add_parser("decide-approval")
    decide.add_argument("--request-id", required=True)
    decide.add_argument("--approver", required=True)
    decide.add_argument("--status", required=True)
    decide.add_argument("--rationale", required=True)

    propose = subparsers.add_parser("propose-evolution")
    propose.add_argument("--hypothesis", required=True)
    propose.add_argument("--source-trace", action="append", default=[])

    evaluate = subparsers.add_parser("evaluate-candidate")
    evaluate.add_argument("--candidate-id", required=True)
    evaluate.add_argument("--gain", type=float, default=0.0)
    evaluate.add_argument("--regression-failures", type=int, default=0)

    rollback = subparsers.add_parser("rollback-candidate")
    rollback.add_argument("--candidate-id", required=True)

    run_eval = subparsers.add_parser("run-eval")
    run_eval.add_argument("--task-id", required=True)

    system_report = subparsers.add_parser("system-report")

    metrics_report = subparsers.add_parser("metrics-report")
    metrics_report.add_argument("--window-hours", type=int, default=24)

    maintenance_report = subparsers.add_parser("maintenance-report")
    maintenance_report.add_argument("--task-id")

    service_health = subparsers.add_parser("service-health")
    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--env-path")

    api_contract = subparsers.add_parser("api-contract")

    kernel = subparsers.add_parser("memory-kernel-state")
    kernel.add_argument("--task-id", required=True)

    memory_pack = subparsers.add_parser("memory-evidence-pack")
    memory_pack.add_argument("--task-id", required=True)
    memory_pack.add_argument("--query", required=True)

    memory_timeline = subparsers.add_parser("memory-timeline")
    memory_timeline.add_argument("--task-id", required=True)
    memory_timeline.add_argument("--subject")
    memory_timeline.add_argument("--predicate")

    project_state = subparsers.add_parser("memory-project-state")
    project_state.add_argument("--task-id", required=True)
    project_state.add_argument("--subject", default="user")

    policy_state = subparsers.add_parser("memory-policy-state")
    policy_state.add_argument("--task-id", required=True)

    maintenance_mode = subparsers.add_parser("memory-maintenance-mode")
    maintenance_mode.add_argument("--task-id", required=True)

    maintenance_workers = subparsers.add_parser("memory-maintenance-workers")
    maintenance_workers.add_argument("--task-id", required=True)

    software_harnesses = subparsers.add_parser("software-harnesses")

    software_manifest = subparsers.add_parser("software-harness-manifest")
    software_manifest.add_argument("--harness-id", required=True)

    software_receipts = subparsers.add_parser("software-action-receipts")
    software_receipts.add_argument("--task-id")
    software_receipts.add_argument("--harness-id")
    software_receipts.add_argument("--with-replay-diagnostics", action="store_true")

    software_report = subparsers.add_parser("software-control-report")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = RuntimeConfig.load(
        config_path=None if args.config is None else Path(args.config),
        overrides={} if args.storage_root is None else {"storage_root": args.storage_root},
    )
    config_path = Path(args.config) if args.config is not None else Path(config.storage_root) / "config.local.json"
    env_path = Path(getattr(args, "env_path", "") or (Path(config.storage_root) / ".env.local"))
    api = OperatorAPI(storage_root=Path(config.storage_root), **config.runtime_kwargs())

    if args.command == "create-task":
        preferences = dict(item.split("=", 1) for item in args.preference)
        payload = api.create_task(args.goal, list(args.attachment), preferences, list(args.prohibition))
    elif args.command == "inspect-task":
        payload = api.task_dashboard(args.task_id)
    elif args.command == "resume-task":
        payload = api.resume_task(args.task_id, interrupt_after=args.interrupt_after)
    elif args.command == "checkpoint-task":
        payload = api.checkpoint_task(args.task_id, args.plan_node_id, {"phase": args.phase})
    elif args.command == "replay-task":
        payload = api.replay_task(args.task_id)
    elif args.command == "query-audit":
        payload = api.audit_query(task_id=args.task_id)
    elif args.command == "query-evidence":
        payload = api.evidence_lineage(args.task_id, args.node_id)
    elif args.command == "query-memory":
        payload = api.memory_query(memory_type=args.memory_type, state=args.state)
    elif args.command == "inspect-handoff":
        payload = api.handoff_packet(args.task_id)
    elif args.command == "inspect-open-questions":
        payload = api.open_questions(args.task_id)
    elif args.command == "inspect-next-actions":
        payload = api.next_actions(args.task_id)
    elif args.command == "decide-approval":
        payload = api.decide_approval(args.request_id, args.approver, args.status, args.rationale)
    elif args.command == "propose-evolution":
        payload = api.propose_evolution(list(args.source_trace), args.hypothesis)
    elif args.command == "evaluate-candidate":
        payload = api.evaluate_candidate(args.candidate_id, regression_failures=args.regression_failures, gain=args.gain)
    elif args.command == "rollback-candidate":
        payload = api.rollback_candidate(args.candidate_id)
    elif args.command == "run-eval":
        payload = api.trace_bundle(args.task_id)
    elif args.command == "system-report":
        payload = api.system_report()
    elif args.command == "metrics-report":
        current = api.metrics_report()
        payload = api.metrics_history(window_hours=args.window_hours)
        payload["maintenance"] = current["maintenance"]
        payload["amos"] = current["amos"]
        payload["software_control"] = current["software_control"]
    elif args.command == "maintenance-report":
        payload = api.maintenance_report(task_id=args.task_id)
    elif args.command == "service-health":
        payload = api.service_health()
    elif args.command == "doctor":
        payload = ConsoleService(api=api, config_path=config_path, env_path=env_path).doctor_report()
    elif args.command == "api-contract":
        payload = api.api_contract()
    elif args.command == "memory-kernel-state":
        payload = api.memory_kernel_state(args.task_id)
    elif args.command == "memory-evidence-pack":
        payload = api.memory_evidence_pack(args.task_id, args.query)
    elif args.command == "memory-timeline":
        payload = api.memory_timeline(args.task_id, subject=args.subject, predicate=args.predicate)
    elif args.command == "memory-project-state":
        payload = api.memory_project_state(args.task_id, subject=args.subject)
    elif args.command == "memory-policy-state":
        payload = api.memory_policy_state(args.task_id)
    elif args.command == "memory-maintenance-mode":
        payload = api.memory_maintenance_mode(args.task_id)
    elif args.command == "memory-maintenance-workers":
        payload = api.memory_maintenance_workers(args.task_id)
    elif args.command == "software-harnesses":
        payload = api.software_harnesses()
    elif args.command == "software-harness-manifest":
        payload = api.software_harness_manifest(args.harness_id)
    elif args.command == "software-action-receipts":
        payload = api.software_action_receipts(
            task_id=args.task_id,
            harness_id=args.harness_id,
            with_replay_diagnostics=args.with_replay_diagnostics,
        )
    elif args.command == "software-control-report":
        payload = api.software_control_report()
    else:  # pragma: no cover - argparse enforces subcommands
        parser.error(f"unsupported command: {args.command}")
        return 2

    print(json.dumps(_serialize(payload), ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
