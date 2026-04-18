"""Lightweight remote operator service."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, is_dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from contract_evidence_os.api.operator import OperatorAPI
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


@dataclass
class RemoteOperatorService:
    """Token-protected HTTP service for operator-safe control-plane actions."""

    storage_root: Path
    token: str
    host: str = "127.0.0.1"
    port: int = 8080
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
        )
        self.api.auth.bootstrap_credential(
            principal_name="bootstrap-admin",
            principal_type="operator",
            scopes=self.bootstrap_scopes or ["viewer", "operator", "approver", "policy-admin", "runtime-admin", "evaluator", "worker-service"],
            token=self.token,
        )
        self._server = ThreadingHTTPServer((self.host, self.port), self._handler())
        bound_host, bound_port = self._server.server_address
        self.base_url = f"http://{bound_host}:{bound_port}"

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        service = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                path = self._normalized_path(parsed.path)
                if path in (["health", "live"], ["health", "ready"]):
                    payload = self._dispatch_get(path, parse_qs(parsed.query))
                    self._write_json(200, payload)
                    return
                query = parse_qs(parsed.query)
                if self._authorized(path=path, method="GET") is None:
                    return
                try:
                    payload = self._dispatch_get(path, query)
                    if path == ["metrics"]:
                        self._write_text(200, str(payload), content_type="text/plain; version=0.0.4")
                    else:
                        self._write_json(200, payload)
                except KeyError as exc:
                    self._write_json(404, {"error": str(exc)})

            def do_POST(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                path = self._normalized_path(parsed.path)
                if int(self.headers.get("Content-Length", "0") or "0") > service.max_request_bytes:
                    self._write_json(413, {"error": "request_too_large"})
                    return
                try:
                    raw_body = self._read_raw_body()
                except ValueError as exc:
                    self._write_json(413, {"error": str(exc)})
                    return
                if self._authorized(path=path, method="POST", body=raw_body) is None:
                    return
                try:
                    body = {} if not raw_body else json.loads(raw_body.decode("utf-8"))
                    payload = self._dispatch_post(path, body)
                    self._write_json(200, payload)
                except KeyError as exc:
                    self._write_json(404, {"error": str(exc)})

            def _normalized_path(self, path_text: str) -> list[str]:
                segments = [segment for segment in path_text.strip("/").split("/") if segment]
                if segments[:1] == ["v1"]:
                    segments = segments[1:]
                return segments

            def _dispatch_get(self, path: list[str], query: dict[str, list[str]]) -> Any:
                if path == ["health", "live"]:
                    return {"live": True}
                if path == ["health", "ready"]:
                    return service.api.service_health()
                if path == ["service", "startup-validation"]:
                    return service.api.startup_validation()
                if path == ["service", "api-contract"]:
                    return service.api.api_contract()
                if path == ["reports", "system"]:
                    return service.api.system_report()
                if path == ["reports", "metrics"]:
                    return service.api.metrics_report()
                if path == ["reports", "metrics", "history"]:
                    return service.api.metrics_history(window_hours=int(query.get("window_hours", ["24"])[0]))
                if path == ["reports", "maintenance"]:
                    task_id = query.get("task_id", [None])[0]
                    return service.api.maintenance_report(task_id=task_id)
                if path == ["reports", "software-control"]:
                    return service.api.software_control_report()
                if path == ["metrics"]:
                    return service.api.prometheus_metrics()
                if path == ["workers"]:
                    return {
                        "items": [item.to_dict() for item in service.api.repository.list_workers()],
                        "hosts": [item.to_dict() for item in service.api.repository.list_host_records()],
                        "bindings": [item.to_dict() for item in service.api.repository.list_worker_host_bindings()],
                        "endpoints": [item.to_dict() for item in service.api.repository.list_worker_endpoints()],
                        "pressure": None
                        if service.api.repository.latest_worker_pressure_snapshot() is None
                        else service.api.repository.latest_worker_pressure_snapshot().to_dict(),
                    }
                if path == ["backend", "state"]:
                    return {
                        "descriptors": [item.to_dict() for item in service.api.repository.list_backend_descriptors()],
                        "health": [item.to_dict() for item in service.api.repository.list_backend_health_records()],
                        "pressure": [item.to_dict() for item in service.api.repository.list_backend_pressure_snapshots()],
                        "shared_state_descriptors": [item.to_dict() for item in service.api.repository.list_shared_state_backend_descriptors()],
                    }
                if path == ["reliability", "state"]:
                    return {
                        "incidents": [item.to_dict() for item in service.api.repository.list_reliability_incidents()],
                        "reconciliation_runs": [item.to_dict() for item in service.api.repository.list_reconciliation_runs()],
                        "backend_outages": [item.to_dict() for item in service.api.repository.list_backend_outage_records()],
                        "degradation_records": [item.to_dict() for item in service.api.repository.list_runtime_degradation_records()],
                    }
                if path == ["security", "state"]:
                    return {
                        "trust_mode": service.trust_mode,
                        "service_trust_policies": [item.to_dict() for item in service.api.repository.list_service_trust_policies()],
                        "credential_bindings": [item.to_dict() for item in service.api.repository.list_credential_binding_records()],
                        "network_identities": [item.to_dict() for item in service.api.repository.list_network_identity_records()],
                        "security_incidents": [item.to_dict() for item in service.api.repository.list_security_incidents()],
                    }
                if path == ["software", "harnesses"]:
                    return {"items": [item.to_dict() for item in service.api.list_cli_anything_harnesses()]}
                if path == ["software", "action-receipts"]:
                    task_id = query.get("task_id", [None])[0]
                    harness_id = query.get("harness_id", [None])[0]
                    return service.api.software_action_receipts(task_id=task_id, harness_id=harness_id)
                if path == ["software", "bridge"]:
                    return {
                        "bridges": [item.to_dict() for item in service.api.list_cli_anything_bridges()],
                        "build_requests": [item.to_dict() for item in service.api.repository.list_software_build_requests("cli-anything")],
                    }
                if len(path) == 4 and path[0] == "software" and path[1] == "harnesses" and path[3] == "manifest":
                    return service.api.software_harness_manifest(path[2])
                if len(path) == 4 and path[0] == "software" and path[1] == "harnesses" and path[3] == "report":
                    return service.api.software_harness_report(path[2])
                if path == ["software", "failure-clusters"]:
                    harness_id = query.get("harness_id", [None])[0]
                    return service.api.software_failure_clusters(harness_id=harness_id)
                if path == ["software", "recovery-hints"]:
                    harness_id = query.get("harness_id", [None])[0]
                    return service.api.software_recovery_hints(harness_id=harness_id)
                if path == ["auth", "scopes"]:
                    return {"items": [item.to_dict() for item in service.api.repository.list_auth_scopes()]}
                if path == ["auth", "service-principals"]:
                    return {"items": [item.to_dict() for item in service.api.repository.list_service_principals()]}
                if path == ["auth", "service-credentials"]:
                    return {"items": [item.to_dict() for item in service.api.repository.list_service_credentials()]}
                if path == ["memory", "cross-scope-timeline"]:
                    scope_keys_raw = query.get("scope_keys", [""])[0]
                    scope_keys = [item for item in scope_keys_raw.split(",") if item]
                    return service.api.cross_scope_memory_timeline(
                        scope_keys=scope_keys,
                        subject=str(query.get("subject", [""])[0]),
                        predicate=str(query.get("predicate", [""])[0]),
                    )
                if path == ["memory", "cross-scope-repairs"]:
                    scope_keys_raw = query.get("scope_keys", [""])[0]
                    scope_keys = [item for item in scope_keys_raw.split(",") if item]
                    return service.api.cross_scope_memory_repairs(
                        scope_keys=scope_keys,
                        subject=str(query.get("subject", [""])[0]),
                        predicate=str(query.get("predicate", [""])[0]),
                    )
                if path == ["tasks"]:
                    status = query.get("status", [None])[0]
                    return {"items": service.api.repository.list_tasks(status=status)}
                if path == ["queue", "status"]:
                    return service.api.queue_status()
                if path == ["queue", "dead-letter"]:
                    return {
                        "items": [
                            item for item in service.api.queue_status()["items"] if item["status"] == "dead_letter"
                        ]
                    }
                if path == ["providers", "health"]:
                    return service.api.provider_health_state()
                if path == ["providers", "fairness"]:
                    return {"items": [item.to_dict() for item in service.api.repository.list_provider_fairness_records()]}
                if path == ["policies"]:
                    return service.api.policy_registry_state()
                if path == ["system", "governance"]:
                    return service.api.system_governance_state()
                if len(path) == 3 and path[0] == "tasks" and path[2] == "status":
                    return service.api.task_status(path[1])
                if len(path) == 3 and path[0] == "tasks" and path[2] == "handoff":
                    return service.api.handoff_packet(path[1])
                if len(path) == 3 and path[0] == "tasks" and path[2] == "checkpoints":
                    return {"items": service.api.checkpoints(path[1])}
                if len(path) == 3 and path[0] == "tasks" and path[2] == "open-questions":
                    return {"items": service.api.open_questions(path[1])}
                if len(path) == 3 and path[0] == "tasks" and path[2] == "next-actions":
                    return {"items": service.api.next_actions(path[1])}
                if len(path) == 3 and path[0] == "tasks" and path[2] == "incident":
                    return service.api.incident_packet(path[1])
                if len(path) == 3 and path[0] == "tasks" and path[2] == "governance":
                    return service.api.governance_state(path[1])
                if len(path) == 3 and path[0] == "tasks" and path[2] == "memory":
                    return service.api.memory_state(path[1])
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "kernel":
                    return service.api.memory_kernel_state(path[1])
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "timeline":
                    subject = query.get("subject", [None])[0]
                    predicate = query.get("predicate", [None])[0]
                    return service.api.memory_timeline(path[1], subject=subject, predicate=predicate)
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "project-state":
                    subject = str(query.get("subject", ["user"])[0] or "user")
                    return service.api.memory_project_state(path[1], subject=subject)
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "artifacts":
                    artifact_kind = query.get("artifact_kind", [None])[0]
                    return service.api.memory_artifacts(path[1], artifact_kind=artifact_kind)
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "artifact-health":
                    return service.api.memory_artifact_health(path[1])
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-drift":
                    return service.api.memory_maintenance_drift(path[1])
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-incidents":
                    return service.api.memory_maintenance_incidents(path[1])
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-mode":
                    return service.api.memory_maintenance_mode(path[1])
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-workers":
                    return service.api.memory_maintenance_workers(path[1])
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-daemon":
                    return service.api.maintenance_daemon_state(path[1])
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "ops-diagnostics":
                    return service.api.memory_operations_diagnostics(path[1])
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "admission-promotions":
                    return service.api.memory_admission_promotions(path[1])
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-recommendations":
                    return {"items": [service.api.memory_maintenance_recommendation(path[1])["recommendation"]]}
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-promotions":
                    return service.api.memory_maintenance_promotions(path[1])
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-rollouts":
                    return service.api.memory_maintenance_rollouts(path[1])
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "policy":
                    return service.api.memory_policy_state(path[1])
                if path == ["approvals"]:
                    task_id = query.get("task_id", [None])[0]
                    status = query.get("status", ["pending"])[0]
                    return {"items": service.api.approval_inbox(task_id=task_id, status=status)}
                raise KeyError("/".join(path))

            def _dispatch_post(self, path: list[str], body: dict[str, Any]) -> Any:
                if path == ["queue", "dispatch"]:
                    return service.api.dispatch_next_queued_task(
                        worker_id=str(body.get("worker_id", "remote-worker")),
                        interrupt_after=body.get("interrupt_after"),
                    )
                if path == ["service", "shutdown"]:
                    return service.api.graceful_shutdown(reason=str(body.get("reason", "remote shutdown requested")))
                if path == ["service", "restart-recovery"]:
                    return service.api.restart_recovery()
                if path == ["reliability", "outage"]:
                    return service.api.record_backend_outage(
                        backend_name=str(body.get("backend_name", "unknown")),
                        fault_domain=str(body.get("fault_domain", "shared_state")),
                        summary=str(body.get("summary", "reported backend outage")),
                    )
                if path == ["reliability", "reconcile"]:
                    return service.api.run_reconciliation(reason=str(body.get("reason", "operator requested reconciliation")))
                if path == ["auth", "credentials"]:
                    credential, token = service.api.auth.issue_credential(
                        principal_name=str(body.get("principal_name", "operator")),
                        principal_type=str(body.get("principal_type", "operator")),
                        scopes=[str(item) for item in body.get("scopes", ["viewer"])],
                        description=str(body.get("description", "")),
                    )
                    return {"credential": credential.to_dict(), "token": token}
                if path == ["auth", "service-credentials"]:
                    credential, token = service.api.auth.issue_service_credential(
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
                            for item in service.api.discover_cli_anything_harnesses(
                                search_roots=[str(item) for item in body.get("search_roots", [])]
                            )
                        ]
                    }
                if path == ["software", "harnesses", "register"]:
                    return service.api.register_cli_anything_harness(
                        executable_path=str(body.get("executable_path", "")),
                        policy_overrides=None if "policy_overrides" not in body else dict(body.get("policy_overrides", {})),
                    )
                if path == ["software", "bridge", "configure"]:
                    return {
                        "bridge": service.api.configure_cli_anything_bridge(
                            repo_path=str(body.get("repo_path", "")),
                            enabled=bool(body.get("enabled", True)),
                        ).to_dict()
                    }
                if path == ["software", "bridge", "install-codex-skill"]:
                    return service.api.install_cli_anything_codex_skill()
                if path == ["software", "build-requests"]:
                    return {
                        "build_request": service.api.submit_cli_anything_build_request(
                            target=str(body.get("target", "")),
                            mode=str(body.get("mode", "build")),
                            focus=str(body.get("focus", "")),
                        ).to_dict()
                    }
                if len(path) == 4 and path[0] == "software" and path[1] == "harnesses" and path[3] == "validate":
                    return {"validation": service.api.validate_cli_anything_harness(path[2]).to_dict()}
                if len(path) == 4 and path[0] == "software" and path[1] == "harnesses" and path[3] == "invoke":
                    return service.api.invoke_cli_anything_harness(
                        harness_id=path[2],
                        command_path=[str(item) for item in body.get("command_path", [])],
                        arguments=[str(item) for item in body.get("arguments", [])],
                        actor=str(body.get("actor", "remote-operator")),
                        task_id=None if body.get("task_id") in {None, ""} else str(body.get("task_id")),
                        approved=bool(body.get("approved", False)),
                        dry_run=bool(body.get("dry_run", False)),
                    )
                if len(path) == 6 and path[0] == "software" and path[1] == "harnesses" and path[3] == "macros" and path[5] == "invoke":
                    return service.api.invoke_software_automation_macro(
                        macro_id=path[4],
                        actor=str(body.get("actor", "remote-operator")),
                        task_id=None if body.get("task_id") in {None, ""} else str(body.get("task_id")),
                        approved=bool(body.get("approved", False)),
                        dry_run=bool(body.get("dry_run", False)),
                    )
                if path == ["auth", "rotate"]:
                    credential, token = service.api.auth.rotate_credential(
                        str(body.get("credential_id", "")),
                        reason=str(body.get("reason", "rotation")),
                    )
                    return {
                        "credential": None if credential is None else credential.to_dict(),
                        "token": token,
                    }
                if path == ["auth", "revoke"]:
                    return service.api.auth.revoke_credential(
                        str(body.get("credential_id", "")),
                        reason=str(body.get("reason", "revoked by operator")),
                    ).to_dict()
                if path == ["system", "governance"]:
                    return service.api.control_system_governance(
                        action=str(body.get("action", "")),
                        operator=str(body.get("operator", "remote-operator")),
                        reason=str(body.get("reason", "")),
                        payload={str(key): str(value) for key, value in dict(body.get("payload", {})).items()},
                    )
                if path == ["providers", "control"]:
                    return service.api.control_system_governance(
                        action=str(body.get("action", "")),
                        operator=str(body.get("operator", "remote-operator")),
                        reason=str(body.get("reason", "")),
                        payload={str(key): str(value) for key, value in dict(body.get("payload", {})).items()},
                    )
                if path == ["policies", "candidates"]:
                    candidate = service.api.propose_policy_candidate_from_runtime(
                        name=str(body.get("name", "runtime-policy-candidate")),
                        hypothesis=str(body.get("hypothesis", "adjust runtime policy from scorecard traces")),
                        policy_payload=dict(body.get("policy_payload", {})),
                        scope_id=str(body.get("scope_id", "policy-scope-routing")),
                    )
                    return candidate
                if path == ["policies", "evaluate"]:
                    return service.api.evaluate_policy_candidate_remote(
                        str(body.get("candidate_id", "")),
                        metrics={str(key): float(value) for key, value in dict(body.get("metrics", {})).items()},
                    )
                if path == ["policies", "promote"]:
                    return service.api.promote_policy_candidate_remote(str(body.get("candidate_id", "")))
                if path == ["policies", "rollback"]:
                    return service.api.rollback_policy_scope_remote(
                        str(body.get("scope_id", "")),
                        reason=str(body.get("reason", "remote rollback requested")),
                    )
                if len(path) == 3 and path[0] == "tasks" and path[2] == "resume":
                    return service.api.resume_task(path[1], interrupt_after=body.get("interrupt_after"))
                if len(path) == 3 and path[0] == "tasks" and path[2] == "replay":
                    return service.api.replay_task(path[1])
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "evidence-pack":
                    return service.api.memory_evidence_pack(
                        path[1],
                        query=str(body.get("query", "")),
                    )
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "consolidate":
                    return service.api.consolidate_memory(
                        path[1],
                        reason=str(body.get("reason", "remote memory consolidation requested")),
                    )
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "rebuild":
                    return service.api.rebuild_memory(
                        path[1],
                        reason=str(body.get("reason", "remote memory rebuild requested")),
                    )
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "selective-rebuild":
                    return service.api.selective_rebuild_memory(
                        path[1],
                        reason=str(body.get("reason", "remote selective rebuild requested")),
                        target_kinds=[str(item) for item in body.get("target_kinds", [])],
                    )
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "operations-loop":
                    return service.api.memory_operations_loop(
                        path[1],
                        reason=str(body.get("reason", "remote memory operations loop requested")),
                        interrupt_after=None if body.get("interrupt_after") in {None, ""} else str(body.get("interrupt_after")),
                    )
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "ops-schedule":
                    return service.api.schedule_memory_operations_loop(
                        path[1],
                        cadence_hours=int(body.get("cadence_hours", 24)),
                        actor=str(body.get("actor", "remote-operator")),
                    )
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "background-maintenance":
                    return service.api.background_memory_maintenance(
                        path[1],
                        actor=str(body.get("actor", "remote-operator")),
                    )
                if len(path) == 5 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-workers" and path[4] == "register":
                    return service.api.register_maintenance_worker(
                        path[1],
                        worker_id=str(body.get("worker_id", "maintenance-worker")),
                        host_id=str(body.get("host_id", "host-local")),
                        actor=str(body.get("actor", "remote-operator")),
                    )
                if len(path) == 5 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-workers" and path[4] == "daemon":
                    return service.api.run_resident_maintenance_daemon(
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
                    return service.api.memory_maintenance_canary(path[1])
                if len(path) == 6 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-incidents" and path[5] == "resolve":
                    return service.api.resolve_maintenance_incident(
                        path[1],
                        incident_id=path[4],
                        actor=str(body.get("actor", "remote-operator")),
                        resolution=str(body.get("resolution", "resolved by operator")),
                    )
                if len(path) == 6 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-promotions" and path[5] == "apply":
                    return service.api.apply_maintenance_promotion(
                        path[1],
                        recommendation_id=path[4],
                        actor=str(body.get("actor", "remote-operator")),
                        reason=str(body.get("reason", "apply maintenance promotion")),
                    )
                if len(path) == 6 and path[0] == "tasks" and path[2] == "memory" and path[3] == "maintenance-rollouts" and path[5] == "rollback":
                    return service.api.rollback_maintenance_rollout(
                        path[1],
                        rollout_id=path[4],
                        actor=str(body.get("actor", "remote-operator")),
                        reason=str(body.get("reason", "rollback maintenance rollout")),
                    )
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "delete":
                    return service.api.delete_memory_scope(
                        path[1],
                        actor=str(body.get("actor", "remote-operator")),
                        reason=str(body.get("reason", "remote memory deletion requested")),
                    )
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "selective-purge":
                    return service.api.selective_purge_memory_scope(
                        path[1],
                        actor=str(body.get("actor", "remote-operator")),
                        reason=str(body.get("reason", "remote selective purge requested")),
                        target_kinds=[str(item) for item in body.get("target_kinds", [])],
                    )
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "hard-purge":
                    target_kinds = body.get("target_kinds")
                    return service.api.hard_purge_memory_scope(
                        path[1],
                        actor=str(body.get("actor", "remote-operator")),
                        reason=str(body.get("reason", "remote memory hard purge requested")),
                        target_kinds=None if target_kinds is None else [str(item) for item in target_kinds],
                    )
                if len(path) == 4 and path[0] == "tasks" and path[2] == "memory" and path[3] == "admission-canary":
                    return service.api.memory_admission_canary(
                        path[1],
                        candidate_ids=[str(item) for item in body.get("candidate_ids", [])],
                    )
                if path == ["memory", "cross-scope-repairs", "canary"]:
                    return service.api.cross_scope_memory_repair_canary(
                        scope_keys=[str(item) for item in body.get("scope_keys", [])],
                        subject=str(body.get("subject", "")),
                        predicate=str(body.get("predicate", "")),
                    )
                if len(path) == 4 and path[0] == "memory" and path[1] == "cross-scope-repairs" and path[3] in {"apply", "rollback"}:
                    if path[3] == "apply":
                        return service.api.apply_cross_scope_memory_repair(
                            path[2],
                            actor=str(body.get("actor", "remote-operator")),
                            reason=str(body.get("reason", "remote repair apply requested")),
                        )
                    return service.api.rollback_cross_scope_memory_repair(
                        path[2],
                        actor=str(body.get("actor", "remote-operator")),
                        reason=str(body.get("reason", "remote repair rollback requested")),
                    )
                if len(path) == 6 and path[0] == "tasks" and path[2] == "memory" and path[3] == "operations-loop" and path[5] == "resume":
                    return service.api.resume_memory_operations_loop(
                        path[4],
                        actor=str(body.get("actor", "remote-operator")),
                        reason=str(body.get("reason", "remote memory operations loop resume requested")),
                    )
                if path == ["memory", "background-maintenance", "run-due"]:
                    return service.api.run_due_background_maintenance(
                        at_time=None if body.get("at_time") in {None, ""} else str(body.get("at_time")),
                        interrupt_after=None if body.get("interrupt_after") in {None, ""} else str(body.get("interrupt_after")),
                    )
                if len(path) == 4 and path[0] == "memory" and path[1] == "maintenance-workers" and path[3] == "cycle":
                    return service.api.run_maintenance_worker_cycle(
                        worker_id=path[2],
                        at_time=None if body.get("at_time") in {None, ""} else str(body.get("at_time")),
                        interrupt_after=None if body.get("interrupt_after") in {None, ""} else str(body.get("interrupt_after")),
                    )
                if len(path) == 4 and path[0] == "memory" and path[1] == "background-maintenance" and path[3] == "resume":
                    return service.api.resume_background_maintenance(
                        path[2],
                        actor=str(body.get("actor", "remote-operator")),
                        reason=str(body.get("reason", "remote background maintenance resume requested")),
                    )
                if len(path) == 3 and path[0] == "tasks" and path[2] == "eval":
                    return service.api.trace_bundle(path[1])
                if len(path) == 3 and path[0] == "tasks" and path[2] == "candidate-eval":
                    return service.api.trace_bundle(path[1])
                if len(path) == 3 and path[0] == "tasks" and path[2] == "governance":
                    return service.api.control_governance(
                        task_id=path[1],
                        action=str(body.get("action", "")),
                        operator=str(body.get("operator", "remote-operator")),
                        reason=str(body.get("reason", "")),
                        payload={str(key): str(value) for key, value in dict(body.get("payload", {})).items()},
                    )
                if len(path) == 3 and path[0] == "approvals" and path[2] == "decision":
                    request_id = path[1]
                    decision = service.api.decide_approval(
                        request_id=request_id,
                        approver=str(body.get("approver", "remote-operator")),
                        status=str(body.get("status", "approved")),
                        rationale=str(body.get("rationale", "")),
                        approved_scope=body.get("approved_scope"),
                        intervention_action=body.get("intervention_action"),
                    )
                    request = next(item for item in service.api.repository.list_approval_requests() if item.request_id == request_id)
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
                    service.api.repository.save_remote_approval_operation(operation)
                    return decision
                raise KeyError("/".join(path))

            def _authorized(self, *, path: list[str], method: str, body: bytes = b""):
                action, required_scopes, sensitive = self._auth_requirements(path, method)
                remote_host = self.client_address[0] if self.client_address else ""
                if sensitive and service.admin_allowlist and remote_host not in service.admin_allowlist:
                    self._write_json(403, {"error": "forbidden", "reason": "remote_host_not_allowed"})
                    return None
                service_credential_id = self.headers.get("X-Service-Credential", "")
                if service.trust_mode == "hmac" and sensitive and service_credential_id:
                    trust_decision = service.api.trust.verify_request(
                        credential_id=service_credential_id,
                        method=method,
                        path="/" + "/".join(path),
                        headers={key.lower(): value for key, value in self.headers.items()},
                        body=body,
                        source_address=remote_host,
                    )
                    if not trust_decision.accepted:
                        self._write_json(409 if trust_decision.reason == "replayed_request" else 401, {"error": trust_decision.reason})
                        return None
                authorization = self.headers.get("Authorization", "")
                if not authorization.startswith("Bearer "):
                    self._write_json(401, {"error": "unauthorized"})
                    return None
                request_id = self.headers.get("X-Request-Id", f"auto-{uuid4().hex[:10]}")
                nonce = self.headers.get("X-Request-Nonce", request_id if sensitive else "")
                idempotency_key = self.headers.get("X-Idempotency-Key", request_id)
                session = service.api.auth.authenticate(authorization.removeprefix("Bearer ").strip(), request_id=request_id)
                if session is None:
                    self._write_json(401, {"error": "unauthorized"})
                    return None
                decision = service.api.auth.authorize(session, required_scopes=required_scopes, action=action)
                if not decision.allowed:
                    self._write_json(403, {"error": "forbidden", "reason": decision.reason})
                    return None
                guard = service.api.auth.record_request(
                    session=session,
                    request_id=request_id,
                    nonce=nonce,
                    idempotency_key=idempotency_key,
                    action=action,
                    sensitive=sensitive,
                )
                if not guard.accepted:
                    self._write_json(409, {"error": guard.reason})
                    return None
                return session

            def _auth_requirements(self, path: list[str], method: str) -> tuple[str, list[str], bool]:
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

            def _read_raw_body(self) -> bytes:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0:
                    return b""
                if length > service.max_request_bytes:
                    raise ValueError("request_too_large")
                return self.rfile.read(length)

            def _write_json(self, status: int, payload: Any) -> None:
                raw = json.dumps(_serialize(payload), ensure_ascii=True).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _write_text(self, status: int, payload: str, *, content_type: str) -> None:
                raw = payload.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        return Handler

    def serve_forever(self) -> None:
        self._server.serve_forever()

    def shutdown(self) -> None:
        self._server.shutdown()
        self._server.server_close()
