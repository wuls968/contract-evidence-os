"""Orchestrator and public service entry points."""

from __future__ import annotations

import json
import socket
import threading
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from contract_evidence_os.agents.registry import default_passports
from contract_evidence_os.audit.ledger import AuditLedger
from contract_evidence_os.audit.models import AuditEvent, ExecutionReceipt
from contract_evidence_os.base import utc_now
from contract_evidence_os.continuity.manager import ContinuityManager
from contract_evidence_os.continuity.models import ContinuityWorkingSet, HandoffPacket, NextAction, OpenQuestion
from contract_evidence_os.contracts.compiler import ContractCompiler
from contract_evidence_os.contracts.lattice import ContractLatticeManager
from contract_evidence_os.contracts.models import ContractLattice, TaskContract
from contract_evidence_os.evidence.graph import EvidenceBuilder
from contract_evidence_os.evidence.models import EvidenceGraph, ValidationReport
from contract_evidence_os.evidence.models import SourceRecord
from contract_evidence_os.evolution.engine import EvolutionEngine
from contract_evidence_os.memory.matrix import MemoryMatrix
from contract_evidence_os.memory.models import (
    MaintenanceDaemonRun,
    MaintenanceIncidentRecommendation,
    MaintenanceResolutionAnalytics,
    MaintenanceWorkerLeaseState,
    MemoryRecord,
    MemorySoftwareProcedureRecord,
)
from contract_evidence_os.observability.dashboard import build_software_control_report, build_system_metrics_report
from contract_evidence_os.observability.models import (
    ObservabilityAlertRecord,
    ObservabilityMetricSnapshot,
    ObservabilityTrendReport,
    SoftwareControlTelemetryRecord,
    TelemetryEvent,
)
from contract_evidence_os.planning.engine import PlanGraphEngine
from contract_evidence_os.planning.models import ExecutionBranch, PlanGraph, PlanNode, PlanRevision, SchedulerState
from contract_evidence_os.policy.lattice import PermissionLattice
from contract_evidence_os.policy.models import ApprovalDecision, ApprovalRequest, HumanIntervention
from contract_evidence_os.recovery.engine import RecoveryEngine
from contract_evidence_os.recovery.models import CheckpointRecord, IncidentReport
from contract_evidence_os.runtime.budgeting import BudgetManager
from contract_evidence_os.runtime.auth import AuthManager
from contract_evidence_os.runtime.capacity import ProviderCapacityForecaster, ProviderQuotaGovernor
from contract_evidence_os.runtime.backends import BackendPressureSnapshot, SQLiteQueueBackend
from contract_evidence_os.runtime.coordination import (
    LeaseRenewalPolicy,
    RedisCoordinationBackend,
    SQLiteCoordinationBackend,
    WorkStealPolicy,
    WorkerCapabilityRecord,
)
from contract_evidence_os.runtime.external_backends import RedisQueueBackend
from contract_evidence_os.runtime.governance import (
    ConcurrencyState,
    ExecutionModeState,
    GovernanceEvent,
    ProviderSelectionPolicy,
    ProviderGovernanceManager,
    RoutingContext,
    RoutingPolicy,
    ToolScorecardView,
)
from contract_evidence_os.runtime.model_routing import ModelRouter
from contract_evidence_os.runtime.policy_registry import PolicyRegistryManager, PolicyScope
from contract_evidence_os.runtime.provider_health import ProviderAvailabilityPolicy, ProviderHealthManager
from contract_evidence_os.runtime.provider_pool import ProviderPoolManager
from contract_evidence_os.runtime.reliability import ReliabilityManager
from contract_evidence_os.runtime.shared_state import PostgresSharedStateBackend, SQLiteSharedStateBackend
from contract_evidence_os.runtime.trust import HMACTrustManager, ServiceTrustPolicy, TrustBoundaryDescriptor
from contract_evidence_os.runtime.providers import (
    AnthropicMessagesProvider,
    OpenAIResponsesProvider,
    ProviderCapabilityRecord,
    ProviderError,
    ProviderManager,
    ProviderRequest,
    ProviderUsageRecord,
    RoutingReceipt,
)
from contract_evidence_os.runtime.queueing import (
    AdmissionPolicy,
    CapacityPolicy,
    CapacitySnapshot,
    DispatchRecord,
    GlobalExecutionModeState,
    LoadSheddingPolicy,
    OperatorOverrideRecord,
    QueueManager,
    QueuePolicy,
    QueuePriorityPolicy,
    RecoveryReservationPolicy,
)
from contract_evidence_os.storage.repository import SQLiteRepository
from contract_evidence_os.tools.governance import ToolGovernanceManager
from contract_evidence_os.tools.anything_cli.models import (
    AppCapabilityRecord,
    HarnessManifest,
    SoftwareActionReceipt,
    SoftwareAutomationMacro,
    SoftwareBuildRequest,
    SoftwareControlBridgeConfig,
    SoftwareControlPolicy,
    SoftwareFailureCluster,
    SoftwareFailurePattern,
    SoftwareHarnessRecord,
    SoftwareHarnessValidation,
    SoftwareRecoveryHint,
    SoftwareReplayDiagnostic,
    SoftwareReplayRecord,
    SoftwareRiskClass,
)
from contract_evidence_os.tools.anything_cli.tool import CLIAnythingHarnessTool
from contract_evidence_os.tools.files.tool import FileRetrievalTool
from contract_evidence_os.verification.shadow import ShadowVerifier


@dataclass
class TaskRunResult:
    """Structured task result returned by the runtime service."""

    task_id: str
    status: str
    contract: TaskContract
    plan: PlanGraph
    contract_lattice: ContractLattice
    delivery: dict[str, object]
    validation_report: ValidationReport
    evidence_graph: EvidenceGraph
    audit_events: list[AuditEvent]
    receipts: list[ExecutionReceipt]
    routing_receipts: list[RoutingReceipt] = field(default_factory=list)
    incident: IncidentReport | None = None
    handoff_packet: HandoffPacket | None = None
    continuity_working_set: ContinuityWorkingSet | None = None
    open_questions: list[OpenQuestion] = field(default_factory=list)
    next_actions: list[NextAction] = field(default_factory=list)


class RuntimeInterrupted(RuntimeError):
    """Raised when execution is intentionally interrupted after a durable checkpoint."""

    def __init__(self, task_id: str, phase: str) -> None:
        super().__init__(f"task {task_id} interrupted at {phase}")
        self.task_id = task_id
        self.phase = phase


@dataclass
class RuntimeService:
    """Main orchestrator for the Contract-Evidence OS vertical slice."""

    storage_root: Path
    routing_strategy: str = "quality"
    queue_backend_kind: str = "sqlite"
    coordination_backend_kind: str = "sqlite"
    external_backend_url: str | None = None
    external_backend_client: object | None = None
    external_backend_namespace: str = "ceos"
    shared_state_backend_kind: str = "sqlite"
    shared_state_backend_url: str | None = None
    shared_state_backend_client: object | None = None
    trust_mode: str = "standard"
    compiler: ContractCompiler = field(default_factory=ContractCompiler)
    lattice_manager: ContractLatticeManager = field(default_factory=ContractLatticeManager)
    planner: PlanGraphEngine = field(default_factory=PlanGraphEngine)
    model_router: ModelRouter = field(default_factory=ModelRouter)
    permission_lattice: PermissionLattice = field(default_factory=PermissionLattice)
    verifier: ShadowVerifier = field(default_factory=ShadowVerifier)
    provider_manager: ProviderManager = field(default_factory=ProviderManager)
    memory: MemoryMatrix = field(default_factory=MemoryMatrix)
    evolution: EvolutionEngine = field(default_factory=EvolutionEngine)
    cli_anything_repo_path: str | None = None

    def __post_init__(self) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.repository = SQLiteRepository(self.storage_root / "contract_evidence_os.sqlite3")
        self.audit = AuditLedger(repository=self.repository)
        self.recovery = RecoveryEngine(storage_root=self.storage_root, repository=self.repository)
        self.continuity = ContinuityManager(repository=self.repository, storage_root=self.storage_root)
        self.memory.repository = self.repository
        self.memory.artifact_root = self.storage_root / "artifacts"
        self.evolution.repository = self.repository
        self.file_tool = FileRetrievalTool()
        self.software_control_tool = CLIAnythingHarnessTool()
        self.tool_governance = ToolGovernanceManager()
        self.provider_governance = ProviderGovernanceManager()
        self.budget_manager = BudgetManager()
        self.provider_health = ProviderHealthManager(repository=self.repository)
        self.queue = QueueManager(repository=self.repository)
        if self.queue_backend_kind == "redis":
            self.queue_backend = RedisQueueBackend(
                self.repository,
                client=self.external_backend_client,
                url=self.external_backend_url,
                namespace=self.external_backend_namespace,
            )
        else:
            self.queue_backend = SQLiteQueueBackend(self.repository)
        if self.coordination_backend_kind == "redis":
            self.coordination = RedisCoordinationBackend(
                self.repository,
                client=self.external_backend_client,
                url=self.external_backend_url,
                namespace=self.external_backend_namespace,
            )
        else:
            self.coordination = SQLiteCoordinationBackend(self.repository)
        if self.shared_state_backend_kind == "postgres":
            self.shared_state_backend = PostgresSharedStateBackend(
                url=self.shared_state_backend_url,
                client=self.shared_state_backend_client,
            )
        else:
            self.shared_state_backend = SQLiteSharedStateBackend(self.storage_root / "shared_state.sqlite3")
        self.provider_pool = ProviderPoolManager(self.repository)
        self.auth = AuthManager(self.repository)
        self.trust = HMACTrustManager(repository=self.repository)
        self.reliability_manager = ReliabilityManager(repository=self.repository, shared_state=self.shared_state_backend)
        self.capacity_forecaster = ProviderCapacityForecaster(repository=self.repository, shared_state=self.shared_state_backend)
        self.quota_governor = ProviderQuotaGovernor(repository=self.repository, shared_state=self.shared_state_backend)
        self.policy_registry = PolicyRegistryManager(repository=self.repository)
        self.passports = default_passports()
        self.task_results: dict[str, TaskRunResult] = {}
        self.task_status_cache: dict[str, str] = {}
        self.execution_mode_overrides: dict[str, str] = {}
        self.disabled_providers: set[str] = set()
        self.disabled_tools: set[str] = set()
        self.concurrency_caps: dict[str, int] = {}
        self.system_mode: str = "normal"
        self._evidence_lock = threading.Lock()
        self._active_dispatch_context: dict[str, str] | None = None
        self._ensure_provider_registration()
        self._ensure_system_scale_registration()
        self._refresh_backend_state()
        self.default_routing_policy = self._build_routing_policy("standard")
        self.repository.save_routing_policy(self.default_routing_policy)
        if self.cli_anything_repo_path:
            self.configure_cli_anything_bridge(repo_path=self.cli_anything_repo_path, enabled=True)

    def create_task(
        self,
        goal: str,
        attachments: list[str],
        preferences: dict[str, str],
        prohibitions: list[str],
        task_id: str | None = None,
    ) -> dict[str, object]:
        task_id = task_id or f"task-{uuid4().hex[:10]}"
        request = {
            "task_id": task_id,
            "goal": goal,
            "attachments": attachments,
            "preferences": preferences,
            "prohibitions": prohibitions,
            "created_at": utc_now().isoformat(),
        }
        self._persist_task_state(task_id, "created", "created", request)
        created_at = utc_now()
        self.memory.record_raw_episode(
            task_id=task_id,
            episode_type="task_request",
            actor="user",
            scope_key=task_id,
            project_id=task_id,
            content={
                "goal": goal,
                "attachments": attachments,
                "preferences": preferences,
                "prohibitions": prohibitions,
            },
            source="task_request",
            consent="granted",
            trust=1.0,
            dialogue_time=created_at,
            event_time_start=created_at,
        )
        self._emit_telemetry(task_id, "task_created", {"goal": goal, "attachments": attachments})
        return request

    def compile_contract(
        self,
        goal: str,
        attachments: list[str],
        preferences: dict[str, str],
        prohibitions: list[str],
    ) -> TaskContract:
        return self.compiler.compile(goal, attachments, preferences, prohibitions)

    def generate_plan(self, contract: TaskContract, attachments: list[str]) -> PlanGraph:
        return self.planner.generate(contract, attachments)

    def execute_node(
        self,
        task_id: str,
        contract: TaskContract,
        node: PlanNode,
        attachments: list[str],
        evidence: EvidenceBuilder,
    ) -> IncidentReport | None:
        self._assert_active_dispatch_ownership()
        handler = node.handler_name or ""
        if handler == "retrieve_source" or node.node_id.startswith("node-retrieve-source"):
            return self._execute_retrieve_node(task_id, contract, node, evidence)
        if handler == "extract_source" or node.node_id.startswith("node-extract-source"):
            return self._execute_extract_node(task_id, contract, node, evidence)
        if handler == "build_delivery" or node.node_id == "node-build-delivery":
            return self._execute_build_node(task_id, contract, node, evidence)
        if handler == "verify_delivery" or node.node_id == "node-verify-delivery":
            return self._execute_verify_node(task_id, contract, node, evidence)
        if handler == "capture_learning" or node.node_id == "node-capture-learning":
            return self._execute_memory_node(task_id, contract, node, evidence)
        return None

    def _execute_retrieve_node(
        self,
        task_id: str,
        contract: TaskContract,
        node: PlanNode,
        evidence: EvidenceBuilder,
    ) -> IncidentReport | None:
        researcher = self.passports["Researcher"]
        authorization = self.permission_lattice.authorize(
            passport=researcher,
            action="read",
            tool_name="file_retrieval",
            risk_level="low",
        )
        if not authorization.allowed:
            incident = self.recovery.classify_failure(task_id, "permission_denial", authorization.reason)
            self._audit_event(
                task_id=task_id,
                contract_id=contract.contract_id,
                event_type="policy_violation",
                actor="Governor",
                why=authorization.reason,
                risk_level=contract.risk_level,
                result="denied",
            )
            return incident

        path = node.attachment_ref or ""
        budget_incident = self._budget_check(task_id, "tool", 0.001)
        if budget_incident is not None:
            return budget_incident
        self._select_tool_variant(task_id=task_id, plan_node_id=node.node_id, tool_name="file_retrieval")
        invocation, result, source = self.file_tool.invoke(
            path,
            actor=researcher.role_name,
            task_id=task_id,
            plan_node_id=node.node_id,
            correlation_id=f"{task_id}:{node.node_id}:file_retrieval",
        )
        self.repository.save_tool_invocation(task_id, invocation)
        self.repository.save_tool_result(task_id, result)
        self._emit_telemetry(
            task_id,
            "tool_invocation_completed",
            {"tool_id": result.tool_id, "status": result.status, "provider_mode": result.provider_mode, "plan_node_id": node.node_id},
        )

        if result.status != "success" or source is None:
            scorecard = self.tool_governance.update(
                scorecard=self.repository.get_tool_scorecard(result.tool_id, result.provider_mode),
                result=result,
                evidence_usefulness=0.0,
            )
            self.repository.save_tool_scorecard(scorecard)
            incident = self.recovery.classify_failure(task_id, "tool_failure", result.error or "tool failed")
            self._audit_event(
                task_id=task_id,
                contract_id=contract.contract_id,
                event_type="tool_invocation",
                actor=researcher.role_name,
                why=node.objective,
                risk_level=contract.risk_level,
                result="failed",
                tool_refs=[invocation.tool_id],
            )
            return incident

        with self._evidence_lock:
            source_node = evidence.add_source(source)
            self.repository.save_source_record(task_id, source)
            self.repository.save_evidence_graph(task_id, evidence.graph, evidence.claims)
        scorecard = self.tool_governance.update(
            scorecard=self.repository.get_tool_scorecard(result.tool_id, result.provider_mode),
            result=result,
            evidence_usefulness=0.6,
        )
        self.repository.save_tool_scorecard(scorecard)
        self._record_budget_consumption(
            task_id=task_id,
            category="tool",
            ref_id=invocation.invocation_id,
            estimated_cost=0.001,
            actual_cost=0.001,
            justification="file retrieval for evidence source",
        )
        self._record_execution_receipt(
            task_id=task_id,
            contract_id=contract.contract_id,
            node=node,
            actor=researcher.role_name,
            tool_used="file_retrieval",
            input_summary=f"Read {path}",
            output_summary=f"Retrieved source snapshot for {path}",
            artifacts=[invocation.invocation_id],
            evidence_refs=[source_node.node_id],
        )
        self._audit_event(
            task_id=task_id,
            contract_id=contract.contract_id,
            event_type="tool_invocation",
            actor=researcher.role_name,
            why=node.objective,
            risk_level=contract.risk_level,
            result="success",
            evidence_refs=[source_node.node_id],
            tool_refs=[invocation.tool_id],
        )
        self._mark_node_completed(task_id, node)
        return None

    def _execute_extract_node(
        self,
        task_id: str,
        contract: TaskContract,
        node: PlanNode,
        evidence: EvidenceBuilder,
    ) -> IncidentReport | None:
        researcher = self.passports["Researcher"]
        attachment_path = node.attachment_ref or ""
        content = Path(attachment_path).read_text(encoding="utf-8")
        strategy = "economy" if node.node_category == "recovery" else self.routing_strategy
        route = self.model_router.route(
            role=researcher.role_name,
            workload="extraction",
            risk_level=contract.risk_level,
            strategy_name=strategy,
        )
        route, routing_decision = self._route_provider(
            task_id=task_id,
            plan_node_id=node.node_id,
            role=researcher.role_name,
            workload="extraction",
            risk_level=contract.risk_level,
            requires_structured_output=False,
            base_route=route,
        )
        budget_incident = self._budget_check(task_id, "provider", 0.01 if routing_decision.chosen_provider.startswith("openai") else 0.004)
        if budget_incident is not None:
            return budget_incident
        if routing_decision.chosen_provider and not self._reserve_provider_slot(routing_decision.chosen_provider):
            return self.recovery.classify_failure(task_id, "provider_error", f"{routing_decision.chosen_provider} unavailable")
        provider_request = ProviderRequest(
            version="1.0",
            request_id=f"provider-request-{uuid4().hex[:10]}",
            task_id=task_id,
            role=researcher.role_name,
            workload="extraction",
            prompt="Extract grounded mandatory constraint statements from the content.",
            input_payload={"content": content, "path": attachment_path},
            plan_node_id=node.node_id,
            correlation_id=f"{task_id}:{node.node_id}:provider",
            created_at=utc_now(),
        )
        try:
            provider_response, routing_receipt = self.provider_manager.complete(route=route, request=provider_request)
        except ProviderError as exc:
            if routing_decision.chosen_provider:
                self._record_provider_failure(provider_name=routing_decision.chosen_provider, error_code=exc.code)
            self._audit_event(
                task_id=task_id,
                contract_id=contract.contract_id,
                event_type="model_routing",
                actor=researcher.role_name,
                why=f"{route.strategy_name}:{route.profile}",
                risk_level=contract.risk_level,
                result="failed",
                tool_refs=[route.model_name],
            )
            return self.recovery.classify_failure(task_id, "provider_error", str(exc))
        self._record_provider_success(
            provider_name=provider_response.provider_name,
            latency_ms=provider_response.latency_ms,
            structured_output_ok=True,
        )

        usage_record = self.provider_manager.build_usage_record(
            provider_request,
            route,
            provider_response,
            routing_receipt,
            estimated_cost=self._estimate_provider_cost(provider_response.provider_name, provider_response.usage),
        )
        self.repository.save_routing_receipt(task_id, routing_receipt)
        self.repository.save_provider_usage_record(usage_record)
        provider_scorecard = self.provider_governance.update(
            self.repository.get_provider_scorecard(provider_response.provider_name, route.profile),
            provider_name=provider_response.provider_name,
            profile=route.profile,
            success=True,
            structured_output_ok=True,
            retry_count=max(routing_receipt.attempt_count - 1, 0),
            fallback_used=routing_receipt.fallback_used,
            latency_ms=provider_response.latency_ms,
            cost=usage_record.estimated_cost,
            verification_usefulness=0.7,
            continuity_usefulness=0.6,
        )
        self.repository.save_provider_scorecard(provider_scorecard)
        self._record_budget_consumption(
            task_id=task_id,
            category="provider",
            ref_id=usage_record.usage_id,
            estimated_cost=usage_record.estimated_cost,
            actual_cost=usage_record.estimated_cost,
            justification=f"provider extraction via {provider_response.provider_name}",
        )
        self._audit_event(
            task_id=task_id,
            contract_id=contract.contract_id,
            event_type="model_routing",
            actor=researcher.role_name,
            why=f"{route.strategy_name}:{route.profile}",
            risk_level=contract.risk_level,
            result="success",
            tool_refs=[routing_receipt.provider_name],
        )
        source_node = self._find_source_node(evidence, attachment_path)
        if source_node is None:
            return self.recovery.classify_failure(task_id, "evidence_inconsistency", f"missing source node for {attachment_path}")
        statements = [
            str(item.get("statement", ""))
            for item in provider_response.output_payload.get("statements", [])
            if str(item.get("statement", "")).strip()
        ]
        with self._evidence_lock:
            extraction_nodes = evidence.add_extractions(source_node, statements)
            self.repository.save_evidence_graph(task_id, evidence.graph, evidence.claims)
        self._record_execution_receipt(
            task_id=task_id,
            contract_id=contract.contract_id,
            node=node,
            actor=researcher.role_name,
            tool_used="provider_extraction",
            input_summary=f"Extract from {attachment_path}",
            output_summary=f"Captured {len(statements)} grounded statements via {route.profile}",
            artifacts=[provider_request.request_id, routing_receipt.routing_id],
            evidence_refs=[source_node.node_id, *[item.node_id for item in extraction_nodes]],
        )
        self._mark_node_completed(task_id, node)
        return None

    def _execute_build_node(
        self,
        task_id: str,
        contract: TaskContract,
        node: PlanNode,
        evidence: EvidenceBuilder,
    ) -> IncidentReport | None:
        route = self.model_router.route(
            role="Builder",
            workload="build",
            risk_level=contract.risk_level,
            strategy_name=self.routing_strategy,
        )
        route, routing_decision = self._route_provider(
            task_id=task_id,
            plan_node_id=node.node_id,
            role="Builder",
            workload="build",
            risk_level=contract.risk_level,
            requires_structured_output=True,
            base_route=route,
        )
        budget_incident = self._budget_check(task_id, "provider", 0.012 if routing_decision.chosen_provider.startswith("openai") else 0.005)
        if budget_incident is not None:
            return budget_incident
        if routing_decision.chosen_provider and not self._reserve_provider_slot(routing_decision.chosen_provider):
            return self.recovery.classify_failure(task_id, "provider_error", f"{routing_decision.chosen_provider} unavailable")
        facts = [claim.statement for claim in evidence.claims]
        provider_request = ProviderRequest(
            version="1.0",
            request_id=f"provider-request-{uuid4().hex[:10]}",
            task_id=task_id,
            role="Builder",
            workload="build",
            prompt="Build a concise structured delivery preview from the evidence-bound facts.",
            input_payload={"facts": facts},
            structured_output={
                "name": "delivery_preview",
                "schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                        "fact_count": {"type": "integer"},
                    },
                    "required": ["summary", "fact_count"],
                },
            },
            plan_node_id=node.node_id,
            correlation_id=f"{task_id}:{node.node_id}:provider",
            created_at=utc_now(),
        )
        try:
            provider_response, routing_receipt = self.provider_manager.complete(route=route, request=provider_request)
        except ProviderError as exc:
            if routing_decision.chosen_provider:
                self._record_provider_failure(provider_name=routing_decision.chosen_provider, error_code=exc.code)
            return self.recovery.classify_failure(task_id, "provider_error", str(exc))
        self._record_provider_success(
            provider_name=provider_response.provider_name,
            latency_ms=provider_response.latency_ms,
            structured_output_ok=True,
        )
        self.repository.save_routing_receipt(task_id, routing_receipt)
        usage_record = self.provider_manager.build_usage_record(
            provider_request,
            route,
            provider_response,
            routing_receipt,
            estimated_cost=self._estimate_provider_cost(provider_response.provider_name, provider_response.usage),
        )
        self.repository.save_provider_usage_record(usage_record)
        self.repository.save_provider_scorecard(
            self.provider_governance.update(
                self.repository.get_provider_scorecard(provider_response.provider_name, route.profile),
                provider_name=provider_response.provider_name,
                profile=route.profile,
                success=True,
                structured_output_ok=True,
                retry_count=max(routing_receipt.attempt_count - 1, 0),
                fallback_used=routing_receipt.fallback_used,
                latency_ms=provider_response.latency_ms,
                cost=usage_record.estimated_cost,
                verification_usefulness=0.5,
                continuity_usefulness=0.5,
            )
        )
        self._record_budget_consumption(
            task_id=task_id,
            category="provider",
            ref_id=usage_record.usage_id,
            estimated_cost=usage_record.estimated_cost,
            actual_cost=usage_record.estimated_cost,
            justification=f"provider build via {provider_response.provider_name}",
        )
        self._record_execution_receipt(
            task_id=task_id,
            contract_id=contract.contract_id,
            node=node,
            actor="Builder",
            tool_used="provider_build",
            input_summary=f"Build from {len(facts)} supported facts",
            output_summary=str(provider_response.output_payload)[:160],
            artifacts=[provider_request.request_id, routing_receipt.routing_id],
            evidence_refs=[claim.evidence_refs[0] for claim in evidence.claims if claim.evidence_refs],
        )
        self._mark_node_completed(task_id, node)
        return None

    def _execute_verify_node(
        self,
        task_id: str,
        contract: TaskContract,
        node: PlanNode,
        evidence: EvidenceBuilder,
    ) -> IncidentReport | None:
        delivery = self._build_delivery(evidence)
        route = self.model_router.route(
            role="Verifier",
            workload="verification",
            risk_level=contract.risk_level,
            strategy_name=self.routing_strategy,
        )
        route, routing_decision = self._route_provider(
            task_id=task_id,
            plan_node_id=node.node_id,
            role="Verifier",
            workload="verification",
            risk_level=contract.risk_level,
            requires_structured_output=False,
            base_route=route,
        )
        budget_incident = self._budget_check(task_id, "verification", 0.012 if routing_decision.chosen_provider.startswith("openai") else 0.005)
        if budget_incident is not None:
            return budget_incident
        if routing_decision.chosen_provider and not self._reserve_provider_slot(routing_decision.chosen_provider):
            return self.recovery.classify_failure(task_id, "provider_error", f"{routing_decision.chosen_provider} unavailable")
        provider_request = ProviderRequest(
            version="1.0",
            request_id=f"provider-request-{uuid4().hex[:10]}",
            task_id=task_id,
            role="Verifier",
            workload="verification",
            prompt="Verify that all claims remain evidence-bound and policy-safe.",
            input_payload={"facts": delivery["facts"]},
            plan_node_id=node.node_id,
            correlation_id=f"{task_id}:{node.node_id}:provider",
            created_at=utc_now(),
        )
        try:
            provider_response, routing_receipt = self.provider_manager.complete(route=route, request=provider_request)
        except ProviderError as exc:
            if routing_decision.chosen_provider:
                self._record_provider_failure(provider_name=routing_decision.chosen_provider, error_code=exc.code)
            return self.recovery.classify_failure(task_id, "provider_error", str(exc))
        self._record_provider_success(
            provider_name=provider_response.provider_name,
            latency_ms=provider_response.latency_ms,
            structured_output_ok=True,
        )
        self.repository.save_routing_receipt(task_id, routing_receipt)
        usage_record = self.provider_manager.build_usage_record(
            provider_request,
            route,
            provider_response,
            routing_receipt,
            estimated_cost=self._estimate_provider_cost(provider_response.provider_name, provider_response.usage),
        )
        self.repository.save_provider_usage_record(usage_record)
        self.repository.save_provider_scorecard(
            self.provider_governance.update(
                self.repository.get_provider_scorecard(provider_response.provider_name, route.profile),
                provider_name=provider_response.provider_name,
                profile=route.profile,
                success=True,
                structured_output_ok=True,
                retry_count=max(routing_receipt.attempt_count - 1, 0),
                fallback_used=routing_receipt.fallback_used,
                latency_ms=provider_response.latency_ms,
                cost=usage_record.estimated_cost,
                verification_usefulness=0.95,
                continuity_usefulness=0.6,
            )
        )
        self._record_budget_consumption(
            task_id=task_id,
            category="verification",
            ref_id=usage_record.usage_id,
            estimated_cost=usage_record.estimated_cost,
            actual_cost=usage_record.estimated_cost,
            justification=f"provider verification via {provider_response.provider_name}",
        )
        report = self.verifier.verify(
            contract=contract,
            evidence_graph=evidence.graph,
            delivery_claims=delivery["facts"],
        )
        self.repository.save_validation_report(task_id, report)
        self._record_execution_receipt(
            task_id=task_id,
            contract_id=contract.contract_id,
            node=node,
            actor="Verifier",
            tool_used="shadow_verification",
            input_summary=f"Verify {len(delivery['facts'])} delivery facts",
            output_summary=report.status,
            artifacts=[provider_request.request_id, routing_receipt.routing_id],
            evidence_refs=report.evidence_refs,
            validation_refs=[report.report_id],
        )
        if report.status != "passed":
            return self.recovery.classify_failure(task_id, "verification_failure", "; ".join(report.findings + report.contradictions))
        self._mark_node_completed(task_id, node)
        return None

    def _execute_memory_node(
        self,
        task_id: str,
        contract: TaskContract,
        node: PlanNode,
        evidence: EvidenceBuilder,
    ) -> IncidentReport | None:
        budget_incident = self._budget_check(task_id, "continuity", 0.002)
        if budget_incident is not None:
            return budget_incident
        self._apply_learning_and_evolution(
            task_id=task_id,
            contract=contract,
            delivery=self._build_delivery(evidence),
            evidence=evidence,
        )
        self._record_budget_consumption(
            task_id=task_id,
            category="continuity",
            ref_id=node.node_id,
            estimated_cost=0.002,
            actual_cost=0.002,
            justification="continuity and evolution capture",
        )
        self._record_execution_receipt(
            task_id=task_id,
            contract_id=contract.contract_id,
            node=node,
            actor="Archivist",
            tool_used="memory_evolution",
            input_summary="Capture reusable trace knowledge",
            output_summary="Stored episodic memory and evaluated evolution candidate",
            artifacts=[],
            evidence_refs=[claim.evidence_refs[0] for claim in evidence.claims if claim.evidence_refs],
        )
        self._mark_node_completed(task_id, node)
        return None

    def _find_source_node(self, evidence: EvidenceBuilder, attachment_path: str):
        for candidate in reversed(evidence.graph.nodes):
            if candidate.node_type == "source" and candidate.content == attachment_path:
                return candidate
        return None

    def _record_execution_receipt(
        self,
        *,
        task_id: str,
        contract_id: str,
        node: PlanNode,
        actor: str,
        tool_used: str,
        input_summary: str,
        output_summary: str,
        artifacts: list[str],
        evidence_refs: list[str],
        validation_refs: list[str] | None = None,
        approval_refs: list[str] | None = None,
    ) -> ExecutionReceipt:
        receipt = ExecutionReceipt(
            version="1.0",
            receipt_id=f"receipt-{uuid4().hex[:10]}",
            contract_id=contract_id,
            plan_node_id=node.node_id,
            actor=actor,
            tool_used=tool_used,
            input_summary=input_summary,
            output_summary=output_summary,
            artifacts=artifacts,
            evidence_refs=evidence_refs,
            validation_refs=validation_refs or [],
            approval_refs=approval_refs or [],
            status="success",
            timestamp=utc_now(),
        )
        self.repository.save_execution_receipt(task_id, receipt)
        return receipt

    def _mark_node_completed(self, task_id: str, node: PlanNode) -> None:
        node.status = "completed"
        self.repository.update_plan_node_status(task_id, node.node_id, "completed")

    def _ensure_provider_registration(self) -> None:
        for provider in self.provider_manager.providers.values():
            capability_method = getattr(provider, "capability", None)
            if callable(capability_method):
                self.repository.save_provider_capability(capability_method())
                continue
            self.repository.save_provider_capability(
                ProviderCapabilityRecord(
                    version="1.0",
                    provider_name=str(getattr(provider, "name", "provider")),
                    supported_response_modes=["completion"],
                    supports_structured_output=True,
                    max_context_hint=32000,
                    cost_characteristics="low" if getattr(provider, "provider_mode", "live") != "live" else "medium",
                    rate_limit_characteristics="n/a",
                    reliability_inputs={"base": 0.75},
                    timeout_defaults={"seconds": 5.0},
                    retry_defaults={"max_attempts": 2},
                    availability_state="available",
                )
            )

    def _ensure_system_scale_registration(self) -> None:
        if self.repository.load_queue_policy("default") is None:
            self.repository.save_queue_policy(
                QueuePolicy(
                    version="1.0",
                    policy_id="queue-policy-default",
                    queue_name="default",
                    max_attempts=3,
                    lease_timeout_seconds=60,
                    dead_letter_queue="dead-letter",
                )
            )
        if self.repository.latest_admission_policy() is None:
            self.repository.save_admission_policy(
                AdmissionPolicy(
                    version="1.0",
                    policy_id="admission-policy-default",
                    allow_high_risk_when_provider_degraded=False,
                    max_active_tasks=2,
                    max_pending_approvals=5,
                    continuity_fragility_threshold=0.75,
                    budget_pressure_threshold=0.4,
                )
            )
        if self.repository.latest_queue_priority_policy() is None:
            self.repository.save_queue_priority_policy(
                QueuePriorityPolicy(
                    version="1.0",
                    policy_id="queue-priority-default",
                    class_weights={"background_eval": 1, "standard": 10, "recovery": 30},
                    resumed_task_bonus=5,
                    stale_continuity_bonus=10,
                    recovery_priority_bonus=20,
                    high_risk_bonus=15,
                )
            )
        if self.repository.latest_capacity_policy() is None:
            self.repository.save_capacity_policy(
                CapacityPolicy(
                    version="1.0",
                    policy_id="capacity-policy-default",
                    max_active_tasks=2,
                    max_active_high_risk_tasks=1,
                    max_provider_parallelism={provider_name: 2 for provider_name in self.provider_manager.providers},
                    max_tool_parallelism={"file_retrieval": 2},
                )
            )
        if self.repository.latest_load_shedding_policy() is None:
            self.repository.save_load_shedding_policy(
                LoadSheddingPolicy(
                    version="1.0",
                    policy_id="load-shedding-default",
                    reject_low_priority_under_degraded_mode=True,
                    defer_background_evals_when_recovery_reserved=True,
                )
            )
        if self.repository.latest_recovery_reservation_policy() is None:
            self.repository.save_recovery_reservation_policy(
                RecoveryReservationPolicy(
                    version="1.0",
                    policy_id="recovery-reservation-default",
                    reserve_active_slots=1,
                    reserve_budget_fraction=0.15,
                )
            )
        if self.repository.latest_global_execution_mode() is None:
            self.repository.save_global_execution_mode(
                GlobalExecutionModeState(
                    version="1.0",
                    mode_id=f"global-mode-{uuid4().hex[:10]}",
                    mode_name="normal",
                    reason="default startup mode",
                    active_constraints=[],
                )
            )
        for provider_name in self.provider_manager.providers:
            if self.repository.load_provider_availability_policy(provider_name) is None:
                self.repository.save_provider_availability_policy(
                    ProviderAvailabilityPolicy(
                        version="1.0",
                        policy_id=f"provider-availability-{provider_name}",
                        provider_name=provider_name,
                        failure_threshold=3,
                        cooldown_seconds=30,
                        rate_limit_window_seconds=60,
                        max_requests_per_window=30,
                    )
                )
            if self.repository.load_provider_capacity_record(provider_name) is None:
                self.provider_pool.register_capacity(
                    provider_name,
                    max_parallel=2,
                    reservation_slots={"verification": 1, "recovery": 1},
                )
            if self.repository.load_provider_quota_policy(provider_name) is None:
                self.quota_governor.set_quota_policy(
                    provider_name=provider_name,
                    per_role_quota={"builder": 2, "verifier": 2, "strategist": 1},
                    protected_reservations={"verification": 1, "recovery": 1},
                    low_priority_cap=1,
                )
        if not self.repository.list_policy_scopes():
            routing_scope = PolicyScope(
                version="1.0",
                scope_id="policy-scope-routing",
                scope_type="routing",
                target_component="provider_selection",
                constraints=["no_policy_boundary_violation"],
            )
            self.policy_registry.register_policy_version(
                name="routing-default",
                scope=routing_scope,
                policy_payload={"execution_mode": "standard", "prefer_low_cost": False},
                summary="Default routing policy.",
            )
        if not self.repository.list_trust_boundary_descriptors():
            self.repository.save_trust_boundary_descriptor(
                TrustBoundaryDescriptor(
                    version="1.0",
                    boundary_id="trust-boundary-default",
                    boundary_name="default-runtime-boundary",
                    trusted_proxy_headers=["x-forwarded-for", "x-forwarded-proto"],
                    enforce_loopback_admin=True,
                    allow_service_assertion=True,
                )
            )
        if not self.repository.list_service_trust_policies():
            self.repository.save_service_trust_policy(
                ServiceTrustPolicy(
                    version="1.0",
                    policy_id="service-trust-default",
                    trust_mode=self.trust_mode,
                    require_nonce=True,
                    max_clock_skew_seconds=120,
                    signed_headers=["x-request-id", "x-request-timestamp", "x-request-nonce"],
                    allowed_networks=["127.0.0.1/32", "::1/128"],
                )
            )

    def _refresh_backend_state(self) -> None:
        queue_descriptor = self.queue_backend.descriptor()
        coordination_descriptor = self.coordination.descriptor()
        self.repository.save_backend_descriptor(queue_descriptor)
        self.repository.save_backend_descriptor(coordination_descriptor)
        shared_descriptor = self.shared_state_backend.descriptor()
        self.repository.save_shared_state_backend_descriptor(shared_descriptor)
        self.repository.save_backend_health_record(self.queue_backend.health())
        self.repository.save_backend_health_record(self.coordination.health())
        shared_health = self.shared_state_backend.health()
        self.repository.save_backend_health_record(shared_health)
        self.shared_state_backend.save_descriptor(shared_descriptor)
        self.shared_state_backend.save_health(shared_health)
        queue_items = self.repository.list_queue_items(statuses=["queued", "deferred", "leased"])
        self.repository.save_backend_pressure_snapshot(
            BackendPressureSnapshot(
                version="1.0",
                snapshot_id=f"backend-pressure-{uuid4().hex[:10]}",
                backend_name=queue_descriptor.backend_name,
                queue_depth=len([item for item in queue_items if item.status in {"queued", "deferred"}]),
                active_leases=len([item for item in queue_items if item.status == "leased"]),
                active_workers=len([item for item in self.repository.list_workers() if item.shutdown_state == "running"]),
                delayed_tasks=len([item for item in queue_items if item.status == "deferred"]),
            )
        )
        self.shared_state_backend.upsert_record(
            record_type="backend_pressure_snapshot",
            record_id=f"backend-pressure-{uuid4().hex[:10]}",
            scope_key=queue_descriptor.backend_name,
            payload=self.repository.list_backend_pressure_snapshots()[-1].to_dict(),
        )

    def _default_worker_capability(self, worker_id: str) -> WorkerCapabilityRecord:
        return WorkerCapabilityRecord(
            version="1.0",
            worker_id=worker_id,
            provider_access=list(self.provider_manager.providers),
            tool_access=["file_retrieval"],
            role_specialization=["Researcher", "Builder", "Verifier", "Strategist", "Archivist"],
            supports_degraded_mode=True,
            supports_high_risk=True,
            max_parallel_tasks=1,
        )

    def _build_routing_policy(self, execution_mode: str) -> RoutingPolicy:
        provider_policy = {
            "standard": ProviderSelectionPolicy(prefer_live=True, require_structured_output=False, verification_bias=False, prefer_low_cost=False, allow_degraded_fallback=True),
            "low_cost": ProviderSelectionPolicy(prefer_live=True, require_structured_output=False, verification_bias=False, prefer_low_cost=True, allow_degraded_fallback=True),
            "verification_heavy": ProviderSelectionPolicy(prefer_live=True, require_structured_output=True, verification_bias=True, prefer_low_cost=False, allow_degraded_fallback=True),
            "high_risk": ProviderSelectionPolicy(prefer_live=True, require_structured_output=True, verification_bias=True, prefer_low_cost=False, allow_degraded_fallback=False),
        }.get(
            execution_mode,
            ProviderSelectionPolicy(prefer_live=True, require_structured_output=False, verification_bias=False, prefer_low_cost=False, allow_degraded_fallback=True),
        )
        return RoutingPolicy(
            version="1.0",
            policy_id=f"routing-policy-{execution_mode}",
            name=f"{execution_mode}-policy",
            execution_mode=execution_mode,
            provider_policy=provider_policy,
            tool_policy={"prefer_reliable_tools": True},
            degraded_mode_policy={"max_disabled_providers": 1, "reduce_concurrency_to": 1, "require_low_cost_paths": execution_mode in {"degraded", "low_cost"}},
        )

    def _set_global_execution_mode(self, mode_name: str, reason: str, active_constraints: list[str]) -> GlobalExecutionModeState:
        self.system_mode = mode_name
        mode = GlobalExecutionModeState(
            version="1.0",
            mode_id=f"global-mode-{uuid4().hex[:10]}",
            mode_name=mode_name,
            reason=reason,
            active_constraints=active_constraints,
        )
        self.repository.save_global_execution_mode(mode)
        return mode

    def _current_capacity_snapshot(self) -> CapacitySnapshot:
        active_tasks = len(
            [
                item
                for item in self.repository.list_tasks()
                if item["status"] in {"running", "ready", "replanning", "recovering"}
            ]
        )
        queued_items = self.repository.list_queue_items(statuses=["queued", "deferred", "leased"])
        approval_backlog = len(self.approval_inbox())
        budget_pressure = 0.0
        ledgers = [self.repository.latest_budget_ledger(item["task_id"]) for item in self.repository.list_tasks()]
        valid_ledgers = [ledger for ledger in ledgers if ledger is not None]
        if valid_ledgers:
            budget_pressure = max(0.0, 1.0 - min(ledger.remaining_budget for ledger in valid_ledgers))
        snapshot = CapacitySnapshot(
            version="1.0",
            snapshot_id=f"capacity-snapshot-{uuid4().hex[:10]}",
            active_tasks=active_tasks,
            queued_tasks=len(queued_items),
            provider_capacity_usage={
                policy.provider_name: 0
                if self.repository.load_rate_limit_state(policy.provider_name) is None
                else self.repository.load_rate_limit_state(policy.provider_name).request_count
                for policy in self.repository.list_provider_availability_policies()
            },
            tool_pressure={"file_retrieval": len([item for item in queued_items if item.priority_class == "standard"])},
            approval_backlog=approval_backlog,
            budget_pressure=budget_pressure,
            recovery_reservations=len([item for item in queued_items if item.recovery_required]),
            eval_load=len([item for item in queued_items if item.priority_class == "background_eval"]),
        )
        self.repository.save_capacity_snapshot(snapshot)
        return snapshot

    def _ensure_budget_state(self, task_id: str, request: dict[str, object]) -> None:
        if self.repository.load_budget_policy(task_id) is not None:
            return
        policy, ledger = self.budget_manager.initialize_policy(task_id, dict(request.get("preferences", {})))
        self.repository.save_budget_policy(policy)
        self.repository.save_budget_ledger(ledger)
        if ledger.remaining_budget <= 0.05:
            self._set_execution_mode(
                task_id=task_id,
                mode_name="low_cost",
                reason="budget pressure at task initialization",
                active_constraints=["low remaining budget"],
                deferred_opportunities=["expensive provider paths"],
            )
            self.repository.save_budget_event(
                self.budget_manager.make_event(
                    task_id=task_id,
                    event_type="budget_mode_activated",
                    summary="Low-cost execution mode activated due to budget pressure.",
                    payload={"remaining_budget": ledger.remaining_budget},
                )
            )

    def _set_execution_mode(
        self,
        *,
        task_id: str,
        mode_name: str,
        reason: str,
        active_constraints: list[str],
        deferred_opportunities: list[str],
    ) -> ExecutionModeState:
        state = ExecutionModeState(
            version="1.0",
            mode_id=f"execution-mode-{uuid4().hex[:10]}",
            task_id=task_id,
            mode_name=mode_name,
            reason=reason,
            active_constraints=active_constraints,
            deferred_opportunities=deferred_opportunities,
        )
        self.repository.save_execution_mode(state)
        self.repository.save_governance_event(
            GovernanceEvent(
                version="1.0",
                event_id=f"governance-event-{uuid4().hex[:10]}",
                task_id=task_id,
                event_type="execution_mode_changed",
                summary=reason,
                payload={"mode_name": mode_name, "active_constraints": active_constraints},
            )
        )
        self.repository.save_routing_policy(self._build_routing_policy(mode_name))
        return state

    def _current_execution_mode(self, task_id: str, contract: TaskContract | None = None) -> ExecutionModeState:
        latest = self.repository.latest_execution_mode(task_id)
        if latest is not None:
            return latest
        if task_id in self.execution_mode_overrides:
            return self._set_execution_mode(
                task_id=task_id,
                mode_name=self.execution_mode_overrides[task_id],
                reason="operator override",
                active_constraints=["operator override"],
                deferred_opportunities=[],
            )
        if contract is not None and contract.risk_level == "high":
            return self._set_execution_mode(
                task_id=task_id,
                mode_name="high_risk",
                reason="high-risk contract",
                active_constraints=["risk-sensitive verification"],
                deferred_opportunities=["parallel execution"],
            )
        return self._set_execution_mode(
            task_id=task_id,
            mode_name="standard",
            reason="default execution mode",
            active_constraints=[],
            deferred_opportunities=[],
        )

    def _budget_ledger(self, task_id: str):
        return self.repository.latest_budget_ledger(task_id)

    def _budget_policy(self, task_id: str):
        return self.repository.load_budget_policy(task_id)

    def _estimate_provider_cost(self, provider_name: str, usage: dict[str, int]) -> float:
        total_tokens = int(usage.get("total_tokens", 0))
        rate = 0.00002 if "openai" in provider_name else 0.000008 if "anthropic" in provider_name else 0.000001
        return total_tokens * rate

    def _reserve_provider_slot(self, provider_name: str) -> bool:
        acquired = self.provider_health.try_acquire_capacity(provider_name)
        if not acquired:
            self._set_global_execution_mode("provider_pressure", f"{provider_name} is under rate-limit or cooldown pressure", ["provider health pressure"])
        return acquired

    def _record_provider_success(
        self,
        *,
        provider_name: str,
        latency_ms: float,
        structured_output_ok: bool,
    ) -> None:
        self.provider_health.record_success(
            provider_name,
            latency_ms=latency_ms,
            structured_output_ok=structured_output_ok,
        )

    def _record_provider_failure(
        self,
        *,
        provider_name: str,
        error_code: str,
        latency_ms: float = 0.0,
    ) -> None:
        self.provider_health.record_failure(
            provider_name,
            error_code=error_code,
            latency_ms=latency_ms,
        )

    def _budget_check(self, task_id: str, category: str, estimated_cost: float) -> IncidentReport | None:
        policy = self._budget_policy(task_id)
        ledger = self._budget_ledger(task_id)
        if policy is None or ledger is None:
            return None
        allowed, reason = self.budget_manager.can_spend(
            ledger=ledger,
            policy=policy,
            estimated_cost=estimated_cost,
            category=category,
        )
        if allowed:
            if ledger.remaining_budget <= policy.total_budget * 0.2:
                self._set_execution_mode(
                    task_id=task_id,
                    mode_name="low_cost",
                    reason="budget guardrail prefers lower-cost routing",
                    active_constraints=["budget pressure"],
                    deferred_opportunities=["expensive provider routes"],
                )
            return None
        event = self.budget_manager.make_event(
            task_id=task_id,
            event_type="budget_guardrail_blocked",
            summary=f"Budget blocked {category} spending.",
            payload={"estimated_cost": estimated_cost, "reason": reason},
        )
        self.repository.save_budget_event(event)
        return self.recovery.classify_failure(task_id, "budget_exhausted", f"{category} blocked by budget guardrails")

    def _record_budget_consumption(
        self,
        *,
        task_id: str,
        category: str,
        ref_id: str,
        estimated_cost: float,
        actual_cost: float,
        justification: str,
    ) -> None:
        ledger = self._budget_ledger(task_id)
        if ledger is None:
            return
        updated = self.budget_manager.consume(ledger=ledger, category=category, actual_cost=actual_cost)
        self.repository.save_budget_ledger(updated)
        self.repository.save_budget_consumption_record(
            self.budget_manager.make_consumption_record(
                task_id=task_id,
                category=category,
                ref_id=ref_id,
                estimated_cost=estimated_cost,
                actual_cost=actual_cost,
                justification=justification,
            )
        )

    def _tool_scorecard_views(self) -> list[ToolScorecardView]:
        views: list[ToolScorecardView] = []
        for item in self.repository.list_tool_scorecards():
            reliability = 1.0 if item.total_invocations == 0 else item.successes / item.total_invocations
            views.append(
                ToolScorecardView(
                    tool_name=item.tool_name,
                    variant=item.variant,
                    reliability=reliability,
                    average_latency_ms=item.average_latency_ms,
                    evidence_usefulness=item.evidence_usefulness,
                    cost_impact=item.cost_impact,
                    approval_friction=float(item.safety_incidents),
                )
            )
        return views

    def _route_provider(
        self,
        *,
        task_id: str,
        plan_node_id: str,
        role: str,
        workload: str,
        risk_level: str,
        requires_structured_output: bool,
        base_route,
    ):
        mode = self._current_execution_mode(task_id)
        ledger = self._budget_ledger(task_id)
        policy = self._build_routing_policy(mode.mode_name)
        health_snapshot = self.provider_health.snapshot(list(self.provider_manager.providers))
        self.repository.save_provider_health_snapshot(health_snapshot)
        available_providers = {
            record.provider_name
            for record in health_snapshot.records
            if record.availability_state == "available" and not record.operator_disabled and record.circuit_state != "open"
        }
        capabilities = {
            item.provider_name: item
            for item in self.repository.list_provider_capabilities()
            if item.provider_name not in self.disabled_providers and (not available_providers or item.provider_name in available_providers)
        }
        if not capabilities:
            self._ensure_provider_registration()
            capabilities = {
                item.provider_name: item
                for item in self.repository.list_provider_capabilities()
                if item.provider_name not in self.disabled_providers and (not available_providers or item.provider_name in available_providers)
            }
        if not capabilities:
            self._set_global_execution_mode("provider_pressure", "no compatible providers are currently available", ["provider saturation"])
        provider_scorecards = {
            item.provider_name: item
            for item in self.repository.list_provider_scorecards()
            if item.profile == base_route.profile or not base_route.profile
        }
        tool_scorecards = {item.tool_name: item for item in self._tool_scorecard_views()}
        decision = policy.select_provider(
            context=RoutingContext(
                role=role,
                workload=workload,
                risk_level=risk_level,
                requires_structured_output=requires_structured_output,
                execution_mode=mode.mode_name,
                budget_remaining=0.0 if ledger is None else ledger.remaining_budget,
                role_budget_remaining=0.0 if ledger is None else ledger.remaining_budget,
                degraded_mode_active=mode.mode_name == "degraded",
            ),
            capabilities=capabilities,
            provider_scorecards=provider_scorecards,
            tool_scorecards=tool_scorecards,
        )
        decision.decision_id = f"routing-decision-{uuid4().hex[:10]}"
        decision.task_id = task_id
        decision.plan_node_id = plan_node_id
        if not decision.chosen_provider:
            decision.chosen_provider = next(
                (
                    provider_name
                    for provider_name in (base_route.provider_order or list(self.provider_manager.providers))
                    if provider_name in self.provider_manager.providers and provider_name not in self.disabled_providers
                ),
                "",
            )
        balance = self.provider_pool.balance(
            candidate_providers=list(capabilities.keys()) if capabilities else list(self.provider_manager.providers),
            task_id=task_id,
            worker_id="inline-runtime" if self._active_dispatch_context is None else self._active_dispatch_context["worker_id"],
            workload=workload,
            risk_level=risk_level,
        )
        if balance.chosen_provider:
            self.capacity_forecaster.record_provider_demand(
                provider_name=balance.chosen_provider,
                role=role.lower(),
                observed_demand=len([item for item in self.repository.list_provider_reservations(balance.chosen_provider) if item.status == "active"]),
                projected_demand=max(1, len([item for item in self.repository.list_queue_items(statuses=["queued", "deferred"])])),
                fallback_pressure=0.2 if mode.mode_name == "degraded" else 0.0,
                reservation_pressure=0.7 if workload in {"verification", "recovery"} else 0.3,
            )
            quota_decision = self.quota_governor.evaluate_request(
                provider_name=balance.chosen_provider,
                task_id=task_id,
                role=role.lower(),
                workload=workload,
                priority_class="high" if risk_level in {"high", "critical"} else "standard",
                requested_units=1,
            )
            if quota_decision.allowed:
                decision.chosen_provider = balance.chosen_provider
            else:
                alternative_candidates = list(capabilities.keys()) if capabilities else list(self.provider_manager.providers)
                alternative = next(
                    (
                        provider_name
                        for provider_name in alternative_candidates
                        if provider_name != balance.chosen_provider
                        and self.quota_governor.evaluate_request(
                            provider_name=provider_name,
                            task_id=task_id,
                            role=role.lower(),
                            workload=workload,
                            priority_class="high" if risk_level in {"high", "critical"} else "standard",
                            requested_units=1,
                        ).allowed
                    ),
                    "",
                )
                decision.chosen_provider = alternative
            if workload in {"verification", "recovery"}:
                existing_reservations = [
                    item
                    for item in self.repository.list_provider_reservations(balance.chosen_provider)
                    if item.task_id == task_id and item.reservation_type == workload and item.status == "active"
                ]
                if not existing_reservations:
                    self.provider_pool.reserve(
                        provider_name=balance.chosen_provider,
                        reservation_type=workload,
                        task_id=task_id,
                        worker_id="inline-runtime" if self._active_dispatch_context is None else self._active_dispatch_context["worker_id"],
                        expires_at=utc_now() + timedelta(minutes=5),
                        host_id=None if self._active_dispatch_context is None else self.repository.load_worker(self._active_dispatch_context["worker_id"]).host_id if self.repository.load_worker(self._active_dispatch_context["worker_id"]) is not None else "",
                    )
        if balance.delayed and not decision.chosen_provider:
            self._set_global_execution_mode(
                "provider_pressure",
                "provider pool balancing delayed routing under sustained load",
                ["provider pool reservation pressure"],
            )
        self.repository.save_routing_decision(decision)
        base_route.provider_order = [decision.chosen_provider] + [
            name for name in self.provider_manager.providers if name != decision.chosen_provider and name not in self.disabled_providers
        ]
        if decision.chosen_provider.startswith("openai"):
            base_route.model_name = "gpt-4.1-mini"
        elif decision.chosen_provider.startswith("anthropic"):
            base_route.model_name = "claude-sonnet-test" if "test" in decision.chosen_provider else "claude-sonnet-4-20250514"
        return base_route, decision

    def _select_tool_variant(self, *, task_id: str, plan_node_id: str, tool_name: str) -> RoutingPolicy:
        mode = self._current_execution_mode(task_id)
        policy = self._build_routing_policy(mode.mode_name)
        candidates = [item for item in self._tool_scorecard_views() if item.tool_name == tool_name]
        if not candidates:
            candidates = [ToolScorecardView(tool_name=tool_name, variant="live", reliability=1.0, evidence_usefulness=0.8)]
        decision = policy.select_tool(
            context=RoutingContext(role="Researcher", workload="retrieval", risk_level="low", execution_mode=mode.mode_name, budget_remaining=0.0 if self._budget_ledger(task_id) is None else self._budget_ledger(task_id).remaining_budget),
            tool_name=tool_name,
            candidates=candidates,
        )
        decision.decision_id = f"routing-decision-{uuid4().hex[:10]}"
        decision.task_id = task_id
        decision.plan_node_id = plan_node_id
        self.repository.save_routing_decision(decision)
        return policy

    def execute_plan(
        self,
        task_id: str,
        contract: TaskContract,
        plan: PlanGraph,
        lattice: ContractLattice,
        attachments: list[str],
        evidence: EvidenceBuilder,
        interrupt_after: str | None = None,
    ) -> IncidentReport | None:
        successful_nodes = {
            receipt.plan_node_id
            for receipt in self.repository.list_execution_receipts(task_id)
            if receipt.status == "success"
        }
        for node in plan.nodes:
            if node.node_id in successful_nodes and node.status != "completed":
                self._mark_node_completed(task_id, node)
        while True:
            self._assert_active_dispatch_ownership()
            plan = self.repository.load_plan(task_id) or plan
            self._release_approved_nodes(task_id, plan)
            ready_nodes = self._ready_nodes(plan)
            if all(node.status == "completed" for node in plan.nodes):
                self._save_scheduler_state(task_id, plan, status="completed")
                self._save_concurrency_state(task_id, active_nodes=[], last_batch_nodes=[])
                return None
            if not ready_nodes:
                scheduler_status = "waiting_for_approval" if any(node.status == "blocked" for node in plan.nodes) else "blocked"
                self._save_scheduler_state(task_id, plan, status=scheduler_status)
                self._save_concurrency_state(task_id, active_nodes=[], last_batch_nodes=[])
                return None

            batch = self._select_ready_batch(task_id, contract, ready_nodes)
            self._save_scheduler_state(task_id, plan, status="running", running_node_id=batch[0].node_id if len(batch) == 1 else None)
            self._save_concurrency_state(task_id, active_nodes=[node.node_id for node in batch], last_batch_nodes=[node.node_id for node in batch])
            request = self.repository.get_task(task_id)["request"]
            self._persist_task_state(
                task_id=task_id,
                status="running",
                current_phase="running_batch" if len(batch) > 1 else batch[0].node_id,
                request=request,
                contract_id=contract.contract_id,
                plan_graph_id=plan.graph_id,
                latest_checkpoint_id=self.repository.get_task(task_id)["latest_checkpoint_id"],
                result=self.repository.get_task(task_id)["result"],
            )
            approval_incident = None
            for node in batch:
                approval_incident = self._approval_wait_if_needed(task_id, contract, node, evidence, plan, lattice)
                if approval_incident is not None:
                    break
            if approval_incident is not None:
                self._save_scheduler_state(task_id, plan, status="waiting_for_approval")
                self._save_concurrency_state(task_id, active_nodes=[], last_batch_nodes=[node.node_id for node in batch])
                return approval_incident
            incidents = self._execute_batch(task_id, contract, batch, attachments, evidence)
            if incidents:
                failed_node, incident = incidents[0]
                if incident.incident_type in {"provider_error", "tool_failure", "verification_failure", "evidence_inconsistency"} and failed_node.node_category != "recovery":
                    plan = self._replan_after_failure(task_id, contract, plan, failed_node, incident)
                    self._save_scheduler_state(task_id, plan, status="replanning")
                    self._save_concurrency_state(task_id, active_nodes=[], last_batch_nodes=[node.node_id for node in batch])
                    continue
                failed_node.status = "failed"
                self.repository.update_plan_node_status(task_id, failed_node.node_id, "failed")
                self._save_scheduler_state(task_id, plan, status="failed")
                self._save_concurrency_state(task_id, active_nodes=[], last_batch_nodes=[node.node_id for node in batch])
                return incident
            plan = self.repository.load_plan(task_id) or plan
            last_batch_node = batch[-1].node_id
            after_checkpoint = self.checkpoint_task(
                task_id,
                last_batch_node,
                {
                    "phase": "after_node_execute",
                    "node_ids": [node.node_id for node in batch],
                    "next_nodes": [candidate.node_id for candidate in plan.nodes if candidate.status != "completed"],
                },
            )
            self._persist_task_state(
                task_id=task_id,
                status="ready",
                current_phase="ready",
                request=request,
                contract_id=contract.contract_id,
                plan_graph_id=plan.graph_id,
                latest_checkpoint_id=after_checkpoint.checkpoint_id,
                result=self.repository.get_task(task_id)["result"],
            )
            if interrupt_after == "after_node_execute":
                self._refresh_long_horizon_state(
                    task_id=task_id,
                    contract=contract,
                    plan=plan,
                    lattice=lattice,
                    evidence=evidence,
                    checkpoint_id=after_checkpoint.checkpoint_id,
                )
            self._save_scheduler_state(task_id, plan, status="ready")
            self._save_concurrency_state(task_id, active_nodes=[], last_batch_nodes=[node.node_id for node in batch])
            self._interrupt_if_requested(task_id, interrupt_after, "after_node_execute")
        return None

    def _ready_nodes(self, plan: PlanGraph) -> list[PlanNode]:
        completed = {node.node_id for node in plan.nodes if node.status == "completed"}
        ready = [
            node
            for node in plan.nodes
            if node.status == "pending"
            and node.branch_id == plan.active_branch_id
            and all(dependency in completed for dependency in node.dependencies)
        ]
        return sorted(ready, key=lambda node: (node.priority, node.budget_cost, node.node_id))

    def _select_ready_batch(self, task_id: str, contract: TaskContract, ready_nodes: list[PlanNode]) -> list[PlanNode]:
        mode = self._current_execution_mode(task_id, contract)
        max_parallel = self.concurrency_caps.get(task_id, 2)
        if mode.mode_name in {"high_risk", "verification_heavy", "degraded"}:
            max_parallel = 1
        if max_parallel <= 1:
            return [ready_nodes[0]]
        first = ready_nodes[0]
        if first.approval_gate is not None or first.node_category in {"build", "verification", "memory_evolution", "recovery"}:
            return [first]
        batch = [first]
        for node in ready_nodes[1:]:
            if len(batch) >= max_parallel:
                break
            if node.approval_gate is not None:
                continue
            if node.role_owner != first.role_owner or node.node_category != first.node_category:
                continue
            batch.append(node)
        return batch

    def _execute_batch(
        self,
        task_id: str,
        contract: TaskContract,
        batch: list[PlanNode],
        attachments: list[str],
        evidence: EvidenceBuilder,
    ) -> list[tuple[PlanNode, IncidentReport]]:
        if len(batch) == 1:
            incident = self.execute_node(task_id, contract, batch[0], attachments, evidence)
            return [] if incident is None else [(batch[0], incident)]
        incidents: list[tuple[PlanNode, IncidentReport]] = []
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            futures = {
                executor.submit(self.execute_node, task_id, contract, node, attachments, evidence): node
                for node in batch
            }
            for future in as_completed(futures):
                node = futures[future]
                incident = future.result()
                if incident is not None:
                    incidents.append((node, incident))
        return incidents

    def _release_approved_nodes(self, task_id: str, plan: PlanGraph) -> None:
        approvals = self.repository.list_approval_requests(task_id=task_id)
        approved_nodes = {request.plan_node_id for request in approvals if request.status == "approved" and request.plan_node_id}
        for node in plan.nodes:
            if node.node_id in approved_nodes and node.status == "blocked":
                node.status = "pending"
                self.repository.update_plan_node_status(task_id, node.node_id, "pending")

    def _save_scheduler_state(
        self,
        task_id: str,
        plan: PlanGraph,
        *,
        status: str,
        running_node_id: str | None = None,
    ) -> SchedulerState:
        ready = [node.node_id for node in self._ready_nodes(plan)]
        state = SchedulerState(
            version="1.0",
            scheduler_id=f"scheduler-{uuid4().hex[:10]}",
            task_id=task_id,
            plan_graph_id=plan.graph_id,
            active_branch_id=plan.active_branch_id,
            ready_queue=ready,
            running_nodes=[] if running_node_id is None else [running_node_id],
            blocked_nodes=[node.node_id for node in plan.nodes if node.status == "blocked"],
            completed_nodes=[node.node_id for node in plan.nodes if node.status == "completed"],
            failed_nodes=[node.node_id for node in plan.nodes if node.status == "failed"],
            deferred_nodes=[
                node.node_id
                for node in plan.nodes
                if node.status == "pending" and node.node_id not in ready and node.branch_id != plan.active_branch_id
            ],
            status=status,
            updated_at=utc_now(),
        )
        self.repository.save_scheduler_state(state)
        return state

    def _save_concurrency_state(
        self,
        task_id: str,
        *,
        active_nodes: list[str],
        last_batch_nodes: list[str],
    ) -> ConcurrencyState:
        mode = self._current_execution_mode(task_id)
        max_parallel_nodes = self.concurrency_caps.get(task_id, 2)
        if mode.mode_name in {"high_risk", "verification_heavy", "degraded"}:
            max_parallel_nodes = 1
        state = ConcurrencyState(
            version="1.0",
            concurrency_id=f"concurrency-{uuid4().hex[:10]}",
            task_id=task_id,
            max_parallel_nodes=max_parallel_nodes,
            role_limits={"Researcher": max_parallel_nodes, "Builder": 1, "Verifier": 1},
            provider_limits={provider_name: 2 for provider_name in self.provider_manager.providers},
            tool_limits={"file_retrieval": max_parallel_nodes},
            active_nodes=active_nodes,
            last_batch_nodes=last_batch_nodes,
            backpressure_active=len(active_nodes) >= max_parallel_nodes,
        )
        self.repository.save_concurrency_state(state)
        return state

    def _replan_after_failure(
        self,
        task_id: str,
        contract: TaskContract,
        plan: PlanGraph,
        failed_node: PlanNode,
        incident: IncidentReport,
    ) -> PlanGraph:
        recovery_branch_id = f"branch-recovery-{uuid4().hex[:6]}"
        revised = self.planner.replan_local(
            plan,
            failed_node_id=failed_node.node_id,
            fallback_objective=f"Recover from {failed_node.objective} after {incident.incident_type}",
            recovery_branch_id=recovery_branch_id,
        )
        revision = PlanRevision(
            version="1.0",
            revision_id=f"revision-{uuid4().hex[:10]}",
            task_id=task_id,
            plan_graph_id=revised.graph_id,
            cause=incident.incident_type,
            affected_nodes=[failed_node.node_id],
            inserted_nodes=[f"{failed_node.node_id}-recovery"],
            superseded_nodes=[failed_node.node_id],
            contract_id=contract.contract_id,
            evidence_refs=[],
            approval_refs=[],
            branch_id=recovery_branch_id,
            created_at=utc_now(),
        )
        for branch in self.repository.list_execution_branches(task_id):
            if branch.selected:
                branch.selected = False
                branch.status = "rejected"
                self.repository.save_execution_branch(branch)
        recovery_branch = ExecutionBranch(
            version="1.0",
            branch_id=recovery_branch_id,
            task_id=task_id,
            plan_graph_id=revised.graph_id,
            parent_branch_id=plan.active_branch_id,
            label=f"Recovery for {failed_node.node_id}",
            status="selected",
            selected=True,
            cause=incident.summary,
            node_ids=[node.node_id for node in revised.nodes if node.branch_id == recovery_branch_id],
            created_at=utc_now(),
        )
        self.repository.save_plan(task_id, revised)
        self.repository.save_plan_revision(revision)
        self.repository.save_execution_branch(recovery_branch)
        self.recovery.mark_failure_context(incident.incident_id, "replanned_with_recovery_branch")
        task = self.repository.get_task(task_id)
        if task is not None:
            self._persist_task_state(
                task_id=task_id,
                status="replanning",
                current_phase="replanning",
                request=task["request"],
                contract_id=contract.contract_id,
                plan_graph_id=revised.graph_id,
                latest_checkpoint_id=task["latest_checkpoint_id"],
                result=task["result"],
            )
        self._audit_event(
            task_id=task_id,
            contract_id=contract.contract_id,
            event_type="plan_revised",
            actor="Strategist",
            why=incident.summary,
            risk_level=contract.risk_level,
            result="replanned",
        )
        self._emit_telemetry(
            task_id,
            "plan_replanned",
            {"failed_node_id": failed_node.node_id, "recovery_branch_id": recovery_branch_id, "incident_id": incident.incident_id},
        )
        return revised

    def validate_result(
        self,
        task_id: str,
        contract: TaskContract,
        evidence: EvidenceBuilder,
        delivery: dict[str, object],
    ) -> ValidationReport:
        base_route = self.model_router.route(
            role="Verifier",
            workload="verification",
            risk_level=contract.risk_level,
            strategy_name=self.routing_strategy,
        )
        route, routing_decision = self._route_provider(
            task_id=task_id,
            plan_node_id="node-validate-result",
            role="Verifier",
            workload="verification",
            risk_level=contract.risk_level,
            requires_structured_output=False,
            base_route=base_route,
        )
        if routing_decision.chosen_provider and not self._reserve_provider_slot(routing_decision.chosen_provider):
            report = ValidationReport(
                version="1.0",
                report_id=f"validation-{uuid4().hex[:10]}",
                contract_id=contract.contract_id,
                validator="ShadowVerifier",
                status="blocked",
                confidence=0.0,
                findings=[f"{routing_decision.chosen_provider} unavailable for verification"],
                contradictions=[],
                evidence_refs=[],
            )
            self.repository.save_validation_report(task_id, report)
            return report
        provider_request = ProviderRequest(
            version="1.0",
            request_id=f"provider-request-{uuid4().hex[:10]}",
            task_id=task_id,
            role="Verifier",
            workload="verification",
            prompt="Verify that all facts remain evidence-bound.",
            input_payload={"facts": delivery["facts"]},
            correlation_id=f"{task_id}:node-validate-result:provider",
            created_at=utc_now(),
        )
        try:
            provider_response, routing_receipt = self.provider_manager.complete(route=route, request=provider_request)
        except ProviderError as exc:
            if routing_decision.chosen_provider:
                self._record_provider_failure(provider_name=routing_decision.chosen_provider, error_code=exc.code)
            report = ValidationReport(
                version="1.0",
                report_id=f"validation-{uuid4().hex[:10]}",
                contract_id=contract.contract_id,
                validator="ShadowVerifier",
                status="blocked",
                confidence=0.0,
                findings=[str(exc)],
                contradictions=[],
                evidence_refs=[],
            )
            self.repository.save_validation_report(task_id, report)
            return report
        self._record_provider_success(
            provider_name=provider_response.provider_name,
            latency_ms=provider_response.latency_ms,
            structured_output_ok=True,
        )
        self.repository.save_routing_receipt(task_id, routing_receipt)
        self.repository.save_provider_usage_record(
            self.provider_manager.build_usage_record(
                provider_request,
                route,
                provider_response,
                routing_receipt,
                estimated_cost=self._estimate_provider_cost(provider_response.provider_name, provider_response.usage),
            )
        )
        self._audit_event(
            task_id=task_id,
            contract_id=contract.contract_id,
            event_type="model_routing",
            actor="Verifier",
            why=f"{route.strategy_name}:{route.profile}",
            risk_level=contract.risk_level,
            result="success",
            tool_refs=[routing_receipt.provider_name],
        )
        report = self.verifier.verify(
            contract=contract,
            evidence_graph=evidence.graph,
            delivery_claims=delivery["facts"],
        )
        self.repository.save_validation_report(task_id, report)
        return report

    def checkpoint_task(
        self,
        task_id: str,
        plan_node_id: str,
        state: dict[str, object],
    ):
        record = self.recovery.save_checkpoint(task_id=task_id, plan_node_id=plan_node_id, state=state)
        return record

    def recover_task(self, checkpoint_id: str) -> dict[str, object]:
        return self.recovery.restore_checkpoint(checkpoint_id)

    def audit_query(
        self,
        task_id: str | None = None,
        event_type: str | None = None,
        actor: str | None = None,
        tool_ref: str | None = None,
        risk_level: str | None = None,
    ) -> list[AuditEvent]:
        return self.audit.query(
            task_id=task_id,
            event_type=event_type,
            actor=actor,
            tool_ref=tool_ref,
            risk_level=risk_level,
        )

    def query_audit(
        self,
        task_id: str | None = None,
        event_type: str | None = None,
        actor: str | None = None,
        tool_ref: str | None = None,
        risk_level: str | None = None,
    ) -> list[AuditEvent]:
        return self.audit_query(
            task_id=task_id,
            event_type=event_type,
            actor=actor,
            tool_ref=tool_ref,
            risk_level=risk_level,
        )

    def memory_query(self, memory_type: str | None = None, state: str | None = None):
        return self.memory.query(memory_type=memory_type, state=state)

    def memory_dashboard(self, scope_key: str):
        return self.memory.dashboard(scope_key=scope_key)

    def memory_evidence_pack(self, *, query: str, scope_key: str, at_time: datetime | None = None):
        return self.memory.retrieve_evidence_pack(query=query, scope_key=scope_key, at_time=at_time)

    def memory_kernel_state(self, *, scope_key: str) -> dict[str, object]:
        return {
            "task_id": scope_key,
            "write_receipts": [item.to_dict() for item in self.memory.list_memory_write_receipts(scope_key=scope_key)],
            "evidence_packs": [item.to_dict() for item in self.repository.list_memory_evidence_packs(scope_key)],
            "deletion_receipts": [item.to_dict() for item in self.memory.list_memory_deletion_receipts(scope_key=scope_key)],
            "consolidation_policy": self.memory.consolidation_policy(scope_key=scope_key).to_dict(),
            "repair_policy": self.memory.repair_policy(scope_key=scope_key).to_dict(),
            "timeline_view": self.memory.timeline_view(scope_key=scope_key).to_dict(),
            "project_state_view": self.memory.project_state_view(scope_key=scope_key).to_dict(),
            "software_procedures": [item.to_dict() for item in self.memory.list_memory_software_procedures(scope_key=scope_key)],
        }

    def raw_episodes(self, *, task_id: str | None = None, scope_key: str | None = None):
        return self.memory.list_raw_episodes(task_id=task_id, scope_key=scope_key)

    def temporal_semantic_facts(self, *, scope_key: str | None = None, task_id: str | None = None):
        return self.memory.list_temporal_semantic_facts(scope_key=scope_key, task_id=task_id)

    def memory_tombstones(self, *, scope_key: str | None = None):
        return self.memory.list_memory_tombstones(scope_key=scope_key)

    def consolidate_memory_scope(self, *, scope_key: str, reason: str):
        return self.memory.run_sleep_consolidation(scope_key=scope_key, reason=reason)

    def rebuild_memory_scope(self, *, scope_key: str, reason: str):
        return self.memory.rebuild_indexes(scope_key=scope_key, reason=reason)

    def delete_memory_scope(self, *, scope_key: str, actor: str, reason: str):
        return self.memory.tombstone_scope(scope_key=scope_key, actor=actor, reason=reason)

    def selective_purge_memory_scope(
        self,
        *,
        scope_key: str,
        actor: str,
        reason: str,
        target_kinds: list[str],
    ):
        return self.memory.selective_purge_scope(
            scope_key=scope_key,
            actor=actor,
            reason=reason,
            target_kinds=target_kinds,
        )

    def hard_purge_memory_scope(
        self,
        *,
        scope_key: str,
        actor: str,
        reason: str,
        target_kinds: list[str] | None = None,
    ):
        return self.memory.hard_purge_scope(
            scope_key=scope_key,
            actor=actor,
            reason=reason,
            target_kinds=target_kinds,
        )

    def memory_timeline(
        self,
        *,
        scope_key: str,
        subject: str | None = None,
        predicate: str | None = None,
    ):
        return self.memory.reconstruct_timeline(
            scope_key=scope_key,
            subject=subject,
            predicate=predicate,
        )

    def cross_scope_memory_timeline(
        self,
        *,
        scope_keys: list[str],
        subject: str,
        predicate: str,
    ):
        return self.memory.reconstruct_cross_scope_timeline(
            scope_keys=scope_keys,
            subject=subject,
            predicate=predicate,
        )

    def memory_project_state(
        self,
        *,
        scope_key: str,
        subject: str = "user",
    ):
        return self.memory.reconstruct_project_state(
            scope_key=scope_key,
            subject=subject,
        )

    def memory_artifacts(self, *, scope_key: str, artifact_kind: str | None = None):
        return self.memory.list_memory_artifacts(scope_key=scope_key, artifact_kind=artifact_kind)

    def memory_artifact_health(self, *, scope_key: str):
        return self.memory.artifact_backend_health(scope_key=scope_key)

    def memory_maintenance_drift(self, *, scope_key: str):
        return self.memory.scan_artifact_drift(scope_key=scope_key)

    def memory_maintenance_incidents(self, *, scope_key: str):
        return self.memory.list_memory_maintenance_incidents(scope_key=scope_key)

    def memory_maintenance_mode(self, *, scope_key: str):
        return self.memory.maintenance_mode(scope_key=scope_key)

    def memory_maintenance_workers(self):
        return self.memory.list_memory_maintenance_workers()

    def register_maintenance_worker(
        self,
        *,
        worker_id: str,
        host_id: str,
        actor: str,
    ):
        return self.memory.register_maintenance_worker(
            worker_id=worker_id,
            host_id=host_id,
            actor=actor,
        )

    def run_maintenance_worker_cycle(
        self,
        *,
        worker_id: str,
        at_time: datetime | None = None,
        interrupt_after: str | None = None,
        lease_seconds: int = 300,
    ):
        return self.memory.run_maintenance_worker_cycle(
            worker_id=worker_id,
            at_time=at_time,
            interrupt_after_phase=interrupt_after,
            lease_seconds=lease_seconds,
        )

    def resolve_maintenance_incident(
        self,
        *,
        incident_id: str,
        actor: str,
        resolution: str,
    ):
        incident = self.memory.resolve_maintenance_incident(
            incident_id=incident_id,
            actor=actor,
            resolution=resolution,
        )
        self.repository.save_maintenance_resolution_analytics(
            MaintenanceResolutionAnalytics(
                version="1.0",
                resolution_id=f"maintenance-resolution-{uuid4().hex[:10]}",
                scope_key=incident.scope_key,
                incident_id=incident_id,
                actor=actor,
                resolution=resolution,
                restored_mode="normal",
                created_at=utc_now(),
            )
        )
        return incident

    def selective_rebuild_memory_scope(
        self,
        *,
        scope_key: str,
        reason: str,
        target_kinds: list[str],
    ):
        return self.memory.selective_rebuild_scope(
            scope_key=scope_key,
            reason=reason,
            target_kinds=target_kinds,
        )

    def memory_operations_loop(
        self,
        *,
        scope_key: str,
        reason: str,
        interrupt_after: str | None = None,
    ):
        return self.memory.run_memory_operations_loop(
            scope_key=scope_key,
            reason=reason,
            interrupt_after_phase=interrupt_after,
        )

    def schedule_memory_operations_loop(
        self,
        *,
        scope_key: str,
        cadence_hours: int,
        actor: str,
        start_at: datetime | None = None,
    ):
        return self.memory.schedule_memory_operations_loop(
            scope_key=scope_key,
            cadence_hours=cadence_hours,
            actor=actor,
            start_at=start_at,
        )

    def resume_memory_operations_loop(
        self,
        *,
        loop_run_id: str,
        actor: str,
        reason: str,
    ):
        return self.memory.resume_memory_operations_loop(
            loop_run_id=loop_run_id,
            actor=actor,
            reason=reason,
        )

    def memory_operations_diagnostics(self, *, scope_key: str):
        return self.memory.memory_operations_diagnostics(scope_key=scope_key)

    def memory_maintenance_recommendation(self, *, scope_key: str):
        return self.memory.recommend_memory_maintenance(scope_key=scope_key)

    def background_memory_maintenance(
        self,
        *,
        scope_keys: list[str] | None = None,
        actor: str,
        at_time: datetime | None = None,
    ):
        return self.memory.run_background_memory_maintenance(
            scope_keys=scope_keys,
            actor=actor,
            at_time=at_time,
        )

    def schedule_background_maintenance(
        self,
        *,
        scope_key: str,
        cadence_hours: int,
        actor: str,
        start_at: datetime | None = None,
    ):
        return self.memory.schedule_background_maintenance(
            scope_key=scope_key,
            cadence_hours=cadence_hours,
            actor=actor,
            start_at=start_at,
        )

    def run_due_background_maintenance(
        self,
        *,
        at_time: datetime | None = None,
        interrupt_after: str | None = None,
        worker_id: str | None = None,
    ):
        return self.memory.run_due_background_maintenance(
            at_time=at_time,
            interrupt_after_phase=interrupt_after,
            worker_id=worker_id,
        )

    def resume_background_maintenance(
        self,
        *,
        run_id: str,
        actor: str,
        reason: str,
        worker_id: str | None = None,
    ):
        return self.memory.resume_background_maintenance(
            run_id=run_id,
            actor=actor,
            reason=reason,
            worker_id=worker_id,
        )

    def memory_maintenance_canary(self, *, scope_key: str):
        return self.memory.run_maintenance_recommendation_canary(scope_key=scope_key)

    def memory_maintenance_promotions(self, *, scope_key: str):
        return self.memory.list_memory_maintenance_promotions(scope_key=scope_key)

    def memory_maintenance_rollouts(self, *, scope_key: str):
        return self.memory.list_memory_maintenance_rollouts(scope_key=scope_key)

    def apply_maintenance_promotion(
        self,
        *,
        scope_key: str,
        recommendation_id: str,
        actor: str,
        reason: str,
    ):
        return self.memory.apply_maintenance_promotion(
            scope_key=scope_key,
            recommendation_id=recommendation_id,
            actor=actor,
            reason=reason,
        )

    def rollback_maintenance_rollout(
        self,
        *,
        rollout_id: str,
        actor: str,
        reason: str,
    ):
        return self.memory.rollback_maintenance_rollout(
            rollout_id=rollout_id,
            actor=actor,
            reason=reason,
        )

    def memory_contradiction_repairs(
        self,
        *,
        scope_keys: list[str],
        subject: str,
        predicate: str,
    ):
        return self.memory.repair_cross_scope_contradictions(
            scope_keys=scope_keys,
            subject=subject,
            predicate=predicate,
        )

    def memory_repair_canary(
        self,
        *,
        scope_keys: list[str],
        subject: str,
        predicate: str,
    ):
        return self.memory.run_contradiction_repair_canary(
            scope_keys=scope_keys,
            subject=subject,
            predicate=predicate,
        )

    def apply_memory_repair(
        self,
        *,
        repair_id: str,
        actor: str,
        reason: str,
    ):
        return self.memory.apply_contradiction_repair(repair_id=repair_id, actor=actor, reason=reason)

    def rollback_memory_repair(
        self,
        *,
        repair_id: str,
        actor: str,
        reason: str,
    ):
        return self.memory.rollback_contradiction_repair(repair_id=repair_id, actor=actor, reason=reason)

    def memory_admission_canary(
        self,
        *,
        scope_key: str,
        candidate_ids: list[str],
    ):
        return self.memory.run_admission_controller_canary(
            scope_key=scope_key,
            candidate_ids=candidate_ids,
        )

    def memory_admission_promotions(self, *, scope_key: str):
        return self.memory.list_admission_promotion_recommendations(scope_key=scope_key)

    def memory_policy_state(self, *, scope_key: str):
        return {
            "scope_key": scope_key,
            "admission_policy": None
            if self.memory._load_admission_policy(scope_key) is None
            else self.memory._load_admission_policy(scope_key).to_dict(),
            "learning_state": None
            if self.memory._load_admission_learning_state(scope_key) is None
            else self.memory._load_admission_learning_state(scope_key).to_dict(),
            "quarantined_candidates": [item.to_dict() for item in self.memory.list_quarantined_candidates(scope_key=scope_key)],
            "lifecycle_traces": [item.to_dict() for item in self.memory.list_memory_lifecycle_traces(scope_key=scope_key)],
            "feature_scores": [item.to_dict() for item in self.memory.list_admission_feature_scores(scope_key=scope_key)],
            "purge_manifests": [item.to_dict() for item in self.memory.list_memory_purge_manifests(scope_key=scope_key)],
            "project_state_snapshots": [item.to_dict() for item in self.memory.list_project_state_snapshots(scope_key=scope_key)],
            "artifacts": [item.to_dict() for item in self.memory.list_memory_artifacts(scope_key=scope_key)],
            "admission_canary_runs": [item.to_dict() for item in self.memory.list_admission_canary_runs(scope_key=scope_key)],
            "repair_canary_runs": [
                item.to_dict()
                for item in self.memory.list_repair_canary_runs()
                if scope_key in item.scope_keys
            ],
            "repair_learning_states": [
                item.to_dict()
                for item in self.memory.list_repair_learning_states()
                if scope_key in item.scope_keys
            ],
            "repair_action_runs": [
                item.to_dict()
                for item in self.memory.list_repair_action_runs()
                if any(scope_key in repair.scope_keys for repair in [self.memory._get_contradiction_repair(item.repair_id)])
            ],
            "selective_rebuild_runs": [item.to_dict() for item in self.memory.list_selective_rebuild_runs(scope_key=scope_key)],
            "operations_loop_runs": [item.to_dict() for item in self.memory.list_memory_operations_loop_runs(scope_key=scope_key)],
            "operations_loop_schedules": [item.to_dict() for item in self.memory.list_memory_operations_loop_schedules(scope_key=scope_key)],
            "operations_recoveries": [item.to_dict() for item in self.memory.list_memory_operations_loop_recoveries(scope_key=scope_key)],
            "operations_diagnostics": [item.to_dict() for item in self.memory.list_memory_operations_diagnostics(scope_key=scope_key)],
            "artifact_backend_health": [item.to_dict() for item in self.memory.list_memory_artifact_backend_health(scope_key=scope_key)],
            "artifact_backend_repairs": [item.to_dict() for item in self.memory.list_memory_artifact_backend_repairs(scope_key=scope_key)],
            "artifact_drift": [item.to_dict() for item in self.memory.list_memory_artifact_drift(scope_key=scope_key)],
            "maintenance_recommendations": [item.to_dict() for item in self.memory.list_memory_maintenance_recommendations(scope_key=scope_key)],
            "maintenance_runs": [item.to_dict() for item in self.memory.list_memory_maintenance_runs(scope_key=scope_key)],
            "maintenance_learning_states": [item.to_dict() for item in self.memory.list_memory_maintenance_learning_states(scope_key=scope_key)],
            "maintenance_canary_runs": [item.to_dict() for item in self.memory.list_memory_maintenance_canary_runs(scope_key=scope_key)],
            "maintenance_promotion_recommendations": [item.to_dict() for item in self.memory.list_memory_maintenance_promotions(scope_key=scope_key)],
            "maintenance_schedules": [item.to_dict() for item in self.memory.list_memory_maintenance_schedules(scope_key=scope_key)],
            "maintenance_recoveries": [item.to_dict() for item in self.memory.list_memory_maintenance_recoveries(scope_key=scope_key)],
            "maintenance_analytics": [item.to_dict() for item in self.memory.list_memory_maintenance_analytics(scope_key=scope_key)],
            "maintenance_incidents": [item.to_dict() for item in self.memory.list_memory_maintenance_incidents(scope_key=scope_key)],
            "maintenance_mode": self.memory.maintenance_mode(scope_key=scope_key),
            "maintenance_workers": [item.to_dict() for item in self.memory.list_memory_maintenance_workers()],
            "maintenance_controller_state": self.memory.maintenance_controller_state(scope_key=scope_key).to_dict(),
            "maintenance_rollouts": [item.to_dict() for item in self.memory.list_memory_maintenance_rollouts(scope_key=scope_key)],
            "admission_promotion_recommendations": [item.to_dict() for item in self.memory.list_admission_promotion_recommendations(scope_key=scope_key)],
            "analytics": [item.to_dict() for item in self.evolution.analyze_memory_policy_candidates(scope_key=scope_key)],
        }

    def promote_memory(self, memory_id: str):
        return self.memory.promote(memory_id)

    def propose_evolution(self, source_traces: list[str], hypothesis: str):
        return self.evolution.propose_candidate(
            candidate_type="skill_capsule",
            source_traces=source_traces,
            target_component="memory.procedural",
            hypothesis=hypothesis,
        )

    def evaluate_candidate(
        self,
        candidate_id: str,
        regression_failures: int | None = None,
        gain: float | None = None,
        report=None,
    ):
        return self.evolution.evaluate_candidate(
            candidate_id,
            regression_failures=regression_failures,
            gain=gain,
            report=report,
        )

    def promote_candidate(self, candidate_id: str):
        return self.evolution.promote_candidate(candidate_id)

    def rollback_candidate(self, candidate_id: str):
        return self.evolution.rollback_candidate(candidate_id)

    def checkpoints(self, task_id: str) -> list[CheckpointRecord]:
        return self.repository.list_checkpoints(task_id)

    def approval_inbox(self, task_id: str | None = None, status: str = "pending") -> list[ApprovalRequest]:
        return self.repository.list_approval_requests(task_id=task_id, status=status)

    def handoff_packet(self, task_id: str) -> HandoffPacket | None:
        return self.repository.latest_handoff_packet(task_id)

    def open_questions(self, task_id: str, status: str | None = None) -> list[OpenQuestion]:
        return self.repository.list_open_questions(task_id, status=status)

    def next_actions(self, task_id: str, status: str | None = None) -> list[NextAction]:
        return self.repository.list_next_actions(task_id, status=status)

    def continuity_working_set(self, task_id: str, role_name: str = "Strategist") -> ContinuityWorkingSet:
        latest = self.repository.latest_continuity_working_set(task_id)
        if latest is not None and role_name == "Strategist":
            return latest
        return self.continuity.reconstruct_working_set(task_id, role_name)

    def discover_cli_anything_harnesses(self, search_roots: list[str] | None = None) -> list[SoftwareHarnessRecord]:
        discovered = self.software_control_tool.discover(search_roots=search_roots)
        records: list[SoftwareHarnessRecord] = []
        for record in discovered:
            existing = self.repository.load_software_harness(record.harness_id)
            if existing is not None:
                records.append(existing)
                continue
            registered, commands, policy = self.software_control_tool.register(
                executable_path=record.executable_path,
                discovery_mode=record.discovery_mode,
            )
            self.repository.save_software_harness(registered)
            for command in commands:
                self.repository.save_software_command(command)
            self.repository.save_software_control_policy(policy)
            records.append(registered)
        return records

    def register_cli_anything_harness(
        self,
        *,
        executable_path: str,
        policy_overrides: dict[str, object] | None = None,
    ) -> dict[str, object]:
        harness, commands, policy = self.software_control_tool.register(
            executable_path=executable_path,
            discovery_mode="manual",
            policy_overrides=policy_overrides,
        )
        self.repository.save_software_harness(harness)
        for command in commands:
            self.repository.save_software_command(command)
        self.repository.save_software_control_policy(policy)
        return {
            "harness": harness.to_dict(),
            "commands": [item.to_dict() for item in commands],
            "policy": policy.to_dict(),
        }

    def list_cli_anything_harnesses(self) -> list[SoftwareHarnessRecord]:
        return self.repository.list_software_harnesses()

    def _software_risk_classes(self) -> list[SoftwareRiskClass]:
        records = self.repository.list_software_risk_classes()
        if records:
            return records
        records = [
            SoftwareRiskClass(version="1.0", risk_level="low", approval_required=False, blocked=False, description="safe default governed app action"),
            SoftwareRiskClass(version="1.0", risk_level="high", approval_required=True, blocked=False, description="high-risk app action requiring approval"),
            SoftwareRiskClass(version="1.0", risk_level="destructive", approval_required=True, blocked=False, description="destructive app action requiring explicit approval"),
            SoftwareRiskClass(version="1.0", risk_level="blocked", approval_required=True, blocked=True, description="blocked app action outside the governed safety boundary"),
        ]
        for record in records:
            self.repository.save_software_risk_class(record)
        return records

    def _build_app_capability(self, harness: SoftwareHarnessRecord, commands: list[object], policy: SoftwareControlPolicy) -> AppCapabilityRecord:
        approval_required_count = sum(1 for command in commands if bool(getattr(command, "approval_required", False)))
        destructive_count = sum(1 for command in commands if getattr(command, "risk_level", "") == "destructive")
        taxonomy: set[str] = {"governed_cli", "contract_bound"}
        for command in commands:
            lowered = " ".join(getattr(command, "command_path", [])).lower()
            if "inspect" in lowered:
                taxonomy.add("inspection")
            if "recover" in lowered or "repair" in lowered:
                taxonomy.add("recovery")
            if "delete" in lowered or getattr(command, "risk_level", "") == "destructive":
                taxonomy.add("destructive")
        capability = AppCapabilityRecord(
            version="1.0",
            capability_id=f"app-capability-{harness.harness_id}",
            harness_id=harness.harness_id,
            software_name=harness.software_name,
            supports_json=harness.supports_json,
            supports_replay=True,
            command_count=len(commands),
            approval_required_count=approval_required_count,
            destructive_count=destructive_count,
            evidence_capture_mode=policy.evidence_capture_mode,
            capability_taxonomy=sorted(taxonomy),
            supported_modes=["direct_action", "replay", "macro"],
            risk_families=sorted({str(getattr(command, "risk_level", "low")) for command in commands} or {"low"}),
        )
        self.repository.save_app_capability(capability)
        return capability

    def software_harness_manifest(self, *, harness_id: str) -> HarnessManifest:
        harness = self.repository.load_software_harness(harness_id)
        if harness is None:
            raise KeyError(harness_id)
        existing = self.repository.load_harness_manifest(harness_id)
        if existing is not None:
            return existing
        commands = self.repository.list_software_commands(harness_id)
        policy = self.repository.load_software_control_policy(harness_id)
        if policy is None:
            _, _, policy = self.software_control_tool.register(executable_path=harness.executable_path)
            self.repository.save_software_control_policy(policy)
        validation = self.repository.latest_software_harness_validation(harness_id)
        capability = self.repository.load_app_capability(harness_id) or self._build_app_capability(harness, commands, policy)
        manifest = HarnessManifest(
            version="1.0",
            manifest_id=f"harness-manifest-{harness_id}",
            harness_id=harness_id,
            software_name=harness.software_name,
            harness=harness,
            commands=commands,
            policy=policy,
            risk_classes=self._software_risk_classes(),
            app_capability=capability,
            validation_status="unknown" if validation is None else validation.status,
            automation_tags=sorted(set(capability.capability_taxonomy + ["cli-anything", "governed"])),
        )
        self.repository.save_harness_manifest(manifest)
        return manifest

    def software_action_receipts(
        self,
        *,
        task_id: str | None = None,
        harness_id: str | None = None,
    ) -> list[SoftwareActionReceipt]:
        records = self.repository.list_software_action_receipts(task_id)
        if harness_id is not None:
            records = [record for record in records if record.harness_id == harness_id]
        return records

    def software_replay_records(self, *, task_id: str | None = None) -> list[SoftwareReplayRecord]:
        return self.repository.list_software_replay_records(task_id)

    def software_failure_patterns(self, *, harness_id: str | None = None) -> list[SoftwareFailurePattern]:
        return self.repository.list_software_failure_patterns(harness_id)

    def software_automation_macros(self, *, harness_id: str | None = None) -> list[SoftwareAutomationMacro]:
        return self.repository.list_software_automation_macros(harness_id)

    def register_software_automation_macro(
        self,
        *,
        harness_id: str,
        actor: str,
        name: str,
        description: str,
        steps: list[dict[str, object]],
        automation_tags: list[str] | None = None,
    ) -> SoftwareAutomationMacro:
        harness = self.repository.load_software_harness(harness_id)
        if harness is None:
            raise KeyError(harness_id)
        policy = self.repository.load_software_control_policy(harness_id)
        if policy is None:
            _, _, policy = self.software_control_tool.register(executable_path=harness.executable_path)
            self.repository.save_software_control_policy(policy)
        approval_required = False
        normalized_steps: list[dict[str, object]] = []
        for step in steps:
            command_path = [str(item) for item in step.get("command_path", [])]
            arguments = [str(item) for item in step.get("arguments", [])]
            _, step_requires_approval, blocked = policy.classify(command_path)
            if blocked:
                raise ValueError(f"macro step is blocked by policy: {' '.join(command_path)}")
            approval_required = approval_required or step_requires_approval
            normalized_steps.append({"command_path": command_path, "arguments": arguments})
        macro = SoftwareAutomationMacro(
            version="1.0",
            macro_id=f"software-macro-{uuid4().hex[:10]}",
            harness_id=harness_id,
            software_name=harness.software_name,
            name=name,
            description=description,
            steps=normalized_steps,
            approval_required=approval_required,
            automation_tags=[] if automation_tags is None else [str(item) for item in automation_tags],
        )
        self.repository.save_software_automation_macro(macro)
        return macro

    def software_replay_diagnostics(self, *, task_id: str | None = None, harness_id: str | None = None) -> list[SoftwareReplayDiagnostic]:
        records = self.repository.list_software_replay_diagnostics(task_id)
        if harness_id is not None:
            records = [record for record in records if record.harness_id == harness_id]
        return records

    def software_recovery_hints(self, *, harness_id: str | None = None) -> list[SoftwareRecoveryHint]:
        return self.repository.list_software_recovery_hints(harness_id)

    def software_failure_clusters(self, *, harness_id: str | None = None) -> list[SoftwareFailureCluster]:
        return self.repository.list_software_failure_clusters(harness_id)

    def software_harness_report(self, *, harness_id: str) -> dict[str, object]:
        manifest = RuntimeService.software_harness_manifest(self, harness_id=harness_id)
        action_receipts = [item for item in self.repository.list_software_action_receipts() if item.harness_id == harness_id]
        task_ids = {item.task_id for item in action_receipts}
        replay_diagnostics = [
            item.to_dict()
            for item in RuntimeService.software_replay_diagnostics(self, harness_id=harness_id)
        ]
        return {
            "manifest": manifest.to_dict(),
            "macros": [item.to_dict() for item in RuntimeService.software_automation_macros(self, harness_id=harness_id)],
            "action_receipts": [item.to_dict() for item in action_receipts],
            "replays": [
                item.to_dict()
                for item in self.repository.list_software_replay_records()
                if item.harness_id == harness_id and item.task_id in task_ids
            ],
            "replay_diagnostics": replay_diagnostics,
            "failure_patterns": [item.to_dict() for item in RuntimeService.software_failure_patterns(self, harness_id=harness_id)],
            "failure_clusters": [item.to_dict() for item in RuntimeService.software_failure_clusters(self, harness_id=harness_id)],
            "recovery_hints": [item.to_dict() for item in RuntimeService.software_recovery_hints(self, harness_id=harness_id)],
        }

    def validate_cli_anything_harness(self, harness_id: str) -> SoftwareHarnessValidation:
        harness = self.repository.load_software_harness(harness_id)
        if harness is None:
            raise KeyError(harness_id)
        validation = self.software_control_tool.validate(harness)
        self.repository.save_software_harness_validation(validation)
        self.repository.save_harness_manifest(RuntimeService.software_harness_manifest(self, harness_id=harness_id))
        return validation

    def configure_cli_anything_bridge(self, *, repo_path: str, enabled: bool = True) -> SoftwareControlBridgeConfig:
        bridge = SoftwareControlBridgeConfig(
            version="1.0",
            bridge_id="software-control-bridge-cli-anything",
            source_kind="cli-anything",
            repo_path=repo_path,
            codex_skill_path=str(Path.home() / ".codex" / "skills" / "cli-anything"),
            enabled=enabled,
            builder_capabilities=["build", "refine", "test", "validate", "install-codex-skill"],
        )
        self.repository.save_software_control_bridge(bridge)
        return bridge

    def list_cli_anything_bridges(self) -> list[SoftwareControlBridgeConfig]:
        return self.repository.list_software_control_bridges("cli-anything")

    def submit_cli_anything_build_request(
        self,
        *,
        target: str,
        mode: str,
        focus: str = "",
    ) -> SoftwareBuildRequest:
        bridges = self.list_cli_anything_bridges()
        repo_path = bridges[0].repo_path if bridges else (self.cli_anything_repo_path or "")
        request = SoftwareBuildRequest(
            version="1.0",
            build_request_id=f"software-build-{uuid4().hex[:10]}",
            source_kind="cli-anything",
            target=target,
            mode=mode,
            focus=focus,
            repo_path=repo_path,
            status="pending",
        )
        self.repository.save_software_build_request(request)
        return request

    def install_cli_anything_codex_skill(self) -> dict[str, object]:
        bridges = self.list_cli_anything_bridges()
        if not bridges:
            raise RuntimeError("cli-anything bridge is not configured")
        bridge = bridges[0]
        destination = Path(bridge.codex_skill_path)
        if destination.exists():
            return {"status": "already_installed", "skill_path": str(destination)}
        installer = Path(bridge.repo_path) / "codex-skill" / "scripts" / "install.sh"
        invocation, result = self.software_control_tool_shell().run(["bash", str(installer)], cwd=Path(bridge.repo_path))
        return {
            "status": "installed" if result.status == "success" else "failed",
            "skill_path": str(destination),
            "invocation": invocation.to_dict(),
            "result": result.to_dict(),
        }

    def _software_replay_diagnostic(
        self,
        *,
        replay_record: SoftwareReplayRecord,
        action_receipt: SoftwareActionReceipt,
        result_status: str,
    ) -> SoftwareReplayDiagnostic:
        reproducibility = "replayable" if result_status == "success" else "needs_operator_review"
        explanation = (
            "The governed action completed successfully with recorded evidence and can usually be replayed."
            if reproducibility == "replayable"
            else "The last governed action failed, so replay should be treated as a recovery path rather than a deterministic rerun."
        )
        return SoftwareReplayDiagnostic(
            version="1.0",
            diagnostic_id=f"software-replay-diagnostic-{uuid4().hex[:10]}",
            task_id=action_receipt.task_id,
            harness_id=action_receipt.harness_id,
            replay_id=replay_record.replay_id,
            action_receipt_id=action_receipt.action_id,
            reproducibility=reproducibility,
            explanation=explanation,
        )

    def _upsert_software_failure_cluster(self, *, harness: SoftwareHarnessRecord, pattern: SoftwareFailurePattern) -> SoftwareFailureCluster:
        existing = next(
            (
                item
                for item in self.repository.list_software_failure_clusters(harness.harness_id)
                if item.failure_classification == pattern.failure_classification
            ),
            None,
        )
        if existing is None:
            existing = SoftwareFailureCluster(
                version="1.0",
                cluster_id=f"software-failure-cluster-{uuid4().hex[:10]}",
                harness_id=harness.harness_id,
                software_name=harness.software_name,
                failure_classification=pattern.failure_classification,
                command_signatures=[pattern.command_signature],
                occurrence_count=pattern.occurrence_count,
            )
        else:
            existing.command_signatures = sorted(set(existing.command_signatures + [pattern.command_signature]))
            existing.occurrence_count += 1
        self.repository.save_software_failure_cluster(existing)
        return existing

    def _upsert_software_recovery_hint(self, *, harness: SoftwareHarnessRecord, pattern: SoftwareFailurePattern) -> SoftwareRecoveryHint:
        recommendation = (
            f"Retry {harness.software_name} with a recovery-oriented macro or verify app state before replaying {pattern.command_signature}."
        )
        existing = next(
            (
                item
                for item in self.repository.list_software_recovery_hints(harness.harness_id)
                if item.trigger_signature == pattern.command_signature
            ),
            None,
        )
        if existing is None:
            existing = SoftwareRecoveryHint(
                version="1.0",
                hint_id=f"software-recovery-hint-{uuid4().hex[:10]}",
                harness_id=harness.harness_id,
                software_name=harness.software_name,
                trigger_signature=pattern.command_signature,
                recommendation=recommendation,
                source_receipt_ids=list(pattern.recent_receipt_ids),
            )
        else:
            existing.recommendation = recommendation
            existing.source_receipt_ids = list(pattern.recent_receipt_ids)
        self.repository.save_software_recovery_hint(existing)
        return existing

    def invoke_cli_anything_harness(
        self,
        *,
        harness_id: str,
        command_path: list[str],
        arguments: list[str],
        actor: str,
        task_id: str | None = None,
        approved: bool = False,
        dry_run: bool = False,
    ) -> dict[str, object]:
        harness = self.repository.load_software_harness(harness_id)
        if harness is None:
            raise KeyError(harness_id)
        policy = self.repository.load_software_control_policy(harness_id)
        if policy is None:
            _, _, policy = self.software_control_tool.register(executable_path=harness.executable_path)
            self.repository.save_software_control_policy(policy)
        request = self._ensure_software_control_task_request(
            task_id=task_id,
            harness=harness,
            command_path=command_path,
            arguments=arguments,
        )
        task_id = str(request["task_id"])
        self._ensure_budget_state(task_id, request)
        contract = self._ensure_contract(task_id, request)
        self._persist_task_state(
            task_id=task_id,
            status="running",
            current_phase="software_control_running",
            request=request,
            contract_id=contract.contract_id,
        )
        evidence = self._load_evidence(task_id)
        risk_level, approval_required, blocked = policy.classify(command_path)
        approval_refs: list[str] = []
        plan_node_id = f"software-control:{harness.software_name}:{'-'.join(command_path)}"
        if blocked or (approval_required and not approved):
            approval_request = self._request_software_control_approval(
                task_id=task_id,
                contract=contract,
                harness=harness,
                command_path=command_path,
                reason="software control command requires operator review",
            )
            approval_refs = [approval_request.request_id]
            self._persist_task_state(
                task_id=task_id,
                status="awaiting_approval",
                current_phase="software_control_waiting_for_approval",
                request=request,
                contract_id=contract.contract_id,
            )
            self._audit_event(
                task_id=task_id,
                contract_id=contract.contract_id,
                event_type="approval_requested",
                actor="Governor",
                why=approval_request.reason,
                risk_level="high" if blocked else risk_level,
                result="pending",
                approval_refs=approval_refs,
            )
            return {
                "status": "awaiting_approval",
                "task_id": task_id,
                "harness": harness.to_dict(),
                "approval_request": approval_request.to_dict(),
            }
        budget_incident = self._budget_check(task_id, "tool", 0.02 if risk_level == "low" else 0.05)
        if budget_incident is not None:
            return {"status": "failed", "task_id": task_id, "incident": budget_incident.to_dict()}
        self._select_tool_variant(task_id=task_id, plan_node_id=plan_node_id, tool_name=harness.executable_name)
        invocation, result, parsed = self.software_control_tool.invoke(
            harness=harness,
            policy=policy,
            command_path=command_path,
            arguments=arguments,
            actor=actor,
            approved=approved,
            dry_run=dry_run,
        )
        invocation.task_id = task_id
        invocation.plan_node_id = plan_node_id
        self.repository.save_tool_invocation(task_id, invocation)
        self.repository.save_tool_result(task_id, result)
        actual_cost = 0.0 if result.provider_mode == "simulator" else (0.02 if result.status == "success" else 0.01)
        self._record_budget_consumption(
            task_id=task_id,
            category="tool",
            ref_id=invocation.invocation_id,
            estimated_cost=0.02 if risk_level == "low" else 0.05,
            actual_cost=actual_cost,
            justification=f"software control via {harness.executable_name}",
        )
        evidence_refs = self._record_software_control_evidence(
            task_id=task_id,
            harness=harness,
            command_path=command_path,
            result=result,
            parsed=parsed,
            evidence=evidence,
        )
        receipt = ExecutionReceipt(
            version="1.0",
            receipt_id=f"receipt-{uuid4().hex[:10]}",
            contract_id=contract.contract_id,
            plan_node_id=plan_node_id,
            actor=actor,
            tool_used=harness.executable_name,
            input_summary=" ".join(command_path + arguments),
            output_summary=str(result.output_payload.get("parsed_json") or result.output_payload.get("stdout", ""))[:240],
            artifacts=result.artifact_refs,
            evidence_refs=evidence_refs,
            validation_refs=[],
            approval_refs=approval_refs,
            status=result.status,
            timestamp=utc_now(),
        )
        self.repository.save_execution_receipt(task_id, receipt)
        action_receipt = SoftwareActionReceipt(
            version="1.0",
            action_id=f"software-action-{invocation.invocation_id}",
            task_id=task_id,
            harness_id=harness.harness_id,
            software_name=harness.software_name,
            command_path=list(command_path),
            arguments=list(arguments),
            risk_level=risk_level,
            approval_request_ids=list(approval_refs),
            invocation_id=invocation.invocation_id,
            result_status=result.status,
            execution_receipt_id=receipt.receipt_id,
            evidence_refs=list(evidence_refs),
            artifact_refs=list(result.artifact_refs),
        )
        self.repository.save_software_action_receipt(action_receipt)
        replay_record = SoftwareReplayRecord(
            version="1.0",
            replay_id=f"software-replay-{invocation.invocation_id}",
            action_receipt_id=action_receipt.action_id,
            task_id=task_id,
            harness_id=harness.harness_id,
            command_signature=f"{harness.harness_id}:{' '.join(command_path)} {' '.join(arguments)}".strip(),
            status="recorded",
            last_result_status=result.status,
        )
        self.repository.save_software_replay_record(replay_record)
        replay_diagnostic = self._software_replay_diagnostic(
            replay_record=replay_record,
            action_receipt=action_receipt,
            result_status=result.status,
        )
        self.repository.save_software_replay_diagnostic(replay_diagnostic)
        self.repository.save_software_control_telemetry_record(
            SoftwareControlTelemetryRecord(
                version="1.0",
                telemetry_id=f"software-telemetry-{uuid4().hex[:10]}",
                scope_key=task_id,
                harness_id=harness.harness_id,
                action_receipt_id=action_receipt.action_id,
                risk_level=risk_level,
                result_status=result.status,
                replayable=replay_diagnostic.reproducibility == "replayable",
                failure_classification=result.failure_classification,
                metadata={"command_path": list(command_path), "arguments": list(arguments)},
            )
        )
        software_procedure = MemorySoftwareProcedureRecord(
            version="1.0",
            procedure_id=f"memory-software-procedure-{invocation.invocation_id}",
            task_id=task_id,
            scope_key=task_id,
            software_name=harness.software_name,
            command_path=list(command_path),
            summary=f"Use {harness.software_name} command {' '.join(command_path)}",
            steps=[f"invoke {harness.executable_name}", "capture structured output", "record execution receipt", "attach evidence"],
            failure_modes=[] if result.failure_classification is None else [result.failure_classification],
            provenance=[invocation.invocation_id, receipt.receipt_id, *evidence_refs],
            created_at=utc_now(),
        )
        self.memory.software_procedures[software_procedure.procedure_id] = software_procedure
        self.repository.save_memory_software_procedure(software_procedure)
        if result.status != "success":
            command_signature = replay_record.command_signature
            existing_patterns = [item for item in self.repository.list_software_failure_patterns(harness.harness_id) if item.command_signature == command_signature]
            if existing_patterns:
                pattern = existing_patterns[0]
                pattern.occurrence_count += 1
                pattern.recent_receipt_ids = (pattern.recent_receipt_ids + [action_receipt.action_id])[-5:]
                pattern.updated_at = utc_now()
            else:
                pattern = SoftwareFailurePattern(
                    version="1.0",
                    pattern_id=f"software-failure-{uuid4().hex[:10]}",
                    harness_id=harness.harness_id,
                    software_name=harness.software_name,
                    command_signature=command_signature,
                    failure_classification=result.failure_classification or "unknown_failure",
                    occurrence_count=1,
                    recent_receipt_ids=[action_receipt.action_id],
                )
            self.repository.save_software_failure_pattern(pattern)
            self._upsert_software_failure_cluster(harness=harness, pattern=pattern)
            self._upsert_software_recovery_hint(harness=harness, pattern=pattern)
        scorecard = self.tool_governance.update(
            scorecard=self.repository.get_tool_scorecard(result.tool_id, result.provider_mode),
            result=result,
            evidence_usefulness=1.0 if evidence_refs else 0.2,
            cost_impact=actual_cost,
        )
        self.repository.save_tool_scorecard(scorecard)
        self._audit_event(
            task_id=task_id,
            contract_id=contract.contract_id,
            event_type="software_control_invocation",
            actor=actor,
            why=f"Invoke {harness.software_name} through CLI-Anything",
            risk_level=risk_level,
            result=result.status,
            evidence_refs=evidence_refs,
            tool_refs=[harness.executable_name],
            approval_refs=approval_refs,
        )
        self._persist_task_state(
            task_id=task_id,
            status="completed" if result.status == "success" else "failed",
            current_phase="software_control_completed" if result.status == "success" else "software_control_failed",
            request=request,
            contract_id=contract.contract_id,
            result={"result": result.to_dict(), "parsed_json": parsed},
        )
        return {
            "status": "completed" if result.status == "success" else "failed",
            "task_id": task_id,
            "harness": harness.to_dict(),
            "result": {**result.to_dict(), "parsed_json": parsed},
            "receipt": receipt.to_dict(),
            "evidence_refs": evidence_refs,
            "replay_diagnostic": replay_diagnostic.to_dict(),
        }

    def invoke_software_automation_macro(
        self,
        *,
        macro_id: str,
        actor: str,
        task_id: str | None = None,
        approved: bool = False,
        dry_run: bool = False,
    ) -> dict[str, object]:
        macro = self.repository.load_software_automation_macro(macro_id)
        if macro is None:
            raise KeyError(macro_id)
        step_results: list[dict[str, object]] = []
        for step in macro.steps:
            step_results.append(
                self.invoke_cli_anything_harness(
                    harness_id=macro.harness_id,
                    command_path=[str(item) for item in step.get("command_path", [])],
                    arguments=[str(item) for item in step.get("arguments", [])],
                    actor=actor,
                    task_id=task_id,
                    approved=approved,
                    dry_run=dry_run,
                )
            )
            if step_results[-1]["status"] not in {"completed", "failed"}:
                break
        overall_status = "completed" if all(item["status"] == "completed" for item in step_results) else "failed"
        return {
            "status": overall_status,
            "macro": macro.to_dict(),
            "steps": step_results,
            "summary": {
                "step_count": len(macro.steps),
                "completed_steps": len([item for item in step_results if item["status"] == "completed"]),
            },
        }

    def decide_approval(
        self,
        request_id: str,
        approver: str,
        status: str,
        rationale: str,
        approved_scope: list[str] | None = None,
        intervention_action: str | None = None,
    ) -> ApprovalDecision:
        request = next(
            approval for approval in self.repository.list_approval_requests() if approval.request_id == request_id
        )
        request.status = status
        self.repository.save_approval_request(request)
        decision = ApprovalDecision(
            version="1.0",
            request_id=request_id,
            decision_id=f"approval-decision-{uuid4().hex[:10]}",
            approver=approver,
            status=status,
            approved_scope=approved_scope or request.requested_scope,
            rationale=rationale,
            decided_at=utc_now(),
            intervention_action=intervention_action or ("approve" if status == "approved" else status),
            task_id=request.task_id,
            plan_node_id=request.plan_node_id,
        )
        self.repository.save_approval_decision(decision)
        self._audit_event(
            task_id=request.task_id,
            contract_id=request.contract_id,
            event_type="approval_decision",
            actor="Governor",
            why=rationale,
            risk_level=request.risk_level,
            result=status,
            approval_refs=[request.request_id],
        )
        self._emit_telemetry(
            request.task_id,
            "approval_decided",
            {"request_id": request.request_id, "status": status, "approver": approver},
        )
        return decision

    def intervene_task(
        self,
        task_id: str,
        action: str,
        operator: str,
        reason: str,
        payload: dict[str, str],
    ) -> HumanIntervention:
        intervention = HumanIntervention(
            version="1.0",
            intervention_id=f"intervention-{uuid4().hex[:10]}",
            task_id=task_id,
            action=action,
            operator=operator,
            reason=reason,
            created_at=utc_now(),
            payload=payload,
        )
        self.repository.save_human_intervention(intervention)
        task = self.repository.get_task(task_id)
        if task is not None and action == "pause_task":
            self._persist_task_state(task_id, "paused", "paused", task["request"], task["contract_id"], task["plan_graph_id"], task["latest_checkpoint_id"], task["result"])
        elif action == "force_low_cost_mode":
            self.execution_mode_overrides[task_id] = "low_cost"
            self._set_execution_mode(
                task_id=task_id,
                mode_name="low_cost",
                reason=reason,
                active_constraints=["operator forced low-cost mode"],
                deferred_opportunities=["higher-cost provider and tool paths"],
            )
        elif action == "force_verification_heavy_mode":
            self.execution_mode_overrides[task_id] = "verification_heavy"
            self._set_execution_mode(
                task_id=task_id,
                mode_name="verification_heavy",
                reason=reason,
                active_constraints=["operator requested stronger verification"],
                deferred_opportunities=["faster lower-confidence completion"],
            )
        elif action == "cap_concurrency":
            cap = max(1, int(payload.get("max_parallel_nodes", "1")))
            self.concurrency_caps[task_id] = cap
            self._save_concurrency_state(task_id, active_nodes=[], last_batch_nodes=[])
        elif action == "pause_provider":
            provider_name = payload.get("provider_name", "")
            if provider_name:
                self.disabled_providers.add(provider_name)
        elif action == "disable_tool":
            tool_name = payload.get("tool_name", "")
            if tool_name:
                self.disabled_tools.add(tool_name)
        elif action == "approve_budget_override":
            self.repository.save_budget_event(
                self.budget_manager.make_event(
                    task_id=task_id,
                    event_type="budget_override_approved",
                    summary=reason,
                    payload=payload,
                )
            )
        elif action == "set_drain_mode":
            self._set_global_execution_mode("drain", reason, ["operator drain mode"])
        elif action == "clear_drain_mode":
            self._set_global_execution_mode("normal", reason, [])
        elif action == "disable_provider":
            provider_name = payload.get("provider_name", "")
            if provider_name:
                self.disabled_providers.add(provider_name)
                record = self.provider_health.snapshot([provider_name]).records[0]
                record.operator_disabled = True
                record.availability_state = "disabled"
                self.repository.save_provider_health_record(record)
        elif action == "enable_provider":
            provider_name = payload.get("provider_name", "")
            if provider_name:
                self.disabled_providers.discard(provider_name)
                record = self.provider_health.snapshot([provider_name]).records[0]
                record.operator_disabled = False
                record.availability_state = "available"
                self.repository.save_provider_health_record(record)
        elif action == "force_half_open_probe":
            provider_name = payload.get("provider_name", "")
            if provider_name:
                self.provider_health.force_half_open_probe(provider_name)
        elif task is not None and action == "downgrade_tool_scope":
            request = dict(task["request"])
            preferences = dict(request.get("preferences", {}))
            preferences["tool_scope"] = "downgraded"
            request["preferences"] = preferences
            self._persist_task_state(task_id, task["status"], task["current_phase"], request, task["contract_id"], task["plan_graph_id"], task["latest_checkpoint_id"], task["result"])
        elif action == "force_checkpoint":
            self.checkpoint_task(task_id, payload.get("plan_node_id", "operator"), {"phase": payload.get("phase", "operator")})
        elif task is not None and action == "force_recovery_path":
            plan = self.repository.load_plan(task_id)
            if plan is not None:
                failed_node_id = payload.get("failed_node_id", "node-reconcile-delivery")
                fallback_objective = payload.get("fallback_objective", "Review evidence before continuing delivery")
                revised = self.planner.replan_local(plan, failed_node_id=failed_node_id, fallback_objective=fallback_objective)
                self.repository.save_plan(task_id, revised)
        self._emit_telemetry(task_id, "human_intervention", {"action": action, "operator": operator, "payload": payload})
        return intervention

    def run_task(
        self,
        goal: str,
        attachments: list[str],
        preferences: dict[str, str],
        prohibitions: list[str],
        task_id: str | None = None,
        interrupt_after: str | None = None,
    ) -> TaskRunResult:
        if task_id is None:
            request = self.create_task(goal, attachments, preferences, prohibitions)
            task_id = str(request["task_id"])
        else:
            task = self.repository.get_task(task_id)
            request = task["request"] if task is not None else self.create_task(goal, attachments, preferences, prohibitions, task_id)

        self._ensure_budget_state(task_id, request)
        contract = self._ensure_contract(task_id, request)
        lattice = self._ensure_lattice(task_id, contract)
        plan = self._ensure_plan(task_id, contract, request)
        self._prime_amos_runtime_memory(task_id=task_id, request=request, contract=contract, plan=plan)
        self._interrupt_if_requested(task_id, interrupt_after, "planned")

        evidence = self._load_evidence(task_id)
        incident = self.execute_plan(
            task_id=task_id,
            contract=contract,
            plan=plan,
            lattice=lattice,
            attachments=list(request["attachments"]),
            evidence=evidence,
            interrupt_after=interrupt_after,
        )

        if incident is not None:
            if incident.incident_type == "approval_wait":
                return self._finalize_waiting_approval_task(task_id, contract, plan, lattice, evidence, incident)
            return self._finalize_blocked_task(task_id, contract, plan, lattice, evidence, incident)

        delivery = self._build_delivery(evidence)
        validation_report = self.repository.load_latest_validation_report(task_id)
        if validation_report is None or validation_report.validator != "ShadowVerifier":
            validation_report = self.validate_result(task_id, contract, evidence, delivery)
        plan = self.repository.load_plan(task_id) or plan
        result = TaskRunResult(
            task_id=task_id,
            status="completed" if validation_report.status == "passed" else "blocked",
            contract=contract,
            plan=plan,
            contract_lattice=lattice,
            delivery=delivery,
            validation_report=validation_report,
            evidence_graph=evidence.graph,
            audit_events=self.repository.query_audit(task_id=task_id),
            receipts=self.repository.list_execution_receipts(task_id),
            routing_receipts=self.repository.list_routing_receipts(task_id),
        )
        final_checkpoint = self.checkpoint_task(
            task_id,
            "node-capture-learning",
            {"phase": "delivery", "status": result.status, "facts": len(result.delivery["facts"])},
        )
        handoff, working_set, open_questions, next_actions = self._refresh_long_horizon_state(
            task_id=task_id,
            contract=contract,
            plan=plan,
            lattice=lattice,
            evidence=evidence,
            checkpoint_id=final_checkpoint.checkpoint_id,
            validation_report=validation_report,
        )
        self._audit_event(
            task_id=task_id,
            contract_id=contract.contract_id,
            event_type="delivery",
            actor="Archivist",
            why="Persist final delivery packet",
            risk_level=contract.risk_level,
            result=result.status,
            evidence_refs=validation_report.evidence_refs,
        )
        self._persist_task_state(
            task_id=task_id,
            status=result.status,
            current_phase=result.status,
            request=request,
            contract_id=contract.contract_id,
            plan_graph_id=plan.graph_id,
            latest_checkpoint_id=final_checkpoint.checkpoint_id,
            result={
                "status": result.status,
                "delivery": delivery,
                "validation_report": validation_report.to_dict(),
            },
        )
        result.audit_events = self.repository.query_audit(task_id=task_id)
        result.handoff_packet = handoff
        result.continuity_working_set = working_set
        result.open_questions = open_questions
        result.next_actions = next_actions
        self._capture_amos_delivery_memory(
            task_id=task_id,
            request=request,
            contract=contract,
            plan=plan,
            delivery=delivery,
            validation_report=validation_report,
        )
        self.task_results[task_id] = result
        self.task_status_cache[task_id] = result.status
        self._emit_telemetry(task_id, "task_completed", {"status": result.status, "checkpoint_id": final_checkpoint.checkpoint_id})
        return result

    def get_task_status(self, task_id: str) -> str | None:
        if task_id in self.task_status_cache:
            return self.task_status_cache.get(task_id)
        task = self.repository.get_task(task_id)
        return None if task is None else str(task["status"])

    def interrupt_task(self, task_id: str) -> str | None:
        task = self.repository.get_task(task_id)
        if task is None:
            return None
        contract = None if task["contract_id"] is None else self.repository.load_contract(str(task["contract_id"]))
        plan = self.repository.load_plan(task_id)
        lattice = self.repository.load_contract_lattice(task_id)
        evidence = self._load_evidence(task_id)
        checkpoint = self.checkpoint_task(task_id, "operator-pause", {"phase": "paused", "task_id": task_id})
        self._persist_task_state(
            task_id,
            "paused",
            "paused",
            task["request"],
            task["contract_id"],
            task["plan_graph_id"],
            checkpoint.checkpoint_id,
            task["result"],
        )
        if contract is not None and plan is not None and lattice is not None:
            self._refresh_long_horizon_state(
                task_id=task_id,
                contract=contract,
                plan=plan,
                lattice=lattice,
                evidence=evidence,
                checkpoint_id=checkpoint.checkpoint_id,
            )
        self._emit_telemetry(task_id, "task_paused", {"checkpoint_id": checkpoint.checkpoint_id})
        return "paused"

    def register_worker(
        self,
        *,
        worker_id: str,
        worker_role: str,
        process_identity: str,
        capabilities: WorkerCapabilityRecord,
        claimed_capacity: int = 1,
        host_id: str | None = None,
        service_identity: str = "worker-service",
        endpoint_address: str = "",
    ):
        record = self.coordination.register_worker(
            worker_id=worker_id,
            worker_role=worker_role,
            process_identity=process_identity,
            capabilities=capabilities,
            claimed_capacity=claimed_capacity,
            host_id=host_id or socket.gethostname(),
            service_identity=service_identity,
            endpoint_address=endpoint_address or f"worker://{host_id or socket.gethostname()}/{worker_id}",
        )
        self._refresh_backend_state()
        return record

    def heartbeat_worker(
        self,
        worker_id: str,
        *,
        active_leases: list[str] | None = None,
        capacity_in_use: int = 0,
        heartbeat_latency_ms: float = 0.0,
    ):
        heartbeat = self.coordination.heartbeat(
            worker_id,
            active_leases=[] if active_leases is None else active_leases,
            capacity_in_use=capacity_in_use,
            heartbeat_latency_ms=heartbeat_latency_ms,
        )
        self._refresh_backend_state()
        return heartbeat

    def reclaim_stale_workers(
        self,
        *,
        force_expire: bool = False,
        heartbeat_expiry_seconds: int = 30,
    ) -> dict[str, int]:
        reclaimed = self.coordination.reclaim_stale_workers(
            heartbeat_expiry_seconds=0 if force_expire else heartbeat_expiry_seconds,
        )
        for ownership in reclaimed:
            try:
                self.queue_backend.force_requeue(lease_id=ownership.lease_id, reason="stale worker recovered")
            except KeyError:
                continue
        self._emit_telemetry(
            "system",
            "stale_workers_reclaimed",
            {"reclaimed_leases": len(reclaimed)},
        )
        self._refresh_backend_state()
        return {"reclaimed_workers": len({item.worker_id for item in reclaimed}), "reclaimed_leases": len(reclaimed)}

    def attempt_work_steal(self, *, worker_id: str, now=None) -> dict[str, object] | None:
        now = utc_now() if now is None else now
        active = [
            ownership
            for ownership in self.repository.list_lease_ownerships(statuses=["active"])
            if ownership.worker_id != worker_id
        ]
        if not active:
            return None
        target = sorted(active, key=lambda item: item.acquired_at)[0]
        decision = self.coordination.steal_lease(
            lease_id=target.lease_id,
            queue_item_id=target.queue_item_id,
            task_id=target.task_id,
            new_worker_id=worker_id,
            now=now,
            policy=WorkStealPolicy(
                version="1.0",
                policy_id="work-steal-default",
                allow_steal_from_draining=True,
                allow_steal_from_stale=True,
                min_lease_age_seconds=20,
                max_pressure_to_keep_owner=0.8,
                protect_verification_capacity=True,
                protect_recovery_capacity=True,
            ),
        )
        if decision is None:
            return None
        self.queue_backend.force_requeue(lease_id=target.lease_id, reason="controlled work steal", now=now)
        self._refresh_backend_state()
        return {"status": "stolen", "lease_id": target.lease_id, "task_id": target.task_id, "decision_id": decision.decision_id}

    def _bind_dispatch_context(self, *, worker_id: str, lease_id: str, fencing_token: str) -> None:
        self._active_dispatch_context = {
            "worker_id": worker_id,
            "lease_id": lease_id,
            "fencing_token": fencing_token,
        }

    def _clear_dispatch_context(self) -> None:
        self._active_dispatch_context = None

    def _assert_active_dispatch_ownership(self) -> None:
        if self._active_dispatch_context is None:
            return
        if not self.coordination.validate_fencing(
            lease_id=self._active_dispatch_context["lease_id"],
            worker_id=self._active_dispatch_context["worker_id"],
            fencing_token=self._active_dispatch_context["fencing_token"],
        ):
            raise RuntimeError("dispatch lease ownership was fenced or reclaimed")

    def _dispatch_via_external_queue(self, *, worker_id: str, capacity_snapshot, provider_health):
        now = utc_now()
        ready_items = self.queue_backend.list_ready(queue_name="default", now=now)
        for item in ready_items:
            decision = self.queue.evaluate_admission(
                item=item,
                capacity_snapshot=capacity_snapshot,
                provider_health=provider_health,
                system_mode=self.system_mode,
            )
            self.repository.save_admission_decision(decision)
            if decision.status != "admitted":
                item.status = "deferred" if decision.status == "deferred" else "rejected"
                item.updated_at = now
                self.repository.save_queue_item(item)
                continue
            policy = self.repository.load_queue_policy(item.queue_name)
            lease_timeout_seconds = 60 if policy is None else policy.lease_timeout_seconds
            lease = self.queue_backend.acquire_lease(
                queue_item_id=item.queue_item_id,
                worker_id=worker_id,
                lease_timeout_seconds=lease_timeout_seconds,
                now=now,
            )
            dispatch = DispatchRecord(
                version="1.0",
                dispatch_id=f"dispatch-{uuid4().hex[:10]}",
                queue_item_id=item.queue_item_id,
                task_id=item.task_id,
                lease_id=lease.lease_id,
                worker_id=worker_id,
                status="dispatched",
                admission_decision_id=decision.decision_id,
                created_at=now,
            )
            self.repository.save_dispatch_record(dispatch)
            refreshed = self.repository.get_queue_item(item.queue_item_id) or item
            return refreshed, lease, decision, dispatch
        return None

    def submit_task(
        self,
        goal: str,
        attachments: list[str],
        preferences: dict[str, str],
        prohibitions: list[str],
        task_id: str | None = None,
        priority_class: str = "standard",
        operator_priority: int = 0,
    ):
        if task_id is None:
            request = self.create_task(goal, attachments, preferences, prohibitions)
            task_id = str(request["task_id"])
        else:
            task = self.repository.get_task(task_id)
            request = task["request"] if task is not None else self.create_task(goal, attachments, preferences, prohibitions, task_id)
        self._ensure_budget_state(task_id, request)
        contract = self._ensure_contract(task_id, request)
        self._current_execution_mode(task_id, contract)
        open_questions = self.repository.list_open_questions(task_id)
        continuity_fragility = 0.95 if open_questions else 0.0
        queue_item = self.queue.enqueue_task(
            task_id=task_id,
            contract_id=contract.contract_id,
            risk_level=contract.risk_level,
            priority_class=priority_class,
            continuity_fragility=continuity_fragility,
            recovery_required=bool(open_questions),
            resume_task=bool(self.repository.get_task(task_id) and self.repository.get_task(task_id)["status"] not in {"created", "contracted"}),
            operator_priority=operator_priority,
            payload={"goal": request["goal"], "attachments": request["attachments"]},
        )
        if self.queue_backend_kind == "redis":
            self.queue_backend.enqueue(queue_item)
            self._refresh_backend_state()
        self._emit_telemetry(task_id, "task_queued", {"queue_item_id": queue_item.queue_item_id, "priority_class": priority_class})
        return queue_item

    def dispatch_next_queued_task(
        self,
        *,
        worker_id: str,
        interrupt_after: str | None = None,
    ) -> dict[str, object]:
        if self.repository.load_worker(worker_id) is None:
            self.register_worker(
                worker_id=worker_id,
                worker_role="worker",
                process_identity=worker_id,
                capabilities=WorkerCapabilityRecord(
                    version="1.0",
                    worker_id=worker_id,
                    provider_access=list(self.provider_manager.providers),
                    tool_access=["file_retrieval"],
                    role_specialization=["Researcher", "Builder", "Verifier", "Strategist", "Archivist"],
                    supports_degraded_mode=True,
                    supports_high_risk=True,
                    max_parallel_tasks=1,
                ),
            )
        self.heartbeat_worker(worker_id, active_leases=[], capacity_in_use=0)
        capacity = self._current_capacity_snapshot()
        health = self.provider_health.snapshot(list(self.provider_manager.providers))
        self.repository.save_provider_health_snapshot(health)
        if self.queue_backend_kind == "redis":
            dispatch = self._dispatch_via_external_queue(worker_id=worker_id, capacity_snapshot=capacity, provider_health=health)
        else:
            dispatch = self.queue.dispatch_next(
                worker_id=worker_id,
                capacity_snapshot=capacity,
                provider_health=health,
                system_mode=self.system_mode,
            )
        if dispatch is None:
            steal = self.attempt_work_steal(worker_id=worker_id)
            if steal is not None:
                if self.queue_backend_kind == "redis":
                    dispatch = self._dispatch_via_external_queue(
                        worker_id=worker_id,
                        capacity_snapshot=self._current_capacity_snapshot(),
                        provider_health=health,
                    )
                else:
                    dispatch = self.queue.dispatch_next(
                        worker_id=worker_id,
                        capacity_snapshot=self._current_capacity_snapshot(),
                        provider_health=health,
                        system_mode=self.system_mode,
                    )
                if dispatch is None:
                    return steal
            return {"status": "deferred" if self.repository.list_queue_items(statuses=["deferred"]) else "idle"}
        item, lease, decision, dispatch_record = dispatch
        ownership = self.coordination.claim_lease(
            lease_id=lease.lease_id,
            queue_item_id=item.queue_item_id,
            task_id=item.task_id,
            worker_id=worker_id,
            expires_at=lease.expires_at,
        )
        lease.fencing_token = ownership.fencing_token
        lease.lease_epoch = ownership.lease_epoch
        self.repository.save_queue_lease(lease)
        self.coordination.claim_dispatch(
            dispatch_id=dispatch_record.dispatch_id,
            task_id=item.task_id,
            queue_item_id=item.queue_item_id,
            lease_id=lease.lease_id,
            worker_id=worker_id,
            fencing_token=ownership.fencing_token,
        )
        self._bind_dispatch_context(worker_id=worker_id, lease_id=lease.lease_id, fencing_token=ownership.fencing_token)
        self.heartbeat_worker(worker_id, active_leases=[lease.lease_id], capacity_in_use=1)
        task = self.repository.get_task(item.task_id)
        try:
            if task is None:
                raise KeyError(item.task_id)
            if item.resume_task or task["status"] not in {"created", "contracted"}:
                result = self.resume_task(item.task_id, interrupt_after=interrupt_after)
            else:
                request = task["request"]
                result = self.run_task(
                    goal=str(request["goal"]),
                    attachments=list(request["attachments"]),
                    preferences=dict(request["preferences"]),
                    prohibitions=list(request["prohibitions"]),
                    task_id=item.task_id,
                    interrupt_after=interrupt_after,
                )
            self.queue_backend.acknowledge(
                lease_id=lease.lease_id,
                worker_id=worker_id,
                fencing_token=ownership.fencing_token,
            )
            self.coordination.release_lease(
                lease_id=lease.lease_id,
                worker_id=worker_id,
                fencing_token=ownership.fencing_token,
                reason="acknowledged",
            )
            self.heartbeat_worker(worker_id, active_leases=[], capacity_in_use=0)
            self._refresh_backend_state()
            return {
                "status": result.status,
                "task_id": result.task_id,
                "queue_item_id": item.queue_item_id,
                "lease_id": lease.lease_id,
                "dispatch_id": dispatch_record.dispatch_id,
            }
        except RuntimeInterrupted:
            queued = self.repository.get_queue_item(item.queue_item_id)
            if queued is not None:
                queued.resume_task = True
                self.repository.save_queue_item(queued)
            self.queue_backend.release(
                lease_id=lease.lease_id,
                worker_id=worker_id,
                fencing_token=ownership.fencing_token,
                reason="runtime interrupted",
                retryable=True,
            )
            self._refresh_backend_state()
            return {
                "status": "interrupted",
                "task_id": item.task_id,
                "queue_item_id": item.queue_item_id,
                "lease_id": lease.lease_id,
            }
        except Exception as exc:
            self.queue_backend.release(
                lease_id=lease.lease_id,
                worker_id=worker_id,
                fencing_token=ownership.fencing_token,
                reason=str(exc),
                retryable=True,
            )
            self._refresh_backend_state()
            return {
                "status": "failed",
                "task_id": item.task_id,
                "queue_item_id": item.queue_item_id,
                "lease_id": lease.lease_id,
                "error": str(exc),
            }
        finally:
            self._clear_dispatch_context()

    def recover_stale_queue_leases(self, *, force_expire: bool = False) -> int:
        recovered = self.queue.recover_stale_leases(force_expire=force_expire)
        if recovered:
            self._emit_telemetry("system", "queue_recovered", {"recovered_leases": recovered})
        return recovered

    def service_health(self) -> dict[str, object]:
        migration_version = self.repository.runner.current_version()
        queue_items = self.repository.list_queue_items()
        provider_health = self.provider_health.snapshot(list(self.provider_manager.providers))
        self.repository.save_provider_health_snapshot(provider_health)
        ready = migration_version is not None and self.system_mode != "maintenance"
        return {
            "live": True,
            "ready": ready and self.system_mode != "drain",
            "system_mode": self.system_mode,
            "migration_version": migration_version,
            "queue_depth": len([item for item in queue_items if item.status in {"queued", "deferred", "leased"}]),
            "provider_health": provider_health.to_dict(),
            "storage_ok": True,
            "worker_available": True,
            "shared_state_health": shared_health.to_dict() if (shared_health := self.shared_state_backend.health()) else None,
            "trust_mode": self.trust_mode,
        }

    def startup_validation_summary(self) -> dict[str, object]:
        migration_version = self.repository.runner.current_version()
        provider_names = list(self.provider_manager.providers)
        provider_policies = {
            provider_name: (
                None
                if self.repository.load_provider_availability_policy(provider_name) is None
                else self.repository.load_provider_availability_policy(provider_name).to_dict()
            )
            for provider_name in provider_names
        }
        return {
            "ok": migration_version is not None,
            "migration_version": migration_version,
            "storage_root": str(self.storage_root),
            "shared_state_backend": self.shared_state_backend.descriptor().to_dict(),
            "provider_names": provider_names,
            "provider_policies": provider_policies,
            "system_mode": self.system_mode,
            "trust_mode": self.trust_mode,
            "queue_policy": None
            if self.repository.load_queue_policy("default") is None
            else self.repository.load_queue_policy("default").to_dict(),
        }

    def graceful_shutdown(self, *, reason: str = "service shutdown requested") -> dict[str, object]:
        self._set_global_execution_mode("drain", reason, ["shutdown drain mode"])
        recovered = self.recover_stale_queue_leases(force_expire=True)
        self._emit_telemetry("system", "service_shutdown_prepared", {"reason": reason, "recovered_leases": recovered})
        return {
            "status": "draining",
            "reason": reason,
            "recovered_leases": recovered,
            "system_mode": self.system_mode,
        }

    def restart_recovery(self) -> dict[str, object]:
        recovered = self.recover_stale_queue_leases(force_expire=True)
        if self.system_mode == "drain":
            self._set_global_execution_mode("normal", "restart recovery complete", [])
        self._emit_telemetry("system", "service_restart_recovered", {"recovered_leases": recovered})
        return {
            "status": "ready",
            "recovered_leases": recovered,
            "system_mode": self.system_mode,
            "health": self.service_health(),
        }

    def apply_operator_override(
        self,
        *,
        action: str,
        operator: str,
        reason: str,
        payload: dict[str, str],
    ) -> OperatorOverrideRecord:
        idempotency_key = payload.get("idempotency_key", "")
        existing = self.repository.find_operator_override(idempotency_key)
        if existing is not None:
            return existing
        override = OperatorOverrideRecord(
            version="1.0",
            override_id=f"operator-override-{uuid4().hex[:10]}",
            action=action,
            scope=payload.get("scope", "system"),
            value=json.dumps(payload, ensure_ascii=True, sort_keys=True),
            operator=operator,
            status="active",
            idempotency_key=idempotency_key,
            reason=reason,
        )
        self.repository.save_operator_override(override)
        synthetic_task_id = payload.get("task_id", "system")
        self.intervene_task(
            task_id=synthetic_task_id,
            action=action,
            operator=operator,
            reason=reason,
            payload=payload,
        )
        return override

    def queue_status(self) -> dict[str, object]:
        queue_items = self.repository.list_queue_items()
        return {
            "queued_tasks": len([item for item in queue_items if item.status == "queued"]),
            "deferred_tasks": len([item for item in queue_items if item.status == "deferred"]),
            "leased_tasks": len([item for item in queue_items if item.status == "leased"]),
            "dead_letter_tasks": len([item for item in queue_items if item.status == "dead_letter"]),
            "items": [item.to_dict() for item in queue_items],
            "admission_decisions": [item.to_dict() for item in self.repository.list_admission_decisions()],
            "dispatch_records": [item.to_dict() for item in self.repository.list_dispatch_records()],
            "lease_ownerships": [item.to_dict() for item in self.repository.list_lease_ownerships()],
            "work_steal_decisions": [item.to_dict() for item in self.repository.list_work_steal_decisions()],
            "latest_capacity_snapshot": None
            if self.repository.latest_capacity_snapshot() is None
            else self.repository.latest_capacity_snapshot().to_dict(),
        }

    def provider_health_state(self) -> dict[str, object]:
        snapshot = self.provider_health.snapshot(list(self.provider_manager.providers))
        self.repository.save_provider_health_snapshot(snapshot)
        fairness = self.provider_pool.fairness_snapshot()
        return {
            "records": [item.to_dict() for item in snapshot.records],
            "rate_limit_states": [
                item.to_dict()
                for provider_name in self.provider_manager.providers
                if (item := self.repository.load_rate_limit_state(provider_name)) is not None
            ],
            "cooldown_windows": [
                item.to_dict()
                for provider_name in self.provider_manager.providers
                if (item := self.repository.load_provider_cooldown_window(provider_name)) is not None
            ],
            "degradation_events": [item.to_dict() for item in self.repository.list_provider_degradation_events()],
            "availability_policies": [item.to_dict() for item in self.repository.list_provider_availability_policies()],
            "provider_pool_state": None
            if self.repository.latest_provider_pool_state() is None
            else self.repository.latest_provider_pool_state().to_dict(),
            "provider_pressure_snapshot": None
            if self.repository.latest_provider_pressure_snapshot() is None
            else self.repository.latest_provider_pressure_snapshot().to_dict(),
            "provider_capacity_records": [item.to_dict() for item in self.repository.list_provider_capacity_records()],
            "provider_reservations": [item.to_dict() for item in self.repository.list_provider_reservations()],
            "provider_balance_decisions": [item.to_dict() for item in self.repository.list_provider_balance_decisions()],
            "provider_fairness_records": [item.to_dict() for item in fairness],
            "provider_demand_forecasts": [item.to_dict() for item in self.repository.list_provider_demand_forecasts()],
            "provider_capacity_forecasts": [item.to_dict() for item in self.repository.list_provider_capacity_forecasts()],
            "provider_quota_policies": [item.to_dict() for item in self.repository.list_provider_quota_policies()],
            "quota_exhaustion_risks": [item.to_dict() for item in self.repository.list_quota_exhaustion_risks()],
            "quota_governance_decisions": [item.to_dict() for item in self.repository.list_quota_governance_decisions()],
        }

    def policy_registry_state(self) -> dict[str, object]:
        return {
            "scopes": [item.to_dict() for item in self.repository.list_policy_scopes()],
            "active_versions": [
                item.to_dict()
                for scope in self.repository.list_policy_scopes()
                for item in self.repository.list_policy_versions(scope.scope_id)
                if item.status == "active"
            ],
            "candidates": [item.to_dict() for item in self.repository.list_policy_candidates()],
            "promotion_runs": [item.to_dict() for item in self.repository.list_policy_promotion_runs()],
            "rollbacks": [item.to_dict() for item in self.repository.list_policy_rollback_records()],
        }

    def system_governance_state(self) -> dict[str, object]:
        latest_mode = self.repository.latest_global_execution_mode()
        latest_capacity = self.repository.latest_capacity_snapshot()
        self._refresh_backend_state()
        return {
            "global_execution_mode": None if latest_mode is None else latest_mode.to_dict(),
            "capacity_snapshot": None if latest_capacity is None else latest_capacity.to_dict(),
            "queue_status": self.queue_status(),
            "provider_health": self.provider_health_state(),
            "operator_overrides": [item.to_dict() for item in self.repository.list_operator_overrides()],
            "dominant_constraints": [] if latest_mode is None else latest_mode.active_constraints,
            "approval_backlog": 0 if latest_capacity is None else latest_capacity.approval_backlog,
            "recovery_reservations": 0 if latest_capacity is None else latest_capacity.recovery_reservations,
            "budget_pressure": 0.0 if latest_capacity is None else latest_capacity.budget_pressure,
            "worker_registry": [item.to_dict() for item in self.repository.list_workers()],
            "hosts": [item.to_dict() for item in self.repository.list_host_records()],
            "worker_bindings": [item.to_dict() for item in self.repository.list_worker_host_bindings()],
            "worker_endpoints": [item.to_dict() for item in self.repository.list_worker_endpoints()],
            "worker_pressure_snapshot": None
            if self.repository.latest_worker_pressure_snapshot() is None
            else self.repository.latest_worker_pressure_snapshot().to_dict(),
            "backend_state": {
                "queue_backend": self.queue_backend.descriptor().to_dict(),
                "coordination_backend": self.coordination.descriptor().to_dict(),
                "shared_state_backend": self.shared_state_backend.descriptor().to_dict(),
                "health_records": [item.to_dict() for item in self.repository.list_backend_health_records()],
                "pressure_snapshots": [item.to_dict() for item in self.repository.list_backend_pressure_snapshots()],
            },
            "reliability": {
                "incidents": [item.to_dict() for item in self.repository.list_reliability_incidents()],
                "reconciliation_runs": [item.to_dict() for item in self.repository.list_reconciliation_runs()],
                "backend_outages": [item.to_dict() for item in self.repository.list_backend_outage_records()],
            },
            "security": {
                "trust_mode": self.trust_mode,
                "trust_policies": [item.to_dict() for item in self.repository.list_service_trust_policies()],
                "security_incidents": [item.to_dict() for item in self.repository.list_security_incidents()],
            },
        }

    def system_report(self) -> dict[str, object]:
        queue = self.queue_status()
        providers = self.provider_health_state()
        governance = self.system_governance_state()
        latest_task_id = None
        tasks = self.repository.list_tasks()
        if tasks:
            latest_task_id = str(tasks[-1]["task_id"])
        memory_summary = {
            "write_receipt_count": len(self.memory.list_memory_write_receipts()),
            "evidence_pack_count": len(self.repository.list_memory_evidence_packs()),
            "deletion_receipt_count": len(self.memory.list_memory_deletion_receipts()),
            "maintenance_mode": None if latest_task_id is None else self.memory.maintenance_mode(scope_key=latest_task_id),
            "controller_versions": {
                "admission": max(
                    ["v1", *[item.controller_version for item in self.memory.list_admission_canary_runs()]],
                    key=lambda item: item,
                ),
                "repair": max(
                    ["v1", *[item.controller_version for item in self.memory.list_repair_canary_runs()]],
                    key=lambda item: item,
                ),
                "maintenance": max(
                    ["v1", *[item.controller_version for item in self.memory.list_memory_maintenance_canary_runs()]],
                    key=lambda item: item,
                ),
            },
        }
        software_receipts = self.repository.list_software_action_receipts()
        failure_patterns = self.repository.list_software_failure_patterns()
        software_summary = {
            "harness_count": len(self.list_cli_anything_harnesses()),
            "action_receipt_count": len(software_receipts),
            "failure_pattern_count": len(failure_patterns),
            "risk_distribution": {
                level: len([item for item in software_receipts if item.risk_level == level])
                for level in ["low", "high", "destructive", "blocked"]
            },
        }
        bottlenecks: list[str] = []
        if queue["deferred_tasks"]:
            bottlenecks.append("queue has deferred tasks awaiting capacity or policy relief")
        if queue["leased_tasks"]:
            bottlenecks.append("active leases are consuming worker capacity")
        if governance["budget_pressure"] and float(governance["budget_pressure"]) >= 0.2:
            bottlenecks.append("budget pressure is constraining admission or routing")
        degraded = [item["provider_name"] for item in providers["records"] if item["availability_state"] != "available"]
        if degraded:
            bottlenecks.append(f"providers under pressure: {', '.join(sorted(degraded))}")
        if not bottlenecks:
            bottlenecks.append("no dominant system bottleneck detected")
        return {
            "summary": {
                "system_mode": self.system_mode,
                "queued_tasks": queue["queued_tasks"],
                "deferred_tasks": queue["deferred_tasks"],
                "leased_tasks": queue["leased_tasks"],
                "budget_pressure": governance["budget_pressure"],
            },
            "bottlenecks": bottlenecks,
            "queue": queue,
            "providers": providers,
            "governance": governance,
            "memory": memory_summary,
            "software_control": software_summary,
        }

    def _capture_metrics_snapshot(self, report: dict[str, object]) -> ObservabilityMetricSnapshot:
        snapshot = ObservabilityMetricSnapshot(
            version="1.0",
            snapshot_id=f"observability-snapshot-{uuid4().hex[:10]}",
            scope_key="global",
            runtime_summary=dict(report["summary"]),
            controller_versions=dict(report["amos"]["controller_versions"]),
            maintenance_summary=dict(report["maintenance"]),
            software_control_summary=dict(report["software_control"]),
            created_at=utc_now(),
        )
        self.repository.save_observability_metric_snapshot(snapshot)
        if int(report["maintenance"]["incident_count"]) > 0 or int(report["maintenance"]["repair_backlog_count"]) > 0:
            self.repository.save_observability_alert_record(
                ObservabilityAlertRecord(
                    version="1.0",
                    alert_id=f"observability-alert-{uuid4().hex[:10]}",
                    scope_key="global",
                    severity="warning",
                    category="maintenance",
                    summary="Maintenance incidents or repair backlog are non-zero.",
                    created_at=utc_now(),
                )
            )
        return snapshot

    def _maintenance_incident_recommendations(self, *, scope_key: str) -> list[MaintenanceIncidentRecommendation]:
        existing = self.repository.list_maintenance_incident_recommendations(scope_key)
        seen = {item.incident_id for item in existing}
        for incident in self.memory.list_memory_maintenance_incidents(scope_key=scope_key):
            if incident.incident_id in seen or incident.status == "resolved":
                continue
            record = MaintenanceIncidentRecommendation(
                version="1.0",
                recommendation_id=f"maintenance-incident-recommendation-{uuid4().hex[:10]}",
                scope_key=scope_key,
                incident_id=incident.incident_id,
                recommended_actions=["review_incident", "run_background_maintenance", "verify_repair_backlog"],
                rationale=f"Incident {incident.incident_kind} is still {incident.status} and should stay operator-visible until resolved.",
                created_at=utc_now(),
            )
            self.repository.save_maintenance_incident_recommendation(record)
            existing.append(record)
        return existing

    def metrics_report(self) -> dict[str, object]:
        system = self.system_report()
        mode_counts: dict[str, int] = {}
        for task in self.repository.list_tasks():
            task_id = str(task["task_id"])
            mode = str(self.memory.maintenance_mode(scope_key=task_id)["mode"])
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
        repair_backlog_count = len(
            [item for item in self.memory.list_memory_contradiction_repairs() if item.repair_status == "recommended"]
        )
        purge_history = {
            "tombstone": len(self.memory.list_memory_deletion_runs()),
            "selective_purge": len(self.memory.list_selective_purge_runs()),
            "hard_purge": len(self.memory.list_hard_purge_runs()),
        }
        rebuild_history = {
            "full_rebuild": len(self.repository.list_memory_rebuild_runs()),
            "selective_rebuild": len(self.memory.list_selective_rebuild_runs()),
        }
        report = build_system_metrics_report(
            summary=system["summary"],
            memory=system["memory"],
            software_control=system["software_control"],
            maintenance_mode_counts=mode_counts or {"normal": 0},
            maintenance_incident_count=len(self.memory.list_memory_maintenance_incidents()),
            repair_backlog_count=repair_backlog_count,
            purge_history=purge_history,
            rebuild_history=rebuild_history,
        )
        self._capture_metrics_snapshot(report)
        return report

    def metrics_history(self, *, window_hours: int = 24) -> dict[str, object]:
        cutoff = utc_now() - timedelta(hours=window_hours)
        snapshots = [item for item in self.repository.list_observability_metric_snapshots("global") if item.created_at >= cutoff]
        latest = None if not snapshots else snapshots[0]
        counters = {
            "snapshot_count": float(len(snapshots)),
            "maintenance_incident_count": 0.0 if latest is None else float(latest.maintenance_summary.get("incident_count", 0)),
            "software_action_receipt_count": 0.0 if latest is None else float(latest.software_control_summary.get("action_receipt_count", 0)),
            "repair_backlog_count": 0.0 if latest is None else float(latest.maintenance_summary.get("repair_backlog_count", 0)),
        }
        trend = ObservabilityTrendReport(
            version="1.0",
            report_id=f"observability-trend-{uuid4().hex[:10]}",
            scope_key="global",
            window_hours=window_hours,
            snapshot_ids=[item.snapshot_id for item in snapshots],
            counters=counters,
            latest_snapshot_at=None if latest is None else latest.created_at,
            created_at=utc_now(),
        )
        self.repository.save_observability_trend_report(trend)
        return {
            "summary": {
                "window_hours": window_hours,
                "snapshot_count": len(snapshots),
                "latest_snapshot_at": None if latest is None else latest.created_at.isoformat(),
            },
            "items": [item.to_dict() for item in snapshots],
            "counters": counters,
            "alerts": [item.to_dict() for item in self.repository.list_observability_alert_records("global")],
            "prometheus_preview": self.prometheus_metrics(),
        }

    def prometheus_metrics(self) -> str:
        snapshots = self.repository.list_observability_metric_snapshots("global")
        if not snapshots:
            self.metrics_report()
            snapshots = self.repository.list_observability_metric_snapshots("global")
        latest = snapshots[0]
        lines = [
            "# HELP ceos_observability_snapshot_count Number of persisted operator metric snapshots.",
            "# TYPE ceos_observability_snapshot_count gauge",
            f"ceos_observability_snapshot_count {len(snapshots)}",
            "# HELP ceos_maintenance_incident_count Current maintenance incident count from the latest snapshot.",
            "# TYPE ceos_maintenance_incident_count gauge",
            f"ceos_maintenance_incident_count {int(latest.maintenance_summary.get('incident_count', 0))}",
            "# HELP ceos_repair_backlog_count Current AMOS repair backlog count from the latest snapshot.",
            "# TYPE ceos_repair_backlog_count gauge",
            f"ceos_repair_backlog_count {int(latest.maintenance_summary.get('repair_backlog_count', 0))}",
            "# HELP ceos_software_action_receipt_count Current governed software action receipt count from the latest snapshot.",
            "# TYPE ceos_software_action_receipt_count gauge",
            f"ceos_software_action_receipt_count {int(latest.software_control_summary.get('action_receipt_count', 0))}",
        ]
        return "\n".join(lines) + "\n"

    def maintenance_report(self, *, task_id: str | None = None) -> dict[str, object]:
        recommendations = [] if task_id is None else self._maintenance_incident_recommendations(scope_key=task_id)
        return {
            "task_id": task_id,
            "report": {
                "mode": None if task_id is None else self.memory.maintenance_mode(scope_key=task_id),
                "workers": [item.to_dict() for item in self.memory.list_memory_maintenance_workers()],
                "leases": [item.to_dict() for item in self.repository.list_maintenance_worker_lease_states()],
                "daemon_runs": [item.to_dict() for item in self.repository.list_maintenance_daemon_runs()],
                "recommendations": [item.to_dict() for item in recommendations],
                "incidents": [
                    item.to_dict()
                    for item in (
                        self.memory.list_memory_maintenance_incidents(scope_key=task_id)
                        if task_id is not None
                        else self.memory.list_memory_maintenance_incidents()
                    )
                ],
                "resolution_analytics": [
                    item.to_dict()
                    for item in (
                        self.repository.list_maintenance_resolution_analytics(task_id)
                        if task_id is not None
                        else self.repository.list_maintenance_resolution_analytics()
                    )
                ],
            },
        }

    def software_control_report(self) -> dict[str, object]:
        manifests = [RuntimeService.software_harness_report(self, harness_id=item.harness_id)["manifest"] for item in self.list_cli_anything_harnesses()]
        action_receipts = [item.to_dict() for item in self.repository.list_software_action_receipts()]
        replay_records = [item.to_dict() for item in self.repository.list_software_replay_records()]
        failure_patterns = [item.to_dict() for item in self.repository.list_software_failure_patterns()]
        replay_diagnostics = [item.to_dict() for item in self.repository.list_software_replay_diagnostics()]
        recovery_hints = [item.to_dict() for item in self.repository.list_software_recovery_hints()]
        failure_clusters = [item.to_dict() for item in self.repository.list_software_failure_clusters()]
        macros = [item.to_dict() for item in self.repository.list_software_automation_macros()]
        summary = {
            "harness_count": len(manifests),
            "action_receipt_count": len(action_receipts),
            "replay_count": len(replay_records),
            "failure_pattern_count": len(failure_patterns),
            "replay_diagnostic_count": len(replay_diagnostics),
            "recovery_hint_count": len(recovery_hints),
            "failure_cluster_count": len(failure_clusters),
            "macro_count": len(macros),
            "risk_distribution": {
                level: len([item for item in action_receipts if item["risk_level"] == level])
                for level in ["low", "high", "destructive", "blocked"]
            },
        }
        report = build_software_control_report(
            summary=summary,
            manifests=manifests,
            action_receipts=action_receipts,
            replay_records=replay_records,
            failure_patterns=failure_patterns,
        )
        report["replay_diagnostics"] = replay_diagnostics
        report["recovery_hints"] = recovery_hints
        report["failure_clusters"] = failure_clusters
        report["macros"] = macros
        return report

    def maintenance_daemon_state(self, *, task_id: str | None = None) -> dict[str, object]:
        return {
            "task_id": task_id,
            "daemon": {
                "runs": [item.to_dict() for item in self.repository.list_maintenance_daemon_runs()],
                "workers": [item.to_dict() for item in self.memory.list_memory_maintenance_workers()],
                "leases": [item.to_dict() for item in self.repository.list_maintenance_worker_lease_states()],
                "incidents": [
                    item.to_dict()
                    for item in (
                        self.memory.list_memory_maintenance_incidents(scope_key=task_id)
                        if task_id is not None
                        else self.memory.list_memory_maintenance_incidents()
                    )
                ],
                "recommendations": [] if task_id is None else [item.to_dict() for item in self._maintenance_incident_recommendations(scope_key=task_id)],
            },
        }

    def run_resident_maintenance_daemon(
        self,
        *,
        worker_id: str,
        host_id: str,
        actor: str,
        task_id: str | None = None,
        daemon: bool = False,
        once: bool = False,
        poll_interval_seconds: int = 0,
        heartbeat_seconds: int = 30,
        lease_seconds: int = 300,
        max_cycles: int = 1,
        cycles: int | None = None,
        interrupt_after: str | None = None,
    ) -> dict[str, object]:
        worker = next((item for item in self.memory.list_memory_maintenance_workers() if item.worker_id == worker_id), None)
        if worker is None:
            worker = self.memory.register_maintenance_worker(worker_id=worker_id, host_id=host_id, actor=actor)
        started_at = utc_now()
        reclaimed_workers = []
        runs = []
        cycles_to_run = 1 if once else max(1, max_cycles if cycles is None else cycles)
        for cycle_index in range(cycles_to_run):
            self.memory.heartbeat_maintenance_worker(worker_id=worker_id, current_mode="daemon_running")
            reclaimed_workers.extend(
                self.memory.reclaim_stale_maintenance_workers(
                    heartbeat_expiry_seconds=heartbeat_seconds * 2,
                )
            )
            recoveries = [
                item
                for item in self.memory.list_memory_maintenance_recoveries(scope_key=task_id)
                if task_id is not None
            ] if task_id is not None else self.memory.list_memory_maintenance_recoveries()
            for recovery in recoveries:
                if recovery.status != "pending":
                    continue
                resumed = self.resume_background_maintenance(
                    run_id=recovery.maintenance_run_id,
                    actor=actor,
                    reason="resident maintenance daemon resumed interrupted run",
                )
                runs.append(resumed)
            runs.extend(
                RuntimeService.run_maintenance_worker_cycle(
                    self,
                    worker_id=worker_id,
                    interrupt_after=interrupt_after,
                    lease_seconds=lease_seconds,
                )
            )
            if daemon and poll_interval_seconds > 0 and cycle_index < cycles_to_run - 1:
                time.sleep(poll_interval_seconds)
        worker = next(item for item in self.memory.list_memory_maintenance_workers() if item.worker_id == worker_id)
        claimed_schedules = [
            item
            for item in self.memory.list_memory_maintenance_schedules()
            if item.claimed_by_worker_id == worker_id and item.lease_expires_at is not None
        ]
        lease_state = MaintenanceWorkerLeaseState(
            version="1.0",
            lease_state_id=f"maintenance-lease-state-{uuid4().hex[:10]}",
            worker_id=worker_id,
            host_id=host_id,
            claimed_schedule_ids=[item.schedule_id for item in claimed_schedules],
            lease_seconds=lease_seconds,
            stale=worker.status == "stale",
            captured_at=utc_now(),
            lease_expires_at=None if not claimed_schedules else max(item.lease_expires_at for item in claimed_schedules),
        )
        self.repository.save_maintenance_worker_lease_state(lease_state)
        daemon_run = MaintenanceDaemonRun(
            version="1.0",
            daemon_run_id=f"maintenance-daemon-run-{uuid4().hex[:10]}",
            worker_id=worker_id,
            host_id=host_id,
            actor=actor,
            daemon_mode=daemon,
            poll_interval_seconds=poll_interval_seconds,
            heartbeat_seconds=heartbeat_seconds,
            lease_seconds=lease_seconds,
            cycles_completed=cycles_to_run,
            started_at=started_at,
            completed_at=utc_now(),
            maintenance_run_ids=[item.run_id for item in runs],
            reclaimed_worker_ids=sorted({item.worker_id for item in reclaimed_workers}),
            status="completed",
            interrupted_phase=interrupt_after,
        )
        self.repository.save_maintenance_daemon_run(daemon_run)
        unique_reclaimed = {item.worker_id: item for item in reclaimed_workers}
        if task_id is not None:
            self._maintenance_incident_recommendations(scope_key=task_id)
        self.metrics_report()
        return {
            "worker": worker.to_dict(),
            "daemon": daemon_run.to_dict(),
            "lease_state": lease_state.to_dict(),
            "runs": [item.to_dict() for item in runs],
            "reclaimed_workers": [item.to_dict() for item in unique_reclaimed.values()],
            "summary": {
                "cycles_completed": cycles_to_run,
                "run_count": len(runs),
                "stale_worker_count": len(unique_reclaimed),
            },
        }

    def record_backend_outage(self, *, backend_name: str, fault_domain: str, summary: str) -> dict[str, object]:
        record = self.reliability_manager.record_backend_outage(
            backend_name=backend_name,
            fault_domain=fault_domain,
            summary=summary,
        )
        self._set_global_execution_mode("degraded", summary, [fault_domain])
        return record.to_dict()

    def run_reconciliation(self, *, reason: str) -> dict[str, object]:
        run = self.reliability_manager.run_reconciliation(reason=reason)
        return run.to_dict()

    def propose_policy_candidate_from_runtime(
        self,
        *,
        name: str,
        hypothesis: str,
        policy_payload: dict[str, object],
        scope_id: str = "policy-scope-routing",
    ):
        try:
            scope = self.repository.load_policy_scope(scope_id)
        except KeyError:
            scope = PolicyScope(
                version="1.0",
                scope_id=scope_id,
                scope_type="routing",
                target_component="provider_selection",
                constraints=["no_policy_boundary_violation"],
            )
        versions = self.repository.list_policy_versions(scope.scope_id)
        base_version = versions[-1] if versions else self.policy_registry.register_policy_version(
            name="routing-default",
            scope=scope,
            policy_payload={"execution_mode": "standard", "prefer_low_cost": False},
            summary="Default routing policy.",
        )
        evidence = self.policy_registry.build_evidence_bundle(
            scope=scope,
            source_refs=[
                *[f"provider_scorecard:{item.provider_name}:{item.profile}" for item in self.repository.list_provider_scorecards()],
                *[f"routing_decision:{item.decision_id}" for item in self.repository.list_routing_decisions(task_id=next(iter([task['task_id'] for task in self.repository.list_tasks()]), ''))],
                *[f"budget_event:{item.event_id}" for item in self.repository.list_budget_events(next(iter([task['task_id'] for task in self.repository.list_tasks()]), ''))],
            ],
            summary="Candidate mined from runtime scorecards and recent routing/budget traces.",
        )
        return self.policy_registry.propose_candidate_from_evidence(
            name=name,
            scope=scope,
            base_version_id=base_version.version_id,
            policy_payload={str(key): value for key, value in policy_payload.items()},
            evidence_bundle=evidence,
            hypothesis=hypothesis,
        )

    def evaluate_policy_candidate(self, candidate_id: str, report) -> object:
        return self.policy_registry.evaluate_candidate(candidate_id, report=report)

    def promote_policy_candidate(self, candidate_id: str) -> object:
        return self.policy_registry.promote_candidate(candidate_id)

    def rollback_policy_scope(self, scope_id: str, reason: str) -> object:
        return self.policy_registry.rollback_scope(scope_id, reason=reason)

    def resume_task(self, task_id: str, interrupt_after: str | None = None, role_name: str = "Strategist"):
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        if task["status"] in {"completed", "blocked", "failed"}:
            replay = self.replay_task(task_id)
            return self._result_from_replay(task_id, replay)
        working_set = None
        if self.repository.latest_handoff_packet(task_id) is not None:
            working_set = self.continuity.reconstruct_working_set(task_id, role_name)
            self._emit_telemetry(
                task_id,
                "task_resumed",
                {"role_name": role_name, "working_set_id": working_set.working_set_id},
            )
        request = task["request"]
        previous_strategy = self.routing_strategy
        if working_set is not None and working_set.recommended_strategy:
            self.routing_strategy = working_set.recommended_strategy
        try:
            result = self.run_task(
                goal=str(request["goal"]),
                attachments=list(request["attachments"]),
                preferences=dict(request["preferences"]),
                prohibitions=list(request["prohibitions"]),
                task_id=task_id,
                interrupt_after=interrupt_after,
            )
        finally:
            self.routing_strategy = previous_strategy
        if working_set is not None and result.continuity_working_set is None:
            result.continuity_working_set = working_set
        return result

    def replay_task(self, task_id: str) -> dict[str, object]:
        return self.repository.replay_task(task_id)

    def evidence_lineage(self, task_id: str, node_id: str) -> dict[str, list[object]]:
        return self.repository.evidence_lineage(task_id, node_id)

    def incident_packet(self, task_id: str) -> dict[str, object]:
        return self.repository.incident_packet(task_id)

    def export_artifacts(self, task_id: str) -> Path:
        replay = self.replay_task(task_id)
        output_path = self.storage_root / f"{task_id}-delivery.json"
        output_path.write_text(json.dumps(replay["delivery"], ensure_ascii=True, indent=2), encoding="utf-8")
        self.memory.register_artifact(
            scope_key=task_id,
            artifact_kind="delivery_export",
            path=str(output_path),
            source_run_id=f"export-{task_id}",
        )
        return output_path

    def _ensure_contract(self, task_id: str, request: dict[str, object]) -> TaskContract:
        task = self.repository.get_task(task_id)
        if task is not None and task["contract_id"] is not None:
            return self.repository.load_contract(str(task["contract_id"]))
        contract = self.compile_contract(
            str(request["goal"]),
            list(request["attachments"]),
            dict(request["preferences"]),
            list(request["prohibitions"]),
        )
        self.repository.save_contract(task_id, contract)
        self._persist_task_state(
            task_id=task_id,
            status="contracted",
            current_phase="contracted",
            request=request,
            contract_id=contract.contract_id,
        )
        self._audit_event(
            task_id=task_id,
            contract_id=contract.contract_id,
            event_type="contract_compiled",
            actor="Strategist",
            why="Compile raw goal into a verifiable contract",
            risk_level=contract.risk_level,
            result="success",
        )
        return contract

    def _ensure_lattice(self, task_id: str, contract: TaskContract) -> ContractLattice:
        lattice = self.repository.load_contract_lattice(task_id)
        if lattice is not None:
            return lattice
        lattice = self.lattice_manager.create_root(contract)
        self.repository.save_contract_lattice(task_id, lattice)
        return lattice

    def _ensure_plan(self, task_id: str, contract: TaskContract, request: dict[str, object]) -> PlanGraph:
        plan = self.repository.load_plan(task_id)
        lattice = self.repository.load_contract_lattice(task_id)
        if plan is not None:
            return plan
        plan = self.generate_plan(contract, list(request["attachments"]))
        plan.graph_id = f"plan-{task_id}"
        for index, edge in enumerate(plan.edges):
            edge.edge_id = f"{task_id}-edge-{index}"
        if lattice is None:
            lattice = self.lattice_manager.create_root(contract)
        for node in plan.nodes:
            subcontract = self.compiler.derive_subcontract(contract, node.objective)
            self.repository.save_contract(task_id, subcontract)
            lattice = self.lattice_manager.attach_subcontract(lattice, contract, subcontract)
        self.repository.save_contract_lattice(task_id, lattice)
        self.repository.save_plan(task_id, plan)
        if not self.repository.list_execution_branches(task_id):
            self.repository.save_execution_branch(
                ExecutionBranch(
                    version="1.0",
                    branch_id=plan.active_branch_id,
                    task_id=task_id,
                    plan_graph_id=plan.graph_id,
                    parent_branch_id=None,
                    label="Primary execution branch",
                    status="active",
                    selected=True,
                    cause="initial_plan",
                    node_ids=[node.node_id for node in plan.nodes if node.branch_id == plan.active_branch_id],
                    created_at=utc_now(),
                )
            )
        self._persist_task_state(
            task_id=task_id,
            status="planned",
            current_phase="planned",
            request=request,
            contract_id=contract.contract_id,
            plan_graph_id=plan.graph_id,
        )
        self._audit_event(
            task_id=task_id,
            contract_id=contract.contract_id,
            event_type="plan_generated",
            actor="Strategist",
            why="Generate plan graph and contract lattice",
            risk_level=contract.risk_level,
            result="success",
        )
        checkpoint = self.checkpoint_task(
            task_id,
            "node-plan-generated",
            {
                "phase": "planned",
                "plan_graph_id": plan.graph_id,
                "pending_nodes": [node.node_id for node in plan.nodes if node.status != "completed"],
            },
        )
        self._persist_task_state(
            task_id=task_id,
            status="planned",
            current_phase="planned",
            request=request,
            contract_id=contract.contract_id,
            plan_graph_id=plan.graph_id,
            latest_checkpoint_id=checkpoint.checkpoint_id,
        )
        self._refresh_long_horizon_state(
            task_id=task_id,
            contract=contract,
            plan=plan,
            lattice=lattice,
            evidence=self._load_evidence(task_id),
            checkpoint_id=checkpoint.checkpoint_id,
        )
        self._save_scheduler_state(task_id, plan, status="ready")
        self._emit_telemetry(task_id, "plan_generated", {"plan_graph_id": plan.graph_id, "checkpoint_id": checkpoint.checkpoint_id})
        return plan

    def _load_evidence(self, task_id: str) -> EvidenceBuilder:
        graph = self.repository.load_evidence_graph(task_id)
        claims = self.repository.load_claims(task_id)
        return EvidenceBuilder(graph=graph, claims=claims)

    def _ensure_software_control_task_request(
        self,
        *,
        task_id: str | None,
        harness: SoftwareHarnessRecord,
        command_path: list[str],
        arguments: list[str],
    ) -> dict[str, object]:
        if task_id is not None:
            task = self.repository.get_task(task_id)
            if task is not None:
                return task["request"]
        goal = f"Use CLI-Anything harness {harness.software_name} to run {' '.join(command_path + arguments)}."
        return self.create_task(
            goal=goal,
            attachments=[],
            preferences={"output_style": "software_control", "max_cost": "0.5"},
            prohibitions=["Do not bypass approval for destructive software-control actions."],
            task_id=task_id,
        )

    def _record_software_control_evidence(
        self,
        *,
        task_id: str,
        harness: SoftwareHarnessRecord,
        command_path: list[str],
        result: ToolResult,
        parsed: dict[str, object] | None,
        evidence: EvidenceBuilder,
    ) -> list[str]:
        snippet = ""
        if isinstance(parsed, dict):
            snippet = json.dumps(parsed, ensure_ascii=True, sort_keys=True)[:400]
        elif isinstance(result.output_payload.get("stdout"), str):
            snippet = str(result.output_payload.get("stdout", ""))[:400]
        if not snippet:
            return []
        source = SourceRecord(
            version="1.0",
            source_id=f"source-{uuid4().hex[:10]}",
            source_type="cli_anything_command",
            locator=f"{harness.executable_name}:{' '.join(command_path)}",
            retrieved_at=utc_now(),
            credibility=0.9 if result.status == "success" else 0.6,
            time_relevance=1.0,
            content_hash=hashlib.sha256(snippet.encode("utf-8")).hexdigest(),
            snippet=snippet,
        )
        source_node = evidence.add_source(source)
        statements: list[str] = []
        if isinstance(parsed, dict):
            for key, value in list(parsed.items())[:5]:
                if isinstance(value, (str, int, float, bool)):
                    statements.append(f"{key}: {value}")
        if not statements:
            statements.append(snippet[:160])
        extractions = evidence.add_extractions(source_node, statements)
        self.repository.save_source_record(task_id, source)
        self.repository.save_evidence_graph(task_id, evidence.graph, evidence.claims)
        return [source_node.node_id] + [item.node_id for item in extractions]

    def _request_software_control_approval(
        self,
        *,
        task_id: str,
        contract: TaskContract,
        harness: SoftwareHarnessRecord,
        command_path: list[str],
        reason: str,
    ) -> ApprovalRequest:
        plan_node_id = f"software-control:{harness.software_name}:{'-'.join(command_path)}"
        existing = [
            request
            for request in self.repository.list_approval_requests(task_id=task_id)
            if request.plan_node_id == plan_node_id and request.status == "pending"
        ]
        if existing:
            return existing[-1]
        request = ApprovalRequest(
            version="1.0",
            request_id=f"approval-{uuid4().hex[:10]}",
            contract_id=contract.contract_id,
            action="software_control_review",
            reason=reason,
            requested_scope=["software_control_review"],
            risk_level="high",
            status="pending",
            task_id=task_id,
            plan_node_id=plan_node_id,
            action_summary=f"Approve {harness.software_name} command {' '.join(command_path)}",
            risk_classification="high",
            relevant_contract_clause="destructive software control commands require explicit approval",
            relevant_evidence=[],
            alternatives_considered=["deny and keep the command blocked", "request a safer software control path"],
            if_denied="The software control action remains blocked.",
            expiry_at=utc_now() + timedelta(hours=1),
        )
        self.repository.save_approval_request(request)
        return request

    def software_control_tool_shell(self) -> FileRetrievalTool | object:
        if not hasattr(self, "_software_control_shell"):
            from contract_evidence_os.tools.shell.tool import ShellPatchTool

            self._software_control_shell = ShellPatchTool()
        return self._software_control_shell

    def _build_delivery(self, evidence: EvidenceBuilder) -> dict[str, object]:
        facts = [
            {"statement": claim.statement, "evidence_refs": claim.evidence_refs, "status": claim.status}
            for claim in evidence.claims
        ]
        inferences = []
        if any("approval" in fact["statement"].lower() for fact in facts):
            inferences.append(
                {
                    "statement": "The task includes governance-sensitive actions.",
                    "basis": [fact["evidence_refs"][0] for fact in facts if "approval" in fact["statement"].lower()],
                }
            )
        return {"facts": facts, "inferences": inferences, "unresolved": []}

    def _approval_wait_if_needed(
        self,
        task_id: str,
        contract: TaskContract,
        node: PlanNode,
        evidence: EvidenceBuilder,
        plan: PlanGraph,
        lattice: ContractLattice,
    ) -> IncidentReport | None:
        if node.approval_gate is None:
            return None
        requests = [request for request in self.repository.list_approval_requests(task_id=task_id) if request.plan_node_id == node.node_id]
        if any(request.status == "approved" for request in requests):
            if node.status == "blocked":
                node.status = "pending"
                self.repository.update_plan_node_status(task_id, node.node_id, "pending")
            return None
        if any(request.status == "denied" for request in requests):
            return self.recovery.classify_failure(task_id, "approval_denied", f"Approval denied for {node.objective}")

        approval_request = self._ensure_approval_request(task_id, contract, node, evidence)
        node.status = "blocked"
        self.repository.update_plan_node_status(task_id, node.node_id, "blocked")
        checkpoint = self.checkpoint_task(
            task_id,
            node.node_id,
            {"phase": "approval_wait", "node_id": node.node_id, "approval_request_id": approval_request.request_id},
        )
        task = self.repository.get_task(task_id)
        request = {"task_id": task_id} if task is None else task["request"]
        self._persist_task_state(
            task_id=task_id,
            status="awaiting_approval",
            current_phase="awaiting_approval",
            request=request,
            contract_id=contract.contract_id,
            plan_graph_id=plan.graph_id,
            latest_checkpoint_id=checkpoint.checkpoint_id,
            result=task["result"] if task is not None else None,
        )
        self._refresh_long_horizon_state(
            task_id=task_id,
            contract=contract,
            plan=plan,
            lattice=lattice,
            evidence=evidence,
            checkpoint_id=checkpoint.checkpoint_id,
        )
        self._audit_event(
            task_id=task_id,
            contract_id=contract.contract_id,
            event_type="approval_requested",
            actor="Governor",
            why=approval_request.reason,
            risk_level=contract.risk_level,
            result="pending",
            evidence_refs=approval_request.relevant_evidence,
            approval_refs=[approval_request.request_id],
        )
        self._emit_telemetry(
            task_id,
            "approval_wait",
            {"request_id": approval_request.request_id, "plan_node_id": node.node_id, "checkpoint_id": checkpoint.checkpoint_id},
        )
        return self.recovery.classify_failure(task_id, "approval_wait", f"Awaiting approval for {node.objective}")

    def _ensure_approval_request(
        self,
        task_id: str,
        contract: TaskContract,
        node: PlanNode,
        evidence: EvidenceBuilder,
    ) -> ApprovalRequest:
        existing = [
            request
            for request in self.repository.list_approval_requests(task_id=task_id)
            if request.plan_node_id == node.node_id and request.status in {"pending", "approved", "denied", "revision_requested"}
        ]
        if existing:
            return existing[-1]
        request = ApprovalRequest(
            version="1.0",
            request_id=f"approval-{uuid4().hex[:10]}",
            contract_id=contract.contract_id,
            action=node.approval_gate or "governor_review",
            reason=f"{node.objective} is gated by {node.approval_gate}.",
            requested_scope=[node.approval_gate or "governor_review"],
            risk_level=contract.risk_level,
            status="pending",
            task_id=task_id,
            plan_node_id=node.node_id,
            action_summary=f"Approve continuation for {node.objective}",
            risk_classification=contract.risk_level,
            relevant_contract_clause=", ".join(contract.approval_required) or "approval required by contract risk",
            relevant_evidence=[item.node_id for item in evidence.graph.nodes[-3:]],
            alternatives_considered=["deny and keep task paused", "request revision before delivery"],
            if_denied="The task remains withheld at the approval gate.",
            expiry_at=utc_now() + timedelta(hours=1),
        )
        self.repository.save_approval_request(request)
        return request

    def _pending_memories_for_task(self, task_id: str) -> list[MemoryRecord]:
        return [
            record
            for record in self.memory.query()
            if str(record.content.get("task_id", "")) == task_id and record.state != "promoted"
        ]

    def _prime_amos_runtime_memory(
        self,
        *,
        task_id: str,
        request: dict[str, object],
        contract: TaskContract,
        plan: PlanGraph,
    ) -> None:
        if self.memory.latest_working_memory_snapshot(task_id) is None:
            self.memory.capture_working_memory(
                task_id=task_id,
                scope_key=task_id,
                active_goal=str(request["goal"]),
                constraints=list(request.get("prohibitions", [])) + list(contract.evidence_requirements),
                confirmed_facts=[],
                tentative_facts=[str(item.objective) for item in plan.nodes if item.status != "completed"],
                evidence_refs=[],
                pending_actions=[str(item.objective) for item in plan.nodes if item.status != "completed"],
                preferences={str(key): str(value) for key, value in dict(request.get("preferences", {})).items()},
                scratchpad=[
                    "Keep raw evidence and semantic abstractions separated.",
                    "Persist contract-critical constraints into governed memory.",
                ],
            )

    def _capture_amos_delivery_memory(
        self,
        *,
        task_id: str,
        request: dict[str, object],
        contract: TaskContract,
        plan: PlanGraph,
        delivery: dict[str, object],
        validation_report: ValidationReport,
    ) -> None:
        delivered_at = utc_now()
        self.memory.record_raw_episode(
            task_id=task_id,
            episode_type="delivery",
            actor="system",
            scope_key=task_id,
            project_id=task_id,
            content={
                "status": validation_report.status,
                "delivery": delivery,
                "contract_id": contract.contract_id,
                "plan_graph_id": plan.graph_id,
            },
            source="runtime_delivery",
            consent="granted",
            trust=0.95 if validation_report.status == "passed" else 0.75,
            dialogue_time=delivered_at,
            event_time_start=delivered_at,
        )
        raw_sources = [episode.episode_id for episode in self.memory.list_raw_episodes(task_id=task_id)]
        if not self.memory.list_temporal_semantic_facts(scope_key=task_id):
            base_candidates = [
                self.memory.create_candidate(
                    task_id=task_id,
                    scope_key=task_id,
                    lane="semantic",
                    summary=f"task goal: {request['goal']}",
                    content={
                        "subject": task_id,
                        "predicate": "has_goal",
                        "object": str(request["goal"]),
                        "head": "goal",
                    },
                    sources=raw_sources,
                )
            ]
            base_candidates.extend(
                self.memory.create_candidate(
                    task_id=task_id,
                    scope_key=task_id,
                    lane="semantic",
                    summary=f"user prefers {value} for {key}",
                    content={
                        "subject": "user",
                        "predicate": f"prefers_{key}",
                        "object": str(value),
                        "head": "preference",
                    },
                    sources=raw_sources,
                )
                for key, value in dict(request.get("preferences", {})).items()
            )
            base_candidates.extend(
                self.memory.create_candidate(
                    task_id=task_id,
                    scope_key=task_id,
                    lane="semantic",
                    summary=f"task must respect prohibition: {rule}",
                    content={
                        "subject": task_id,
                        "predicate": "must_not",
                        "object": str(rule),
                        "head": "constraint",
                    },
                    sources=raw_sources,
                )
                for rule in list(request.get("prohibitions", []))
            )
            for candidate in base_candidates:
                self.memory.govern_candidate(candidate.candidate_id)
                self.memory.consolidate_candidate(candidate.candidate_id)
        delivery_statements = [
            str(fact.get("statement", "")).strip()
            for fact in delivery.get("facts", [])
            if str(fact.get("statement", "")).strip()
        ]
        if delivery_statements:
            candidate = self.memory.create_candidate(
                task_id=task_id,
                scope_key=task_id,
                lane="semantic",
                summary=f"delivery established constraints: {'; '.join(delivery_statements[:3])}",
                content={
                    "subject": task_id,
                    "predicate": "delivery_summary",
                    "object": " | ".join(delivery_statements[:5]),
                    "head": "fact",
                },
                sources=list(raw_sources),
            )
            self.memory.govern_candidate(candidate.candidate_id)
            self.memory.consolidate_candidate(candidate.candidate_id)

    def _refresh_long_horizon_state(
        self,
        task_id: str,
        contract: TaskContract,
        plan: PlanGraph,
        lattice: ContractLattice,
        evidence: EvidenceBuilder,
        checkpoint_id: str,
        validation_report: ValidationReport | None = None,
    ) -> tuple[HandoffPacket, ContinuityWorkingSet, list[OpenQuestion], list[NextAction]]:
        pending_approvals = self.approval_inbox(task_id=task_id)
        pending_memories = self._pending_memories_for_task(task_id)
        receipts = self.repository.list_execution_receipts(task_id)
        evidence_delta = self.continuity.generate_evidence_delta(
            task_id=task_id,
            checkpoint_id=checkpoint_id,
            claims=evidence.claims,
            evidence_graph=evidence.graph,
            validation_report=validation_report,
            receipts=[receipt.receipt_id for receipt in receipts],
        )
        open_questions, next_actions = self.continuity.refresh_ledgers(
            task_id=task_id,
            contract=contract,
            plan=plan,
            evidence_delta=evidence_delta,
            pending_approvals=pending_approvals,
            validation_report=validation_report,
        )
        snapshot = self.continuity.snapshot_workspace(
            task_id=task_id,
            audit_refs=[event.event_id for event in self.repository.query_audit(task_id=task_id)],
            evidence_refs=[node.node_id for node in evidence.graph.nodes[-5:]],
            memory_refs=[memory.memory_id for memory in pending_memories],
            recent_tool_outputs=[
                json.dumps(result.output_payload, ensure_ascii=True, sort_keys=True)[:200]
                for result in self.repository.list_tool_results(task_id)[-3:]
            ],
        )
        handoff = self.continuity.generate_handoff_packet(
            task_id=task_id,
            contract=contract,
            plan=plan,
            lattice=lattice,
            evidence_delta=evidence_delta,
            open_questions=open_questions,
            next_actions=next_actions,
            pending_approvals=pending_approvals,
            pending_memories=pending_memories,
            recommended_strategy=self.routing_strategy,
        )
        self.continuity.compact_context(
            task_id=task_id,
            role_name="Strategist",
            contract=contract,
            plan=plan,
            evidence_delta=evidence_delta,
            open_questions=open_questions,
            next_actions=next_actions,
            pending_approvals=pending_approvals,
            pending_memories=pending_memories,
            recommended_strategy=self.routing_strategy,
        )
        working_set = self.continuity.reconstruct_working_set(task_id, "Strategist")
        self._emit_telemetry(
            task_id,
            "handoff_generated",
            {"packet_id": handoff.packet_id, "checkpoint_id": checkpoint_id, "snapshot_id": snapshot.snapshot_id},
        )
        return handoff, working_set, open_questions, next_actions

    def _collect_continuity_state(
        self,
        task_id: str,
        role_name: str = "Strategist",
    ) -> tuple[HandoffPacket | None, ContinuityWorkingSet | None, list[OpenQuestion], list[NextAction]]:
        handoff = self.repository.latest_handoff_packet(task_id)
        open_questions = self.repository.list_open_questions(task_id)
        next_actions = self.repository.list_next_actions(task_id)
        working_set = None
        if handoff is not None:
            working_set = self.continuity.reconstruct_working_set(task_id, role_name)
        return handoff, working_set, open_questions, next_actions

    def _finalize_blocked_task(
        self,
        task_id: str,
        contract: TaskContract,
        plan: PlanGraph,
        lattice: ContractLattice,
        evidence: EvidenceBuilder,
        incident: IncidentReport,
    ) -> TaskRunResult:
        validation_report = ValidationReport(
            version="1.0",
            report_id=f"validation-{uuid4().hex[:10]}",
            contract_id=contract.contract_id,
            validator="ShadowVerifier",
            status="blocked",
            confidence=0.0,
            findings=[incident.summary],
            contradictions=[],
            evidence_refs=[],
        )
        self.repository.save_validation_report(task_id, validation_report)
        checkpoint = self.checkpoint_task(
            task_id,
            "node-blocked",
            {"phase": "blocked", "incident_id": incident.incident_id, "summary": incident.summary},
        )
        handoff, working_set, open_questions, next_actions = self._refresh_long_horizon_state(
            task_id=task_id,
            contract=contract,
            plan=plan,
            lattice=lattice,
            evidence=evidence,
            checkpoint_id=checkpoint.checkpoint_id,
            validation_report=validation_report,
        )
        self._persist_task_state(
            task_id=task_id,
            status="blocked",
            current_phase="blocked",
            request=self.repository.get_task(task_id)["request"],
            contract_id=contract.contract_id,
            plan_graph_id=plan.graph_id,
            latest_checkpoint_id=checkpoint.checkpoint_id,
            result={
                "status": "blocked",
                "delivery": {"facts": [], "inferences": [], "unresolved": [incident.summary]},
                "validation_report": validation_report.to_dict(),
            },
        )
        result = TaskRunResult(
            task_id=task_id,
            status="blocked",
            contract=contract,
            plan=plan,
            contract_lattice=lattice,
            delivery={"facts": [], "inferences": [], "unresolved": [incident.summary]},
            validation_report=validation_report,
            evidence_graph=evidence.graph,
            audit_events=self.repository.query_audit(task_id=task_id),
            receipts=self.repository.list_execution_receipts(task_id),
            routing_receipts=self.repository.list_routing_receipts(task_id),
            incident=incident,
            handoff_packet=handoff,
            continuity_working_set=working_set,
            open_questions=open_questions,
            next_actions=next_actions,
        )
        self.task_results[task_id] = result
        self.task_status_cache[task_id] = result.status
        self._emit_telemetry(task_id, "task_blocked", {"incident_id": incident.incident_id, "checkpoint_id": checkpoint.checkpoint_id})
        return result

    def _finalize_waiting_approval_task(
        self,
        task_id: str,
        contract: TaskContract,
        plan: PlanGraph,
        lattice: ContractLattice,
        evidence: EvidenceBuilder,
        incident: IncidentReport,
    ) -> TaskRunResult:
        validation_report = ValidationReport(
            version="1.0",
            report_id=f"validation-{uuid4().hex[:10]}",
            contract_id=contract.contract_id,
            validator="Governor",
            status="pending_approval",
            confidence=0.0,
            findings=[incident.summary],
            contradictions=[],
            evidence_refs=[node.node_id for node in evidence.graph.nodes[-3:]],
        )
        self.repository.save_validation_report(task_id, validation_report)
        handoff, working_set, open_questions, next_actions = self._collect_continuity_state(task_id, role_name="Governor")
        delivery = self._build_delivery(evidence)
        delivery["unresolved"] = [incident.summary]
        self._persist_task_state(
            task_id=task_id,
            status="awaiting_approval",
            current_phase="awaiting_approval",
            request=self.repository.get_task(task_id)["request"],
            contract_id=contract.contract_id,
            plan_graph_id=plan.graph_id,
            latest_checkpoint_id=self.repository.get_task(task_id)["latest_checkpoint_id"],
            result={
                "status": "awaiting_approval",
                "delivery": delivery,
                "validation_report": validation_report.to_dict(),
            },
        )
        result = TaskRunResult(
            task_id=task_id,
            status="awaiting_approval",
            contract=contract,
            plan=plan,
            contract_lattice=lattice,
            delivery=delivery,
            validation_report=validation_report,
            evidence_graph=evidence.graph,
            audit_events=self.repository.query_audit(task_id=task_id),
            receipts=self.repository.list_execution_receipts(task_id),
            routing_receipts=self.repository.list_routing_receipts(task_id),
            incident=incident,
            handoff_packet=handoff,
            continuity_working_set=working_set,
            open_questions=open_questions,
            next_actions=next_actions,
        )
        self.task_results[task_id] = result
        self.task_status_cache[task_id] = result.status
        return result

    def _apply_learning_and_evolution(
        self,
        *,
        task_id: str,
        contract: TaskContract,
        delivery: dict[str, object],
        evidence: EvidenceBuilder,
    ) -> None:
        audit_events = self.repository.query_audit(task_id=task_id)
        validation_report = self.repository.load_latest_validation_report(task_id)
        memory = self.memory.write(
            memory_type="episodic",
            summary="Executed a verified file retrieval and extraction slice.",
            content={"task_id": task_id, "claims": len(delivery["facts"])},
            sources=[event.event_id for event in audit_events],
        )
        self.memory.validate(memory.memory_id)
        candidate = self.propose_evolution(
            source_traces=[event.event_id for event in audit_events],
            hypothesis="Promote successful verified retrieval traces into a reusable procedural capsule.",
        )
        from contract_evidence_os.evals.models import StrategyEvaluationReport

        report = StrategyEvaluationReport(
            strategy_name=self.routing_strategy,
            metrics={
                "factual_correctness_rate": 1.0 if validation_report is not None and validation_report.status == "passed" else 0.0,
                "evidence_coverage_rate": 1.0 if all(fact["evidence_refs"] for fact in delivery["facts"]) else 0.0,
                "policy_violation_rate": 0.0,
            },
        )
        evaluation = self.evaluate_candidate(candidate.candidate_id, report=report)
        if evaluation.status == "passed":
            self.evolution.run_canary(candidate.candidate_id, success_rate=1.0, anomaly_count=0)
            self.promote_candidate(candidate.candidate_id)
        else:
            self.rollback_candidate(candidate.candidate_id)

    def _persist_task_state(
        self,
        task_id: str,
        status: str,
        current_phase: str,
        request: dict[str, object],
        contract_id: str | None = None,
        plan_graph_id: str | None = None,
        latest_checkpoint_id: str | None = None,
        result: dict[str, object] | None = None,
    ) -> None:
        mutable_request = dict(request)
        mutable_request["updated_at"] = utc_now().isoformat()
        self.repository.save_task(
            task_id=task_id,
            status=status,
            request=mutable_request,
            current_phase=current_phase,
            contract_id=contract_id,
            plan_graph_id=plan_graph_id,
            latest_checkpoint_id=latest_checkpoint_id,
            result=result,
        )
        self.task_status_cache[task_id] = status

    def _audit_event(
        self,
        task_id: str,
        contract_id: str,
        event_type: str,
        actor: str,
        why: str,
        risk_level: str,
        result: str,
        evidence_refs: list[str] | None = None,
        tool_refs: list[str] | None = None,
        approval_refs: list[str] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            version="1.0",
            event_id=f"audit-{uuid4().hex[:10]}",
            task_id=task_id,
            contract_id=contract_id,
            event_type=event_type,
            actor=actor,
            why=why,
            evidence_refs=evidence_refs or [],
            tool_refs=tool_refs or [],
            approval_refs=approval_refs or [],
            result=result,
            rollback_occurred=False,
            learning_candidate_generated=False,
            system_version="0.3.0",
            skill_version="milestone-3",
            timestamp=utc_now(),
            risk_level=risk_level,
        )
        self.audit.record(event)
        return event

    def _emit_telemetry(self, task_id: str, event_type: str, payload: dict[str, object]) -> TelemetryEvent:
        event = TelemetryEvent(
            version="1.0",
            event_id=f"telemetry-{uuid4().hex[:10]}",
            task_id=task_id,
            event_type=event_type,
            payload=payload,
            timestamp=utc_now(),
        )
        self.repository.save_telemetry_event(event)
        return event

    def _interrupt_if_requested(self, task_id: str, interrupt_after: str | None, phase: str) -> None:
        if interrupt_after != phase:
            return
        task = self.repository.get_task(task_id)
        request = task["request"] if task is not None else {"task_id": task_id}
        self._persist_task_state(
            task_id=task_id,
            status="interrupted",
            current_phase=phase,
            request=request,
            contract_id=task["contract_id"] if task is not None else None,
            plan_graph_id=task["plan_graph_id"] if task is not None else None,
            latest_checkpoint_id=task["latest_checkpoint_id"] if task is not None else None,
            result=task["result"] if task is not None else None,
        )
        self._emit_telemetry(task_id, "session_boundary", {"phase": phase, "status": "interrupted"})
        raise RuntimeInterrupted(task_id, phase)

    def _result_from_replay(self, task_id: str, replay: dict[str, object]) -> TaskRunResult:
        contract = TaskContract.from_dict(dict(replay["contract"]))
        plan = PlanGraph.from_dict(dict(replay["plan"]))
        lattice = ContractLattice.from_dict(dict(replay["contract_lattice"]))
        validation_report = ValidationReport.from_dict(dict(replay["validation_report"]))
        evidence_graph = EvidenceGraph.from_dict(dict(replay["evidence_graph"]))
        result = TaskRunResult(
            task_id=task_id,
            status=str(replay["task"]["status"]),
            contract=contract,
            plan=plan,
            contract_lattice=lattice,
            delivery=dict(replay["delivery"]),
            validation_report=validation_report,
            evidence_graph=evidence_graph,
            audit_events=[AuditEvent.from_dict(item) for item in replay["audit_events"]],
            receipts=[ExecutionReceipt.from_dict(item) for item in replay["execution_receipts"]],
            routing_receipts=[RoutingReceipt.from_dict(item) for item in replay["routing_receipts"]],
            handoff_packet=None if replay.get("handoff") is None else HandoffPacket.from_dict(dict(replay["handoff"])),
            continuity_working_set=None
            if replay.get("continuity_working_set") is None
            else ContinuityWorkingSet.from_dict(dict(replay["continuity_working_set"])),
            open_questions=[OpenQuestion.from_dict(item) for item in replay.get("open_questions", [])],
            next_actions=[NextAction.from_dict(item) for item in replay.get("next_actions", [])],
        )
        self.task_results[task_id] = result
        self.task_status_cache[task_id] = result.status
        return result
