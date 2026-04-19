"""ASGI application for the browser-first UX console and operator API."""

from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass, field, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from contract_evidence_os.api.operator import OperatorAPI
from contract_evidence_os.console.service import ConsoleService, SessionPrincipal
from contract_evidence_os.policy.models import RemoteApprovalOperation


def _serialize(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return {key: _serialize(item) for key, item in value.__dict__.items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass
class RemoteOperatorController:
    """Shared controller used by the ASGI app and the network service wrapper."""

    storage_root: Path
    token: str
    bootstrap_scopes: list[str] = field(default_factory=list)
    max_request_bytes: int = 65536
    admin_allowlist: list[str] = field(default_factory=lambda: ["127.0.0.1", "::1"])
    queue_backend_kind: str = "sqlite"
    coordination_backend_kind: str = "sqlite"
    external_backend_url: str | None = None
    external_backend_client: object | None = None
    external_backend_namespace: str = "ceos"
    shared_state_backend_kind: str = "sqlite"
    shared_state_backend_url: str | None = None
    shared_state_backend_client: object | None = None
    trust_mode: str = "standard"
    cli_anything_repo_path: str | None = None
    provider_settings: dict[str, Any] = field(default_factory=dict)
    config_path: Path | None = None
    env_path: Path | None = None

    def __post_init__(self) -> None:
        self.api = OperatorAPI(
            storage_root=self.storage_root,
            queue_backend_kind=self.queue_backend_kind,
            coordination_backend_kind=self.coordination_backend_kind,
            external_backend_url=self.external_backend_url,
            external_backend_client=self.external_backend_client,
            external_backend_namespace=self.external_backend_namespace,
            shared_state_backend_kind=self.shared_state_backend_kind,
            shared_state_backend_url=self.shared_state_backend_url,
            shared_state_backend_client=self.shared_state_backend_client,
            trust_mode=self.trust_mode,
            cli_anything_repo_path=self.cli_anything_repo_path,
            provider_settings=self.provider_settings,
        )
        self.api.auth.bootstrap_credential(
            principal_name="bootstrap-admin",
            principal_type="operator",
            scopes=self.bootstrap_scopes or ["viewer", "operator", "approver", "policy-admin", "runtime-admin", "evaluator", "worker-service"],
            token=self.token,
        )
        self.console = ConsoleService(
            api=self.api,
            config_path=self.config_path or (self.storage_root / "config.local.json"),
            env_path=self.env_path or (self.storage_root / ".env.local"),
        )

    def normalized_path(self, path_text: str) -> list[str]:
        segments = [segment for segment in path_text.strip("/").split("/") if segment]
        if segments[:1] == ["v1"]:
            segments = segments[1:]
        return segments

    # ------------------------------------------------------------------
    # Existing /v1 dispatch logic
    # ------------------------------------------------------------------
    def dispatch_get(self, path: list[str], query: dict[str, list[str]]) -> Any:
        if path == ["health", "live"]:
            return {"live": True}
        if path == ["health", "ready"]:
            return self.api.service_health()
        if path == ["service", "startup-validation"]:
            return self.api.startup_validation()
        if path == ["service", "api-contract"]:
            return self.api.api_contract()
        if path == ["reports", "system"]:
            return self.api.system_report()
        if path == ["reports", "metrics"]:
            return self.api.metrics_report()
        if path == ["reports", "metrics", "history"]:
            return self.api.metrics_history(window_hours=int(query.get("window_hours", ["24"])[0]))
        if path == ["reports", "maintenance"]:
            task_id = query.get("task_id", [None])[0]
            return self.api.maintenance_report(task_id=task_id)
        if path == ["reports", "software-control"]:
            return self.api.software_control_report()
        if path == ["metrics"]:
            return self.api.prometheus_metrics()
        if path == ["workers"]:
            return {
                "items": [item.to_dict() for item in self.api.repository.list_workers()],
                "hosts": [item.to_dict() for item in self.api.repository.list_host_records()],
                "bindings": [item.to_dict() for item in self.api.repository.list_worker_host_bindings()],
                "endpoints": [item.to_dict() for item in self.api.repository.list_worker_endpoints()],
                "pressure": None
                if self.api.repository.latest_worker_pressure_snapshot() is None
                else self.api.repository.latest_worker_pressure_snapshot().to_dict(),
            }
        if path == ["backend", "state"]:
            return {
                "descriptors": [item.to_dict() for item in self.api.repository.list_backend_descriptors()],
                "health": [item.to_dict() for item in self.api.repository.list_backend_health_records()],
                "pressure": [item.to_dict() for item in self.api.repository.list_backend_pressure_snapshots()],
                "shared_state_descriptors": [item.to_dict() for item in self.api.repository.list_shared_state_backend_descriptors()],
            }
        if path == ["reliability", "state"]:
            return {
                "incidents": [item.to_dict() for item in self.api.repository.list_reliability_incidents()],
                "reconciliation_runs": [item.to_dict() for item in self.api.repository.list_reconciliation_runs()],
                "backend_outages": [item.to_dict() for item in self.api.repository.list_backend_outage_records()],
                "degradation_records": [item.to_dict() for item in self.api.repository.list_runtime_degradation_records()],
            }
        if path == ["security", "state"]:
            return {
                "trust_mode": self.trust_mode,
                "service_trust_policies": [item.to_dict() for item in self.api.repository.list_service_trust_policies()],
                "credential_bindings": [item.to_dict() for item in self.api.repository.list_credential_binding_records()],
                "network_identities": [item.to_dict() for item in self.api.repository.list_network_identity_records()],
                "security_incidents": [item.to_dict() for item in self.api.repository.list_security_incidents()],
            }
        if path == ["software", "harnesses"]:
            return {"items": [item.to_dict() for item in self.api.list_cli_anything_harnesses()]}
        if path == ["software", "action-receipts"]:
            task_id = query.get("task_id", [None])[0]
            harness_id = query.get("harness_id", [None])[0]
            with_replay_diagnostics = query.get("with_replay_diagnostics", ["false"])[0].lower() in {"1", "true", "yes"}
            return self.api.software_action_receipts(task_id=task_id, harness_id=harness_id, with_replay_diagnostics=with_replay_diagnostics)
        if path == ["software", "bridge"]:
            return {
                "bridges": [item.to_dict() for item in self.api.list_cli_anything_bridges()],
                "build_requests": [item.to_dict() for item in self.api.repository.list_software_build_requests("cli-anything")],
            }
        if len(path) == 4 and path[0] == "software" and path[1] == "harnesses" and path[3] == "manifest":
            return self.api.software_harness_manifest(path[2])
        if len(path) == 4 and path[0] == "software" and path[1] == "harnesses" and path[3] == "report":
            return self.api.software_harness_report(path[2])
        if path == ["software", "failure-clusters"]:
            harness_id = query.get("harness_id", [None])[0]
            return self.api.software_failure_clusters(harness_id=harness_id)
        if path == ["software", "recovery-hints"]:
            harness_id = query.get("harness_id", [None])[0]
            return self.api.software_recovery_hints(harness_id=harness_id)
        if path == ["auth", "scopes"]:
            return {"items": [item.to_dict() for item in self.api.repository.list_auth_scopes()]}
        if path == ["auth", "service-principals"]:
            return {"items": [item.to_dict() for item in self.api.repository.list_service_principals()]}
        if path == ["auth", "service-credentials"]:
            return {"items": [item.to_dict() for item in self.api.repository.list_service_credentials()]}
        if path == ["memory", "cross-scope-timeline"]:
            scope_keys_raw = query.get("scope_keys", [""])[0]
            scope_keys = [item for item in scope_keys_raw.split(",") if item]
            return self.api.cross_scope_memory_timeline(
                scope_keys=scope_keys,
                subject=str(query.get("subject", [""])[0]),
                predicate=str(query.get("predicate", [""])[0]),
            )
        if path == ["memory", "cross-scope-repairs"]:
            scope_keys_raw = query.get("scope_keys", [""])[0]
            scope_keys = [item for item in scope_keys_raw.split(",") if item]
            return self.api.cross_scope_memory_repairs(
                scope_keys=scope_keys,
                subject=str(query.get("subject", [""])[0]),
                predicate=str(query.get("predicate", [""])[0]),
            )
        if path == ["tasks"]:
            status = query.get("status", [None])[0]
            return {"items": self.api.repository.list_tasks(status=status)}
        if path == ["queue", "status"]:
            return self.api.queue_status()
        if path == ["queue", "dead-letter"]:
            return {"items": [item for item in self.api.queue_status()["items"] if item["status"] == "dead_letter"]}
        if path == ["providers", "health"]:
            return self.api.provider_health_state()
        if path == ["providers", "fairness"]:
            return {"items": [item.to_dict() for item in self.api.repository.list_provider_fairness_records()]}
        if path == ["policies"]:
            return self.api.policy_registry_state()
        if path == ["system", "governance"]:
            return self.api.system_governance_state()
        if len(path) == 3 and path[0] == "tasks" and path[2] == "status":
            return self.api.task_status(path[1])
        if len(path) == 3 and path[0] == "tasks" and path[2] == "handoff":
            return self.api.handoff_packet(path[1])
        if len(path) == 3 and path[0] == "tasks" and path[2] == "checkpoints":
            return {"items": self.api.checkpoints(path[1])}
        if len(path) == 3 and path[0] == "tasks" and path[2] == "open-questions":
            return {"items": self.api.open_questions(path[1])}
        if len(path) == 3 and path[0] == "tasks" and path[2] == "next-actions":
            return {"items": self.api.next_actions(path[1])}
        if len(path) == 3 and path[0] == "tasks" and path[2] == "incident":
            return self.api.incident_packet(path[1])
        if len(path) == 3 and path[0] == "tasks" and path[2] == "governance":
            return self.api.governance_state(path[1])
        if len(path) == 3 and path[0] == "tasks" and path[2] == "memory":
            return self.api.memory_state(path[1])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "kernel":
            return self.api.memory_kernel_state(path[1])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "timeline":
            subject = query.get("subject", [None])[0]
            predicate = query.get("predicate", [None])[0]
            return self.api.memory_timeline(path[1], subject=subject, predicate=predicate)
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "project-state":
            subject = str(query.get("subject", ["user"])[0] or "user")
            return self.api.memory_project_state(path[1], subject=subject)
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "artifacts":
            artifact_kind = query.get("artifact_kind", [None])[0]
            return self.api.memory_artifacts(path[1], artifact_kind=artifact_kind)
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "artifact-health":
            return self.api.memory_artifact_health(path[1])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-drift":
            return self.api.memory_maintenance_drift(path[1])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-incidents":
            return self.api.memory_maintenance_incidents(path[1])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-mode":
            return self.api.memory_maintenance_mode(path[1])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-workers":
            return self.api.memory_maintenance_workers(path[1])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-daemon":
            return self.api.maintenance_daemon_state(path[1])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "ops-diagnostics":
            return self.api.memory_operations_diagnostics(path[1])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "admission-promotions":
            return self.api.memory_admission_promotions(path[1])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-recommendations":
            return {"items": [self.api.memory_maintenance_recommendation(path[1])["recommendation"]]}
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-promotions":
            return self.api.memory_maintenance_promotions(path[1])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-rollouts":
            return self.api.memory_maintenance_rollouts(path[1])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "policy":
            return self.api.memory_policy_state(path[1])
        if path == ["approvals"]:
            task_id = query.get("task_id", [None])[0]
            status = query.get("status", ["pending"])[0]
            return {"items": self.api.approval_inbox(task_id=task_id, status=status)}
        raise KeyError("/".join(path))

    def dispatch_post(self, path: list[str], body: dict[str, Any]) -> Any:
        if path == ["queue", "dispatch"]:
            return self.api.dispatch_next_queued_task(
                worker_id=str(body.get("worker_id", "remote-worker")),
                interrupt_after=body.get("interrupt_after"),
            )
        if path == ["service", "shutdown"]:
            return self.api.graceful_shutdown(reason=str(body.get("reason", "remote shutdown requested")))
        if path == ["service", "restart-recovery"]:
            return self.api.restart_recovery()
        if path == ["reliability", "outage"]:
            return self.api.record_backend_outage(
                backend_name=str(body.get("backend_name", "unknown")),
                fault_domain=str(body.get("fault_domain", "shared_state")),
                summary=str(body.get("summary", "reported backend outage")),
            )
        if path == ["reliability", "reconcile"]:
            return self.api.run_reconciliation(reason=str(body.get("reason", "operator requested reconciliation")))
        if path == ["auth", "credentials"]:
            credential, token = self.api.auth.issue_credential(
                principal_name=str(body.get("principal_name", "operator")),
                principal_type=str(body.get("principal_type", "operator")),
                scopes=[str(item) for item in body.get("scopes", ["viewer"])],
                description=str(body.get("description", "")),
            )
            return {"credential": credential.to_dict(), "token": token}
        if path == ["auth", "service-credentials"]:
            credential, token = self.api.auth.issue_service_credential(
                service_name=str(body.get("service_name", "runtime-service")),
                service_role=str(body.get("service_role", "worker")),
                scopes=[str(item) for item in body.get("scopes", ["worker-service"])],
                allowed_hosts=[str(item) for item in body.get("allowed_hosts", [])],
                description=str(body.get("description", "")),
            )
            return {"credential": credential.to_dict(), "token": token}
        if path == ["software", "harnesses", "discover"]:
            return {
                "items": [
                    item.to_dict()
                    for item in self.api.discover_cli_anything_harnesses(
                        search_roots=[str(item) for item in body.get("search_roots", [])]
                    )
                ]
            }
        if path == ["software", "harnesses", "register"]:
            return self.api.register_cli_anything_harness(
                executable_path=str(body.get("executable_path", "")),
                policy_overrides=None if "policy_overrides" not in body else dict(body.get("policy_overrides", {})),
            )
        if path == ["software", "bridge", "configure"]:
            return {
                "bridge": self.api.configure_cli_anything_bridge(
                    repo_path=str(body.get("repo_path", "")),
                    enabled=bool(body.get("enabled", True)),
                ).to_dict()
            }
        if path == ["software", "bridge", "install-codex-skill"]:
            return self.api.install_cli_anything_codex_skill()
        if path == ["software", "build-requests"]:
            return {
                "build_request": self.api.submit_cli_anything_build_request(
                    target=str(body.get("target", "")),
                    mode=str(body.get("mode", "build")),
                    focus=str(body.get("focus", "")),
                ).to_dict()
            }
        if len(path) == 4 and path[0] == "software" and path[1] == "harnesses" and path[3] == "validate":
            return {"validation": self.api.validate_cli_anything_harness(path[2]).to_dict()}
        if len(path) == 4 and path[0] == "software" and path[1] == "harnesses" and path[3] == "invoke":
            return self.api.invoke_cli_anything_harness(
                harness_id=path[2],
                command_path=[str(item) for item in body.get("command_path", [])],
                arguments=[str(item) for item in body.get("arguments", [])],
                actor=str(body.get("actor", "remote-operator")),
                task_id=None if body.get("task_id") in {None, ""} else str(body.get("task_id")),
                approved=bool(body.get("approved", False)),
                dry_run=bool(body.get("dry_run", False)),
            )
        if len(path) == 6 and path[0] == "software" and path[1] == "harnesses" and path[3] == "macros" and path[5] == "invoke":
            return self.api.invoke_software_automation_macro(
                macro_id=path[4],
                actor=str(body.get("actor", "remote-operator")),
                task_id=None if body.get("task_id") in {None, ""} else str(body.get("task_id")),
                approved=bool(body.get("approved", False)),
                dry_run=bool(body.get("dry_run", False)),
            )
        if path == ["auth", "rotate"]:
            credential, token = self.api.auth.rotate_credential(
                str(body.get("credential_id", "")),
                reason=str(body.get("reason", "rotation")),
            )
            return {"credential": None if credential is None else credential.to_dict(), "token": token}
        if path == ["auth", "revoke"]:
            return self.api.auth.revoke_credential(
                str(body.get("credential_id", "")),
                reason=str(body.get("reason", "revoked by operator")),
            ).to_dict()
        if path == ["system", "governance"]:
            return self.api.control_system_governance(
                action=str(body.get("action", "")),
                operator=str(body.get("operator", "remote-operator")),
                reason=str(body.get("reason", "")),
                payload={str(key): str(value) for key, value in dict(body.get("payload", {})).items()},
            )
        if path == ["providers", "control"]:
            return self.api.control_system_governance(
                action=str(body.get("action", "")),
                operator=str(body.get("operator", "remote-operator")),
                reason=str(body.get("reason", "")),
                payload={str(key): str(value) for key, value in dict(body.get("payload", {})).items()},
            )
        if path == ["policies", "candidates"]:
            return self.api.propose_policy_candidate_from_runtime(
                name=str(body.get("name", "runtime-policy-candidate")),
                hypothesis=str(body.get("hypothesis", "adjust runtime policy from scorecard traces")),
                policy_payload=dict(body.get("policy_payload", {})),
                scope_id=str(body.get("scope_id", "policy-scope-routing")),
            )
        if path == ["policies", "evaluate"]:
            return self.api.evaluate_policy_candidate_remote(
                str(body.get("candidate_id", "")),
                metrics={str(key): float(value) for key, value in dict(body.get("metrics", {})).items()},
            )
        if path == ["policies", "promote"]:
            return self.api.promote_policy_candidate_remote(str(body.get("candidate_id", "")))
        if path == ["policies", "rollback"]:
            return self.api.rollback_policy_scope_remote(
                str(body.get("scope_id", "")),
                reason=str(body.get("reason", "remote rollback requested")),
            )
        if len(path) == 3 and path[0] == "tasks" and path[2] == "resume":
            return self.api.resume_task(path[1], interrupt_after=body.get("interrupt_after"))
        if len(path) == 3 and path[0] == "tasks" and path[2] == "replay":
            return self.api.replay_task(path[1])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "evidence-pack":
            return self.api.memory_evidence_pack(path[1], query=str(body.get("query", "")))
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "consolidate":
            return self.api.consolidate_memory(path[1], reason=str(body.get("reason", "remote memory consolidation requested")))
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "rebuild":
            return self.api.rebuild_memory(path[1], reason=str(body.get("reason", "remote memory rebuild requested")))
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "selective-rebuild":
            return self.api.selective_rebuild_memory(
                path[1],
                reason=str(body.get("reason", "remote selective rebuild requested")),
                target_kinds=[str(item) for item in body.get("target_kinds", [])],
            )
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "operations-loop":
            return self.api.memory_operations_loop(
                path[1],
                reason=str(body.get("reason", "remote memory operations loop requested")),
                interrupt_after=None if body.get("interrupt_after") in {None, ""} else str(body.get("interrupt_after")),
            )
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "ops-schedule":
            return self.api.schedule_memory_operations_loop(path[1], cadence_hours=int(body.get("cadence_hours", 24)), actor=str(body.get("actor", "remote-operator")))
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "background-maintenance":
            return self.api.background_memory_maintenance(path[1], actor=str(body.get("actor", "remote-operator")))
        if len(path) == 5 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-workers" and path[4] == "register":
            return self.api.register_maintenance_worker(path[1], worker_id=str(body.get("worker_id", "maintenance-worker")), host_id=str(body.get("host_id", "host-local")), actor=str(body.get("actor", "remote-operator")))
        if len(path) == 5 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-workers" and path[4] == "daemon":
            return self.api.run_resident_maintenance_daemon(
                path[1],
                worker_id=str(body.get("worker_id", "maintenance-worker")),
                host_id=str(body.get("host_id", "host-local")),
                actor=str(body.get("actor", "remote-operator")),
                daemon=bool(body.get("daemon", False)),
                once=bool(body.get("once", False)),
                poll_interval_seconds=int(body.get("poll_interval_seconds", 0)),
                heartbeat_seconds=int(body.get("heartbeat_seconds", 30)),
                lease_seconds=int(body.get("lease_seconds", 300)),
                max_cycles=int(body.get("max_cycles", body.get("cycles", 1))),
                interrupt_after=body.get("interrupt_after"),
            )
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-canary":
            return self.api.memory_maintenance_canary(path[1])
        if len(path) == 6 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-incidents" and path[5] == "resolve":
            return self.api.resolve_maintenance_incident(path[1], incident_id=path[4], actor=str(body.get("actor", "remote-operator")), resolution=str(body.get("resolution", "resolved by operator")))
        if len(path) == 6 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-promotions" and path[5] == "apply":
            return self.api.apply_maintenance_promotion(path[1], recommendation_id=path[4], actor=str(body.get("actor", "remote-operator")), reason=str(body.get("reason", "apply maintenance promotion")))
        if len(path) == 6 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-rollouts" and path[5] == "rollback":
            return self.api.rollback_maintenance_rollout(path[1], rollout_id=path[4], actor=str(body.get("actor", "remote-operator")), reason=str(body.get("reason", "rollback maintenance rollout")))
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "delete":
            return self.api.delete_memory_scope(path[1], actor=str(body.get("actor", "remote-operator")), reason=str(body.get("reason", "remote memory deletion requested")))
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "selective-purge":
            return self.api.selective_purge_memory_scope(path[1], actor=str(body.get("actor", "remote-operator")), reason=str(body.get("reason", "remote selective purge requested")), target_kinds=[str(item) for item in body.get("target_kinds", [])])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "hard-purge":
            target_kinds = body.get("target_kinds")
            return self.api.hard_purge_memory_scope(path[1], actor=str(body.get("actor", "remote-operator")), reason=str(body.get("reason", "remote memory hard purge requested")), target_kinds=None if target_kinds is None else [str(item) for item in target_kinds])
        if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "admission-canary":
            return self.api.memory_admission_canary(path[1], candidate_ids=[str(item) for item in body.get("candidate_ids", [])])
        if path == ["memory", "cross-scope-repairs", "canary"]:
            return self.api.cross_scope_memory_repair_canary(scope_keys=[str(item) for item in body.get("scope_keys", [])], subject=str(body.get("subject", "")), predicate=str(body.get("predicate", "")))
        if len(path) == 4 and path[0] == "memory" and path[1] == "cross-scope-repairs" and path[3] in {"apply", "rollback"}:
            if path[3] == "apply":
                return self.api.apply_cross_scope_memory_repair(path[2], actor=str(body.get("actor", "remote-operator")), reason=str(body.get("reason", "remote repair apply requested")))
            return self.api.rollback_cross_scope_memory_repair(path[2], actor=str(body.get("actor", "remote-operator")), reason=str(body.get("reason", "remote repair rollback requested")))
        if len(path) == 6 and path[0] == "tasks" and path[2] == "memory" and path[3] == "operations-loop" and path[5] == "resume":
            return self.api.resume_memory_operations_loop(path[4], actor=str(body.get("actor", "remote-operator")), reason=str(body.get("reason", "remote memory operations loop resume requested")))
        if path == ["memory", "background-maintenance", "run-due"]:
            return self.api.run_due_background_maintenance(at_time=None if body.get("at_time") in {None, ""} else str(body.get("at_time")), interrupt_after=None if body.get("interrupt_after") in {None, ""} else str(body.get("interrupt_after")))
        if len(path) == 4 and path[0] == "memory" and path[1] == "maintenance-workers" and path[3] == "cycle":
            return self.api.run_maintenance_worker_cycle(worker_id=path[2], at_time=None if body.get("at_time") in {None, ""} else str(body.get("at_time")), interrupt_after=None if body.get("interrupt_after") in {None, ""} else str(body.get("interrupt_after")))
        if len(path) == 4 and path[0] == "memory" and path[1] == "background-maintenance" and path[3] == "resume":
            return self.api.resume_background_maintenance(path[2], actor=str(body.get("actor", "remote-operator")), reason=str(body.get("reason", "remote background maintenance resume requested")))
        if len(path) == 3 and path[0] == "tasks" and path[2] == "eval":
            return self.api.trace_bundle(path[1])
        if len(path) == 3 and path[0] == "tasks" and path[2] == "candidate-eval":
            return self.api.trace_bundle(path[1])
        if len(path) == 3 and path[0] == "tasks" and path[2] == "governance":
            return self.api.control_governance(task_id=path[1], action=str(body.get("action", "")), operator=str(body.get("operator", "remote-operator")), reason=str(body.get("reason", "")), payload={str(key): str(value) for key, value in dict(body.get("payload", {})).items()})
        if len(path) == 3 and path[0] == "approvals" and path[2] == "decision":
            request_id = path[1]
            decision = self.api.decide_approval(
                request_id=request_id,
                approver=str(body.get("approver", "remote-operator")),
                status=str(body.get("status", "approved")),
                rationale=str(body.get("rationale", "")),
                approved_scope=body.get("approved_scope"),
                intervention_action=body.get("intervention_action"),
            )
            request = next(item for item in self.api.repository.list_approval_requests() if item.request_id == request_id)
            operation = RemoteApprovalOperation(
                version="1.0",
                operation_id=f"remote-approval-op-{uuid4().hex[:10]}",
                request_id=request_id,
                task_id=request.task_id,
                contract_id=request.contract_id,
                plan_node_id=request.plan_node_id,
                operator=str(body.get("approver", "remote-operator")),
                action="approval_decision",
                status=decision.status,
                rationale=str(body.get("rationale", "")),
                decision_id=decision.decision_id,
            )
            self.api.repository.save_remote_approval_operation(operation)
            return decision
        raise KeyError("/".join(path))

    def auth_requirements(self, path: list[str], method: str) -> tuple[str, list[str], bool]:
        if method == "GET":
            return ("/".join(path) or "root", ["viewer"], False)
        if path == ["queue", "dispatch"]:
            return ("queue_dispatch", ["worker-service", "runtime-admin"], True)
        if path in (["service", "shutdown"], ["service", "restart-recovery"], ["system", "governance"], ["providers", "control"], ["reliability", "outage"], ["reliability", "reconcile"]):
            return ("/".join(path), ["runtime-admin"], True)
        if path in (["policies", "candidates"], ["policies", "promote"], ["policies", "rollback"]):
            return ("/".join(path), ["policy-admin"], True)
        if path == ["policies", "evaluate"]:
            return ("policy_evaluate", ["evaluator", "policy-admin"], True)
        if path in (["auth", "credentials"], ["auth", "revoke"], ["auth", "service-credentials"], ["auth", "rotate"]):
            return ("/".join(path), ["runtime-admin"], True)
        if len(path) == 3 and path[0] == "approvals" and path[2] == "decision":
            return ("approval_decision", ["approver"], True)
        return ("/".join(path), ["operator", "runtime-admin"], True)

    def authorize_request(self, *, headers: dict[str, str], path: list[str], method: str, body: bytes = b"", remote_host: str = "") -> None:
        action, required_scopes, sensitive = self.auth_requirements(path, method)
        if sensitive and self.admin_allowlist and remote_host not in self.admin_allowlist:
            raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": "remote_host_not_allowed"})
        service_credential_id = headers.get("x-service-credential", "")
        if self.trust_mode == "hmac" and sensitive and service_credential_id:
            trust_decision = self.api.trust.verify_request(
                credential_id=service_credential_id,
                method=method,
                path="/" + "/".join(path),
                headers=headers,
                body=body,
                source_address=remote_host,
            )
            if not trust_decision.accepted:
                raise HTTPException(status_code=409 if trust_decision.reason == "replayed_request" else 401, detail={"error": trust_decision.reason})
        authorization = headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail={"error": "unauthorized"})
        request_id = headers.get("x-request-id", f"auto-{uuid4().hex[:10]}")
        nonce = headers.get("x-request-nonce", request_id if sensitive else "")
        idempotency_key = headers.get("x-idempotency-key", request_id)
        session = self.api.auth.authenticate(authorization.removeprefix("Bearer ").strip(), request_id=request_id)
        if session is None:
            raise HTTPException(status_code=401, detail={"error": "unauthorized"})
        decision = self.api.auth.authorize(session, required_scopes=required_scopes, action=action)
        if not decision.allowed:
            raise HTTPException(status_code=403, detail={"error": "forbidden", "reason": decision.reason})
        guard = self.api.auth.record_request(
            session=session,
            request_id=request_id,
            nonce=nonce,
            idempotency_key=idempotency_key,
            action=action,
            sensitive=sensitive,
        )
        if not guard.accepted:
            raise HTTPException(status_code=409, detail={"error": guard.reason})


def _mask_token(token: str) -> str:
    if len(token) <= 8:
        return "*" * len(token)
    return token[:4] + "..." + token[-4:]


def create_console_app(
    *,
    storage_root: Path,
    token: str,
    host: str = "127.0.0.1",
    port: int = 8080,
    bootstrap_scopes: list[str] | None = None,
    max_request_bytes: int = 65536,
    admin_allowlist: list[str] | None = None,
    queue_backend_kind: str = "sqlite",
    coordination_backend_kind: str = "sqlite",
    external_backend_url: str | None = None,
    external_backend_client: object | None = None,
    external_backend_namespace: str = "ceos",
    shared_state_backend_kind: str = "sqlite",
    shared_state_backend_url: str | None = None,
    shared_state_backend_client: object | None = None,
    trust_mode: str = "standard",
    cli_anything_repo_path: str | None = None,
    provider_settings: dict[str, Any] | None = None,
    config_path: Path | None = None,
    env_path: Path | None = None,
    frontend_dist: Path | None = None,
) -> FastAPI:
    controller = RemoteOperatorController(
        storage_root=storage_root,
        token=token,
        bootstrap_scopes=[] if bootstrap_scopes is None else bootstrap_scopes,
        max_request_bytes=max_request_bytes,
        admin_allowlist=["127.0.0.1", "::1"] if admin_allowlist is None else admin_allowlist,
        queue_backend_kind=queue_backend_kind,
        coordination_backend_kind=coordination_backend_kind,
        external_backend_url=external_backend_url,
        external_backend_client=external_backend_client,
        external_backend_namespace=external_backend_namespace,
        shared_state_backend_kind=shared_state_backend_kind,
        shared_state_backend_url=shared_state_backend_url,
        shared_state_backend_client=shared_state_backend_client,
        trust_mode=trust_mode,
        cli_anything_repo_path=cli_anything_repo_path,
        provider_settings={} if provider_settings is None else provider_settings,
        config_path=config_path,
        env_path=env_path,
    )

    app = FastAPI(title="Contract-Evidence OS UX Console", version="0.9.0")
    app.state.controller = controller
    app.state.console = controller.console
    app.state.host = host
    app.state.port = port
    dist_path = frontend_dist or (_repo_root() / "frontend" / "dist")
    assets_path = dist_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    def current_session(request: Request, *, required_scopes: list[str] | None = None) -> SessionPrincipal:
        session_id = request.cookies.get("ceos_session", "")
        principal = controller.console.resolve_session(session_id) if session_id else None
        if principal is None:
            raise HTTPException(status_code=401, detail={"error": "unauthorized"})
        if required_scopes:
            missing = [scope for scope in required_scopes if scope not in principal.scopes]
            if missing:
                raise HTTPException(status_code=403, detail={"error": "forbidden", "missing_scopes": missing})
        return principal

    def proxy_error_response(exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {"error": str(exc.detail)}
        return JSONResponse(_serialize(detail), status_code=exc.status_code)

    def spa_shell() -> HTMLResponse:
        if dist_path.exists() and (dist_path / "index.html").exists():
            return HTMLResponse((dist_path / "index.html").read_text(encoding="utf-8"))
        return HTMLResponse(
            """
            <!doctype html>
            <html>
              <head><meta charset="utf-8"><title>Contract-Evidence OS Console</title></head>
              <body style="font-family: Helvetica, Arial, sans-serif; background:#0d1117; color:#f0f6fc; padding:40px;">
                <h1>Contract-Evidence OS UX Console</h1>
                <p>The frontend bundle is not built yet.</p>
                <p>Run <code>cd frontend && npm install && npm run build</code> to generate the production dashboard.</p>
              </body>
            </html>
            """.strip()
        )

    @app.get("/", include_in_schema=False)
    def root(request: Request) -> Response:
        bootstrap = controller.console.bootstrap_state()
        if bootstrap["setup_required"]:
            return RedirectResponse("/setup", status_code=307)
        session_id = request.cookies.get("ceos_session", "")
        principal = controller.console.resolve_session(session_id) if session_id else None
        if principal is None:
            return RedirectResponse("/login", status_code=307)
        return RedirectResponse("/dashboard", status_code=307)

    for path in ("/setup", "/login", "/dashboard", "/memory", "/software", "/maintenance", "/usage", "/settings", "/doctor", "/audit", "/benchmarks", "/playbooks", "/collaboration", "/mcp"):
        app.add_api_route(path, lambda: spa_shell(), methods=["GET"], include_in_schema=False)

    @app.get("/tasks/{task_id}", include_in_schema=False)
    def spa_task(task_id: str) -> HTMLResponse:  # noqa: ARG001
        return spa_shell()

    @app.get("/memory/cross-scope-timeline")
    def legacy_cross_scope_timeline(request: Request, scope_keys: str, subject: str, predicate: str) -> JSONResponse:
        headers = {key.lower(): value for key, value in request.headers.items()}
        remote_host = request.client.host if request.client else ""
        path = ["memory", "cross-scope-timeline"]
        try:
            controller.authorize_request(path=path, method="GET", headers=headers, remote_host=remote_host)
            payload = controller.dispatch_get(
                path,
                {"scope_keys": [scope_keys], "subject": [subject], "predicate": [predicate]},
            )
        except HTTPException as exc:
            return proxy_error_response(exc)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
        return JSONResponse(_serialize(payload))

    @app.get("/memory/cross-scope-repairs")
    def legacy_cross_scope_repairs(request: Request, scope_keys: str, subject: str, predicate: str) -> JSONResponse:
        headers = {key.lower(): value for key, value in request.headers.items()}
        remote_host = request.client.host if request.client else ""
        path = ["memory", "cross-scope-repairs"]
        try:
            controller.authorize_request(path=path, method="GET", headers=headers, remote_host=remote_host)
            payload = controller.dispatch_get(
                path,
                {"scope_keys": [scope_keys], "subject": [subject], "predicate": [predicate]},
            )
        except HTTPException as exc:
            return proxy_error_response(exc)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
        return JSONResponse(_serialize(payload))

    @app.get("/memory/{task_id}", include_in_schema=False)
    def spa_memory(task_id: str) -> HTMLResponse:  # noqa: ARG001
        return spa_shell()

    @app.get("/ui/bootstrap-state")
    def ui_bootstrap_state() -> dict[str, Any]:
        return controller.console.bootstrap_state()

    @app.post("/auth/bootstrap-admin")
    async def auth_bootstrap_admin(request: Request) -> JSONResponse:
        payload = await request.json()
        created = controller.console.bootstrap_admin(dict(payload))
        return JSONResponse(_serialize(created))

    @app.post("/auth/login")
    async def auth_login(request: Request) -> JSONResponse:
        payload = await request.json()
        principal = controller.console.authenticate_local(email=str(payload.get("email", "")), password=str(payload.get("password", "")))
        response = JSONResponse(
            {
                "account": principal.user.to_dict(),
                "roles": principal.roles,
                "scopes": principal.scopes,
                "session": {"session_id": principal.session.session_id, "expires_at": None if principal.session.expires_at is None else principal.session.expires_at.isoformat()},
            }
        )
        response.set_cookie("ceos_session", principal.session.session_id, httponly=True, samesite="lax", max_age=7 * 24 * 60 * 60)
        return response

    @app.post("/auth/logout")
    def auth_logout(request: Request) -> JSONResponse:
        session_id = request.cookies.get("ceos_session", "")
        if session_id:
            controller.console.logout_session(session_id)
        response = JSONResponse({"status": "logged_out"})
        response.delete_cookie("ceos_session")
        return response

    @app.get("/auth/session")
    def auth_session(request: Request) -> dict[str, Any]:
        principal = current_session(request)
        return {
            "account": principal.user.to_dict(),
            "roles": principal.roles,
            "scopes": principal.scopes,
            "session": principal.session.to_dict(),
        }

    @app.get("/auth/users")
    def auth_users(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        return {"items": [_serialize(item) for item in controller.console.list_user_accounts()]}

    @app.post("/auth/users")
    async def auth_users_create(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.create_user_account(
            email=str(payload.get("email", "")),
            password=str(payload.get("password", "")),
            display_name=str(payload.get("display_name", "")),
            role_name=str(payload.get("role_name", "viewer")),
        )

    @app.get("/auth/roles")
    def auth_roles(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        return {"items": [_serialize(item) for item in controller.console.list_user_role_bindings()]}

    @app.get("/auth/sessions")
    def auth_sessions(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        return {"items": [_serialize(item) for item in controller.console.list_browser_sessions()]}

    @app.get("/auth/invitations")
    def auth_invitations(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        return {"items": [_serialize(item) for item in controller.console.list_workspace_invitations()]}

    @app.post("/auth/invitations")
    async def auth_invitations_create(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.create_workspace_invitation(
            email=str(payload.get("email", "")),
            role_name=str(payload.get("role_name", "viewer")),
            invited_by=str(payload.get("invited_by", "runtime-admin")),
        )

    @app.get("/auth/oidc/presets")
    def auth_oidc_presets() -> dict[str, Any]:
        return {"items": controller.console.oidc_presets()}

    @app.get("/auth/oidc/providers")
    def auth_oidc_providers(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        return {"items": [_serialize(item) for item in controller.console.list_oidc_provider_configs()]}

    @app.post("/auth/oidc/providers")
    async def auth_oidc_save_provider(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.save_oidc_provider_config(dict(payload))

    @app.get("/auth/oidc/start/{provider_id}")
    def auth_oidc_start(provider_id: str, request: Request, next_path: str = "/dashboard") -> RedirectResponse:
        host_value = request.headers.get("host", f"{host}:{port}")
        redirect_uri = f"{request.url.scheme}://{host_value}/auth/oidc/callback"
        url = controller.console.start_oidc_login(provider_id, redirect_uri=redirect_uri, next_path=next_path)
        return RedirectResponse(url, status_code=307)

    @app.get("/auth/oidc/callback")
    def auth_oidc_callback(state: str, code: str) -> RedirectResponse:
        principal = controller.console.finish_oidc_login(state_id=state, code=code)
        response = RedirectResponse("/dashboard", status_code=307)
        response.set_cookie("ceos_session", principal.session.session_id, httponly=True, samesite="lax", max_age=7 * 24 * 60 * 60)
        return response

    @app.get("/ui/dashboard-summary")
    def ui_dashboard_summary(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.dashboard_summary()

    @app.get("/ui/tasks/recent")
    def ui_tasks_recent(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return {"items": controller.console.dashboard_summary()["recent_tasks"]}

    @app.get("/ui/tasks/{task_id}")
    def ui_task_cockpit(task_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.task_cockpit(task_id)

    @app.get("/ui/tasks/{task_id}/timeline")
    def ui_task_timeline(task_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.task_cockpit(task_id)["timeline"]

    @app.get("/ui/tasks/{task_id}/evidence-trace")
    def ui_task_evidence_trace(task_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.task_cockpit(task_id)["evidence_trace"]

    @app.get("/ui/memory/overview")
    def ui_memory_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.memory_overview()

    @app.get("/ui/memory/{task_id}")
    def ui_memory_task(task_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.api.memory_kernel_state(task_id)

    @app.get("/ui/software/overview")
    def ui_software_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.software_overview()

    @app.get("/ui/maintenance/overview")
    def ui_maintenance_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.maintenance_overview()

    @app.get("/ui/approvals")
    def ui_approvals(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.approvals_inbox()

    @app.post("/ui/approvals/{request_id}/decision")
    async def ui_approval_decision(request_id: str, request: Request) -> dict[str, Any]:
        principal = current_session(request, required_scopes=["approver"])
        payload = await request.json()
        return controller.console.decide_approval(
            request_id=request_id,
            approver=principal.user.email,
            status=str(payload.get("status", "approved")),
            rationale=str(payload.get("rationale", "")),
        )

    @app.get("/ui/doctor")
    def ui_doctor(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.doctor_report()

    @app.get("/ui/audit/overview")
    def ui_audit_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.audit_overview()

    @app.get("/ui/playbooks/overview")
    def ui_playbooks_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.playbooks_overview()

    @app.get("/ui/benchmarks/overview")
    def ui_benchmarks_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.benchmarks_overview()

    @app.get("/ui/collaboration/overview")
    def ui_collaboration_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.collaboration_summary().to_dict()

    @app.get("/ui/mcp/overview")
    def ui_mcp_overview(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.mcp_overview()

    @app.post("/ui/mcp/servers")
    async def ui_mcp_register_server(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.register_mcp_server(dict(payload))

    @app.post("/ui/mcp/servers/{server_id}/tools")
    async def ui_mcp_register_tool(server_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.register_mcp_tool(server_id, dict(payload))

    @app.post("/ui/mcp/servers/{server_id}/invoke")
    async def ui_mcp_invoke(server_id: str, request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["operator"])
        payload = await request.json()
        return controller.console.invoke_mcp_tool(server_id, dict(payload))

    @app.get("/config/effective")
    def config_effective(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        return controller.console.config_effective()

    @app.post("/config/update")
    async def config_update(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.update_config(dict(payload))

    @app.post("/config/test-provider")
    async def config_test_provider(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.test_provider_connection(dict(payload))

    @app.post("/config/test-oidc")
    async def config_test_oidc(request: Request) -> dict[str, Any]:
        current_session(request, required_scopes=["runtime-admin"])
        payload = await request.json()
        return controller.console.test_oidc_provider_config(dict(payload))

    @app.get("/usage/summary")
    def usage_summary(request: Request, window: str = "24h") -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.usage_summary(window=window)

    @app.get("/usage/tasks/{task_id}")
    def usage_task(request: Request, task_id: str, window: str = "24h") -> dict[str, Any]:
        current_session(request, required_scopes=["viewer"])
        return controller.console.task_usage_summary(task_id, window=window)

    @app.get("/events/stream")
    def events_stream(request: Request) -> StreamingResponse:
        current_session(request, required_scopes=["viewer"])

        def iterator() -> Any:
            for event_name, payload in controller.console.event_stream_payloads():
                yield f"event: {event_name}\n".encode("utf-8")
                yield f"data: {json.dumps(_serialize(payload), ensure_ascii=True)}\n\n".encode("utf-8")
            yield b"event: heartbeat\n"
            yield f"data: {json.dumps({'timestamp': datetime.now().isoformat()})}\n\n".encode("utf-8")

        return StreamingResponse(iterator(), media_type="text/event-stream")

    @app.get("/metrics")
    def metrics(request: Request) -> PlainTextResponse:
        headers = {key.lower(): value for key, value in request.headers.items()}
        controller.authorize_request(path=["metrics"], method="GET", headers=headers, remote_host=request.client.host if request.client else "")
        return PlainTextResponse(controller.api.prometheus_metrics(), media_type="text/plain; version=0.0.4")

    @app.api_route("/v1/{full_path:path}", methods=["GET", "POST"])
    async def v1_proxy(full_path: str, request: Request) -> Response:
        path = controller.normalized_path("/v1/" + full_path)
        headers = {key.lower(): value for key, value in request.headers.items()}
        remote_host = request.client.host if request.client else ""
        try:
            if request.method == "GET":
                controller.authorize_request(path=path, method="GET", headers=headers, remote_host=remote_host)
                payload = controller.dispatch_get(path, parse_qs(request.url.query))
                if path == ["metrics"]:
                    return PlainTextResponse(str(payload), media_type="text/plain; version=0.0.4")
                return JSONResponse(_serialize(payload))
            body = await request.body()
            if len(body) > controller.max_request_bytes:
                raise HTTPException(status_code=413, detail={"error": "request_too_large"})
            controller.authorize_request(path=path, method="POST", headers=headers, body=body, remote_host=remote_host)
            payload = controller.dispatch_post(path, {} if not body else json.loads(body.decode("utf-8")))
        except HTTPException as exc:
            return proxy_error_response(exc)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
        return JSONResponse(_serialize(payload))

    @app.api_route("/{full_path:path}", methods=["GET", "POST"])
    async def legacy_proxy(full_path: str, request: Request) -> Response:
        path = controller.normalized_path("/" + full_path)
        headers = {key.lower(): value for key, value in request.headers.items()}
        remote_host = request.client.host if request.client else ""
        try:
            if request.method == "GET":
                controller.authorize_request(path=path, method="GET", headers=headers, remote_host=remote_host)
                payload = controller.dispatch_get(path, parse_qs(request.url.query))
                if path == ["metrics"]:
                    return PlainTextResponse(str(payload), media_type="text/plain; version=0.0.4")
                return JSONResponse(_serialize(payload))
            body = await request.body()
            if len(body) > controller.max_request_bytes:
                raise HTTPException(status_code=413, detail={"error": "request_too_large"})
            controller.authorize_request(path=path, method="POST", headers=headers, body=body, remote_host=remote_host)
            payload = controller.dispatch_post(path, {} if not body else json.loads(body.decode("utf-8")))
        except HTTPException as exc:
            return proxy_error_response(exc)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={"error": str(exc)}) from exc
        return JSONResponse(_serialize(payload))

    return app


class RemoteOperatorService:
    """ASGI-backed network service preserving the historical RemoteOperatorService interface."""

    def __init__(
        self,
        *,
        storage_root: Path,
        token: str,
        host: str = "127.0.0.1",
        port: int = 8080,
        bootstrap_scopes: list[str] | None = None,
        max_request_bytes: int = 65536,
        admin_allowlist: list[str] | None = None,
        queue_backend_kind: str = "sqlite",
        coordination_backend_kind: str = "sqlite",
        external_backend_url: str | None = None,
        external_backend_client: object | None = None,
        external_backend_namespace: str = "ceos",
        shared_state_backend_kind: str = "sqlite",
        shared_state_backend_url: str | None = None,
        shared_state_backend_client: object | None = None,
        trust_mode: str = "standard",
        cli_anything_repo_path: str | None = None,
        provider_settings: dict[str, Any] | None = None,
        config_path: Path | None = None,
        env_path: Path | None = None,
        frontend_dist: Path | None = None,
    ) -> None:
        self.app = create_console_app(
            storage_root=storage_root,
            token=token,
            host=host,
            port=port,
            bootstrap_scopes=bootstrap_scopes,
            max_request_bytes=max_request_bytes,
            admin_allowlist=admin_allowlist,
            queue_backend_kind=queue_backend_kind,
            coordination_backend_kind=coordination_backend_kind,
            external_backend_url=external_backend_url,
            external_backend_client=external_backend_client,
            external_backend_namespace=external_backend_namespace,
            shared_state_backend_kind=shared_state_backend_kind,
            shared_state_backend_url=shared_state_backend_url,
            shared_state_backend_client=shared_state_backend_client,
            trust_mode=trust_mode,
            cli_anything_repo_path=cli_anything_repo_path,
            provider_settings=provider_settings,
            config_path=config_path,
            env_path=env_path,
            frontend_dist=frontend_dist,
        )
        self.controller: RemoteOperatorController = self.app.state.controller
        self.api = self.controller.api
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(128)
        sock.setblocking(True)
        bound_host, bound_port = sock.getsockname()
        self._socket = sock
        self._config = uvicorn.Config(self.app, host=bound_host, port=bound_port, log_level="error", access_log=False)
        self._server = uvicorn.Server(self._config)
        self.base_url = f"http://{bound_host}:{bound_port}"

    def serve_forever(self) -> None:
        self._server.run(sockets=[self._socket])

    def shutdown(self) -> None:
        self._server.should_exit = True
