"""SQLite-backed repository and query layer."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import MISSING, fields
from pathlib import Path
from typing import Any

from contract_evidence_os.audit.models import AuditEvent, ExecutionReceipt
from contract_evidence_os.base import utc_now
from contract_evidence_os.continuity.models import (
    ContextCompaction,
    ContinuityWorkingSet,
    EvidenceDeltaSummary,
    HandoffPacket,
    HandoffPacketVersion,
    HandoffSummarySection,
    NextAction,
    OpenQuestion,
    PromptBudgetAllocation,
    WorkspaceSnapshot,
)
from contract_evidence_os.contracts.models import ContractDelta, ContractLattice, TaskContract
from contract_evidence_os.evidence.models import (
    ClaimRecord,
    EvidenceEdge,
    EvidenceGraph,
    EvidenceNode,
    SourceRecord,
    ValidationReport,
)
from contract_evidence_os.evolution.models import (
    CanaryRun,
    EvaluationRun,
    EvolutionCandidate,
    MemoryLifecycleTrace,
    MemoryPolicyAnalyticsRecord,
    MemoryPolicyMiningRun,
)
from contract_evidence_os.memory.models import (
    MaintenanceDaemonRun,
    MaintenanceIncidentRecommendation,
    MaintenanceResolutionAnalytics,
    MaintenanceWorkerLeaseState,
    MemoryAdmissionCanaryRun,
    MemoryArtifactDriftRecord,
    MemoryArtifactBackendHealthRecord,
    MemoryArtifactBackendRepairRun,
    MemoryMaintenanceAnalyticsRecord,
    MemoryMaintenanceCanaryRun,
    MemoryMaintenanceControllerState,
    MemoryMaintenanceIncidentRecord,
    MemoryMaintenanceLearningState,
    MemoryMaintenancePromotionRecommendation,
    MemoryMaintenanceRecoveryRecord,
    MemoryMaintenanceRolloutRecord,
    MemoryMaintenanceSchedule,
    MemoryMaintenanceWorkerRecord,
    MemorySelectiveRebuildRun,
    MemoryRepairCanaryRun,
    MemoryRepairActionRun,
    MemoryRepairLearningState,
    MemoryRepairSafetyAssessment,
    MemoryRepairRolloutAnalyticsRecord,
    MemoryMaintenanceRecommendation,
    MemoryMaintenanceRun,
    MemoryOperationsLoopRun,
    MemoryAdmissionPromotionRecommendation,
    MemoryOperationsLoopSchedule,
    MemoryOperationsLoopRecoveryRecord,
    MemoryOperationsDiagnosticRecord,
    DurativeMemoryRecord,
    ExplicitMemoryRecord,
    MatrixAssociationPointer,
    MemoryAdmissionDecision,
    MemoryAdmissionFeatureScore,
    MemoryAdmissionLearningState,
    MemoryAdmissionPolicy,
    MemoryDashboardItem,
    MemoryConsolidationRun,
    MemoryConsolidationPolicy,
    MemoryContradictionRepairRecord,
    MemoryCrossScopeTimelineSegment,
    MemoryDeletionRun,
    MemoryDeletionReceipt,
    MemoryEvidencePack,
    MemoryGovernanceDecision,
    MemoryHardPurgeRun,
    MemoryArtifactRecord,
    MemoryPromotionRecord,
    MemoryProjectStateSnapshot,
    MemoryProjectStateView,
    MemoryPurgeManifest,
    MemoryRecord,
    MemoryRepairPolicy,
    MemoryRebuildRun,
    MemorySelectivePurgeRun,
    MemoryTimelineSegment,
    MemoryTimelineView,
    MemoryTombstoneRecord,
    MemoryWriteCandidate,
    MemoryWriteReceipt,
    MemorySoftwareProcedureRecord,
    ProceduralPattern,
    RawEpisodeRecord,
    SkillCapsule,
    TemporalSemanticFact,
    WorkingMemorySnapshot,
)
from contract_evidence_os.observability.models import (
    ObservabilityAlertRecord,
    ObservabilityMetricSnapshot,
    ObservabilityTrendReport,
    SoftwareControlTelemetryRecord,
    TelemetryEvent,
)
from contract_evidence_os.planning.models import ExecutionBranch, PlanEdge, PlanGraph, PlanNode, PlanRevision, SchedulerState
from contract_evidence_os.policy.models import ApprovalDecision, ApprovalRequest, HumanIntervention, RemoteApprovalOperation
from contract_evidence_os.recovery.models import CheckpointRecord, IncidentReport
from contract_evidence_os.runtime.backends import (
    BackendCapabilityDescriptor,
    BackendHealthRecord,
    BackendPressureSnapshot,
    CoordinationBackendDescriptor,
    QueueBackendDescriptor,
)
from contract_evidence_os.runtime.budgeting import BudgetConsumptionRecord, BudgetEvent, BudgetLedger, BudgetPolicy
from contract_evidence_os.runtime.coordination import (
    DispatchOwnershipRecord,
    HostRecord,
    LeaseContentionRecord,
    LeaseExpiryForecast,
    LeaseRenewalPolicy,
    LeaseOwnershipRecord,
    LeaseTransferRecord,
    OwnershipConflictEvent,
    RenewalAttemptRecord,
    WorkStealDecision,
    WorkStealPolicy,
    WorkerCapabilityRecord,
    WorkerHeartbeatRecord,
    WorkerHostBinding,
    WorkerLifecycleRecord,
    WorkerEndpointRecord,
    WorkerPressureSnapshot,
)
from contract_evidence_os.runtime.governance import (
    ConcurrencyState,
    ExecutionModeState,
    GovernanceEvent,
    ProviderScorecard,
    RoutingDecisionRecord,
    RoutingPolicy,
)
from contract_evidence_os.runtime.policy_registry import (
    PolicyCandidate,
    PolicyEvidenceBundle,
    PolicyPromotionRun,
    PolicyRollbackRecord,
    PolicyScope,
    PolicyVersion,
)
from contract_evidence_os.runtime.provider_health import (
    ProviderAvailabilityPolicy,
    ProviderCooldownWindow,
    ProviderDegradationEvent,
    ProviderHealthRecord,
    ProviderHealthSnapshot,
    RateLimitState,
)
from contract_evidence_os.runtime.provider_pool import (
    ProviderBalanceDecision,
    ProviderFairnessPolicy,
    ProviderFairnessRecord,
    ProviderPoolBalancePolicy,
    ProviderCapacityRecord,
    ProviderPoolEvent,
    ProviderPoolState,
    ProviderPressureSnapshot,
    ProviderReservation,
    ReservationPolicy,
    SustainedPressurePolicy,
)
from contract_evidence_os.runtime.providers import ProviderCapabilityRecord, ProviderUsageRecord, RoutingReceipt
from contract_evidence_os.runtime.queueing import (
    AdmissionDecision,
    AdmissionPolicy,
    CapacityPolicy,
    CapacitySnapshot,
    DispatchRecord,
    GlobalExecutionModeState,
    LoadSheddingEvent,
    LoadSheddingPolicy,
    OperatorOverrideRecord,
    QueueItem,
    QueueLease,
    QueuePolicy,
    QueuePriorityPolicy,
    RecoveryReservationPolicy,
)
from contract_evidence_os.runtime.auth import (
    AuthCredential,
    AuthEvent,
    AuthFailureEvent,
    AuthPrincipal,
    AuthScope,
    AuthSession,
    ControlPlaneRequestRecord,
    RevokedCredentialRecord,
    CredentialRotationRecord,
    ServiceCredential,
    ServicePrincipal,
    ServiceTrustRecord,
)
from contract_evidence_os.runtime.capacity import (
    CapacityTrendRecord,
    ProviderCapacityForecast,
    ProviderDemandForecast,
    ProviderQuotaPolicy,
    QuotaExhaustionRisk,
    QuotaGovernanceDecision,
    ReservationForecast,
)
from contract_evidence_os.runtime.reliability import (
    BackendOutageRecord,
    ConflictResolutionRecord,
    FaultDomain,
    FaultDomainEvent,
    LeasePredictionRecord,
    LeasePressureSignal,
    LeaseRenewalForecast,
    LeaseSafetyMargin,
    NetworkPartitionRecord,
    ProviderOutageRecord,
    RecoveryBacklogRecord,
    ReliabilityIncident,
    ReliabilityRecoveryPlan,
    ReconciliationRun,
    RenewalRiskScore,
    RuntimeDegradationRecord,
)
from contract_evidence_os.runtime.shared_state import NetworkIdentityRecord, SharedStateBackendDescriptor
from contract_evidence_os.runtime.trust import (
    CredentialBindingRecord,
    SecurityIncidentRecord,
    ServiceTrustPolicy,
    TrustBoundaryDescriptor,
    TrustReplayRecord,
)
from contract_evidence_os.storage.migration_hooks import migrate_payload
from contract_evidence_os.storage.migrations import MigrationRunner
from contract_evidence_os.tools.governance import ToolScorecard
from contract_evidence_os.tools.anything_cli.models import (
    AppCapabilityRecord,
    HarnessManifest,
    SoftwareActionReceipt,
    SoftwareAutomationMacro,
    SoftwareBuildRequest,
    SoftwareCommandDescriptor,
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
from contract_evidence_os.tools.models import ToolInvocation, ToolResult


class SQLiteRepository:
    """Persist and query execution state through SQLite."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.runner = MigrationRunner(self.db_path)
        self.runner.apply_all()

    def dumps(self, payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)

    def loads(self, payload_json: str) -> dict[str, Any]:
        return json.loads(payload_json)

    def save_task(
        self,
        task_id: str,
        status: str,
        request: dict[str, Any],
        current_phase: str,
        contract_id: str | None = None,
        plan_graph_id: str | None = None,
        latest_checkpoint_id: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        created_at = str(request.get("created_at"))
        updated_at = str(request.get("updated_at", created_at))
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks (
                    task_id, status, current_phase, request_json, result_json,
                    contract_id, plan_graph_id, latest_checkpoint_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    status=excluded.status,
                    current_phase=excluded.current_phase,
                    request_json=excluded.request_json,
                    result_json=excluded.result_json,
                    contract_id=COALESCE(excluded.contract_id, tasks.contract_id),
                    plan_graph_id=COALESCE(excluded.plan_graph_id, tasks.plan_graph_id),
                    latest_checkpoint_id=COALESCE(excluded.latest_checkpoint_id, tasks.latest_checkpoint_id),
                    updated_at=excluded.updated_at
                """,
                (
                    task_id,
                    status,
                    current_phase,
                    self.dumps(request),
                    None if result is None else self.dumps(result),
                    contract_id,
                    plan_graph_id,
                    latest_checkpoint_id,
                    created_at,
                    updated_at,
                ),
            )
            connection.commit()

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return {
            "task_id": row["task_id"],
            "status": row["status"],
            "current_phase": row["current_phase"],
            "request": self.loads(row["request_json"]),
            "result": None if row["result_json"] is None else self.loads(row["result_json"]),
            "contract_id": row["contract_id"],
            "plan_graph_id": row["plan_graph_id"],
            "latest_checkpoint_id": row["latest_checkpoint_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM tasks"
        params: tuple[Any, ...] = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY updated_at DESC"
        rows = self._fetchall(query, params)
        return [
            {
                "task_id": row["task_id"],
                "status": row["status"],
                "current_phase": row["current_phase"],
                "contract_id": row["contract_id"],
                "plan_graph_id": row["plan_graph_id"],
                "latest_checkpoint_id": row["latest_checkpoint_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def save_contract(self, task_id: str, contract: TaskContract) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO contracts (
                    contract_id, task_id, record_version, risk_level, normalized_goal, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    contract.contract_id,
                    task_id,
                    contract.version,
                    contract.risk_level,
                    contract.normalized_goal,
                    self.dumps(contract.to_dict()),
                ),
            )
            connection.commit()

    def load_contract(self, contract_id: str) -> TaskContract:
        row = self._fetchone("SELECT * FROM contracts WHERE contract_id = ?", (contract_id,))
        return self._model_from_row("contracts", row, TaskContract)

    def load_task_contract(self, task_id: str) -> TaskContract | None:
        row = self._fetchone(
            "SELECT * FROM contracts WHERE task_id = ? ORDER BY rowid ASC LIMIT 1",
            (task_id,),
        )
        return None if row is None else self._model_from_row("contracts", row, TaskContract)

    def save_contract_delta(self, delta: ContractDelta) -> None:
        self._insert_or_replace(
            "contract_deltas",
            {
                "delta_id": delta.delta_id,
                "contract_id": delta.contract_id,
                "record_version": delta.version,
                "timestamp": delta.timestamp.isoformat(),
                "payload_json": self.dumps(delta.to_dict()),
            },
        )

    def save_contract_lattice(self, task_id: str, lattice: ContractLattice) -> None:
        self._insert_or_replace(
            "contract_lattices",
            {
                "root_contract_id": lattice.root_contract_id,
                "task_id": task_id,
                "record_version": lattice.version,
                "payload_json": self.dumps(lattice.to_dict()),
            },
        )

    def load_contract_lattice(self, task_id: str) -> ContractLattice | None:
        row = self._fetchone("SELECT * FROM contract_lattices WHERE task_id = ?", (task_id,))
        return None if row is None else self._model_from_row("contract_lattices", row, ContractLattice)

    def save_plan(self, task_id: str, plan: PlanGraph) -> None:
        self._execute("DELETE FROM plan_graphs WHERE task_id = ?", (task_id,))
        self._insert_or_replace(
            "plan_graphs",
            {
                "graph_id": plan.graph_id,
                "task_id": task_id,
                "record_version": plan.version,
                "payload_json": self.dumps(plan.to_dict()),
                "updated_at": self._now_iso(),
            },
        )
        with self._connect() as connection:
            connection.execute("DELETE FROM plan_nodes WHERE task_id = ?", (task_id,))
            connection.execute("DELETE FROM plan_edges WHERE task_id = ?", (task_id,))
            for index, node in enumerate(plan.nodes):
                connection.execute(
                    """
                    INSERT INTO plan_nodes (
                        task_id, node_id, graph_id, position, status, role_owner, objective,
                        approval_gate, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        node.node_id,
                        plan.graph_id,
                        index,
                        node.status,
                        node.role_owner,
                        node.objective,
                        node.approval_gate,
                        self.dumps(node.to_dict()),
                    ),
                )
            for index, edge in enumerate(plan.edges):
                connection.execute(
                    """
                    INSERT INTO plan_edges (
                        edge_id, task_id, graph_id, position, source_node_id, target_node_id,
                        edge_type, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        edge.edge_id,
                        task_id,
                        plan.graph_id,
                        index,
                        edge.source_node_id,
                        edge.target_node_id,
                        edge.edge_type,
                        self.dumps(edge.to_dict()),
                    ),
                )
            connection.commit()

    def update_plan_node_status(self, task_id: str, node_id: str, status: str) -> None:
        row = self._fetchone(
            "SELECT payload_json FROM plan_nodes WHERE task_id = ? AND node_id = ?",
            (task_id, node_id),
        )
        if row is None:
            return
        payload = self.loads(row["payload_json"])
        payload["status"] = status
        self._execute(
            "UPDATE plan_nodes SET status = ?, payload_json = ? WHERE task_id = ? AND node_id = ?",
            (status, self.dumps(payload), task_id, node_id),
        )

    def load_plan(self, task_id: str) -> PlanGraph | None:
        graph_row = self._fetchone(
            "SELECT * FROM plan_graphs WHERE task_id = ? ORDER BY updated_at DESC LIMIT 1",
            (task_id,),
        )
        if graph_row is None:
            return None
        node_rows = self._fetchall(
            "SELECT payload_json FROM plan_nodes WHERE task_id = ? ORDER BY position ASC",
            (task_id,),
        )
        edge_rows = self._fetchall(
            "SELECT payload_json FROM plan_edges WHERE task_id = ? ORDER BY position ASC",
            (task_id,),
        )
        graph = self._model_from_row("plan_graphs", graph_row, PlanGraph)
        graph.nodes = [PlanNode.from_dict(self.loads(row["payload_json"])) for row in node_rows]
        graph.edges = [PlanEdge.from_dict(self.loads(row["payload_json"])) for row in edge_rows]
        return graph

    def save_source_record(self, task_id: str, source: SourceRecord) -> None:
        self._insert_or_replace(
            "source_records",
            {
                "source_id": source.source_id,
                "task_id": task_id,
                "record_version": source.version,
                "locator": source.locator,
                "source_type": source.source_type,
                "credibility": source.credibility,
                "retrieved_at": source.retrieved_at.isoformat(),
                "payload_json": self.dumps(source.to_dict()),
            },
        )

    def save_evidence_graph(
        self,
        task_id: str,
        graph: EvidenceGraph,
        claims: list[ClaimRecord] | None = None,
    ) -> None:
        with self._connect() as connection:
            for node in graph.nodes:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO evidence_nodes (
                        node_id, task_id, graph_id, record_version, node_type,
                        confidence, created_at, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        node.node_id,
                        task_id,
                        graph.graph_id,
                        node.version,
                        node.node_type,
                        node.confidence,
                        node.created_at.isoformat(),
                        self.dumps(node.to_dict()),
                    ),
                )
            for edge in graph.edges:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO evidence_edges (
                        edge_id, task_id, graph_id, record_version, source_node_id,
                        target_node_id, edge_type, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        edge.edge_id,
                        task_id,
                        graph.graph_id,
                        edge.version,
                        edge.source_node_id,
                        edge.target_node_id,
                        edge.edge_type,
                        self.dumps(edge.to_dict()),
                    ),
                )
            for claim in claims or []:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO claim_records (
                        claim_id, task_id, record_version, status, claim_type, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        claim.claim_id,
                        task_id,
                        claim.version,
                        claim.status,
                        claim.claim_type,
                        self.dumps(claim.to_dict()),
                    ),
                )
            connection.commit()

    def load_evidence_graph(self, task_id: str) -> EvidenceGraph:
        node_rows = self._fetchall(
            "SELECT * FROM evidence_nodes WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        edge_rows = self._fetchall(
            "SELECT * FROM evidence_edges WHERE task_id = ? ORDER BY rowid ASC",
            (task_id,),
        )
        graph_id = str(node_rows[0]["graph_id"]) if node_rows else "evidence-root"
        return EvidenceGraph(
            version="1.0",
            graph_id=graph_id,
            nodes=[self._model_from_row("evidence_nodes", row, EvidenceNode) for row in node_rows],
            edges=[self._model_from_row("evidence_edges", row, EvidenceEdge) for row in edge_rows],
        )

    def load_claims(self, task_id: str) -> list[ClaimRecord]:
        rows = self._fetchall("SELECT * FROM claim_records WHERE task_id = ? ORDER BY rowid ASC", (task_id,))
        return [self._model_from_row("claim_records", row, ClaimRecord) for row in rows]

    def save_validation_report(self, task_id: str, report: ValidationReport) -> None:
        self._insert_or_replace(
            "validation_reports",
            {
                "report_id": report.report_id,
                "task_id": task_id,
                "contract_id": report.contract_id,
                "record_version": report.version,
                "status": report.status,
                "validator": report.validator,
                "confidence": report.confidence,
                "payload_json": self.dumps(report.to_dict()),
            },
        )

    def load_latest_validation_report(self, task_id: str) -> ValidationReport | None:
        row = self._fetchone(
            "SELECT * FROM validation_reports WHERE task_id = ? ORDER BY rowid DESC LIMIT 1",
            (task_id,),
        )
        return None if row is None else self._model_from_row("validation_reports", row, ValidationReport)

    def save_tool_invocation(self, task_id: str, invocation: ToolInvocation) -> None:
        self._insert_or_replace(
            "tool_invocations",
            {
                "invocation_id": invocation.invocation_id,
                "task_id": task_id,
                "tool_id": invocation.tool_id,
                "actor": invocation.actor,
                "requested_at": invocation.requested_at.isoformat(),
                "idempotency_key": invocation.idempotency_key,
                "attempt": invocation.attempt,
                "payload_json": self.dumps(invocation.to_dict()),
            },
        )

    def save_tool_result(self, task_id: str, result: ToolResult) -> None:
        self._insert_or_replace(
            "tool_results",
            {
                "invocation_id": result.invocation_id,
                "task_id": task_id,
                "tool_id": result.tool_id,
                "status": result.status,
                "completed_at": result.completed_at.isoformat(),
                "confidence": result.confidence,
                "provider_mode": result.provider_mode,
                "deterministic": 1 if result.deterministic else 0,
                "provenance_json": self.dumps(result.provenance),
                "record_version": result.version,
                "payload_json": self.dumps(result.to_dict()),
            },
        )

    def list_tool_invocations(self, task_id: str) -> list[ToolInvocation]:
        rows = self._fetchall(
            "SELECT * FROM tool_invocations WHERE task_id = ? ORDER BY requested_at ASC",
            (task_id,),
        )
        return [self._model_from_row("tool_invocations", row, ToolInvocation) for row in rows]

    def list_tool_results(self, task_id: str) -> list[ToolResult]:
        rows = self._fetchall(
            "SELECT * FROM tool_results WHERE task_id = ? ORDER BY completed_at ASC",
            (task_id,),
        )
        return [self._model_from_row("tool_results", row, ToolResult) for row in rows]

    def save_routing_receipt(self, task_id: str, receipt: RoutingReceipt) -> None:
        self._insert_or_replace(
            "routing_receipts",
            {
                "routing_id": receipt.routing_id,
                "task_id": task_id,
                "role": receipt.role,
                "workload": receipt.workload,
                "risk_level": receipt.risk_level,
                "strategy_name": receipt.strategy_name,
                "provider_name": receipt.provider_name,
                "model_name": receipt.model_name,
                "profile": receipt.profile,
                "cost_tier": receipt.cost_tier,
                "attempt_count": receipt.attempt_count,
                "fallback_used": 1 if receipt.fallback_used else 0,
                "status": receipt.status,
                "created_at": receipt.created_at.isoformat(),
                "record_version": receipt.version,
                "payload_json": self.dumps(receipt.to_dict()),
            },
        )

    def list_routing_receipts(self, task_id: str) -> list[RoutingReceipt]:
        rows = self._fetchall(
            "SELECT * FROM routing_receipts WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        return [self._model_from_row("routing_receipts", row, RoutingReceipt) for row in rows]

    def save_provider_usage_record(self, record: ProviderUsageRecord) -> None:
        self._insert_or_replace(
            "provider_usage_records",
            {
                "usage_id": record.usage_id,
                "task_id": record.task_id,
                "plan_node_id": record.plan_node_id,
                "correlation_id": record.correlation_id,
                "role": record.role,
                "provider_name": record.provider_name,
                "model_name": record.model_name,
                "profile": record.profile,
                "status": record.status,
                "created_at": record.created_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def list_provider_usage_records(self, task_id: str) -> list[ProviderUsageRecord]:
        rows = self._fetchall(
            "SELECT * FROM provider_usage_records WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        return [self._model_from_row("provider_usage_records", row, ProviderUsageRecord) for row in rows]

    def save_provider_capability(self, capability: ProviderCapabilityRecord) -> None:
        self._insert_or_replace(
            "provider_capabilities",
            {
                "provider_name": capability.provider_name,
                "availability_state": capability.availability_state,
                "record_version": capability.version,
                "payload_json": self.dumps(capability.to_dict()),
            },
        )

    def list_provider_capabilities(self) -> list[ProviderCapabilityRecord]:
        rows = self._fetchall("SELECT * FROM provider_capabilities ORDER BY provider_name ASC", ())
        return [self._model_from_row("provider_capabilities", row, ProviderCapabilityRecord) for row in rows]

    def save_provider_scorecard(self, scorecard: ProviderScorecard) -> None:
        self._insert_or_replace(
            "provider_scorecards",
            {
                "provider_name": scorecard.provider_name,
                "profile": scorecard.profile,
                "updated_at": scorecard.last_updated.isoformat(),
                "record_version": scorecard.version,
                "payload_json": self.dumps(scorecard.to_dict()),
            },
        )

    def get_provider_scorecard(self, provider_name: str, profile: str) -> ProviderScorecard | None:
        row = self._fetchone(
            "SELECT * FROM provider_scorecards WHERE provider_name = ? AND profile = ?",
            (provider_name, profile),
        )
        return None if row is None else self._model_from_row("provider_scorecards", row, ProviderScorecard)

    def list_provider_scorecards(self) -> list[ProviderScorecard]:
        rows = self._fetchall("SELECT * FROM provider_scorecards ORDER BY updated_at DESC", ())
        return [self._model_from_row("provider_scorecards", row, ProviderScorecard) for row in rows]

    def save_routing_policy(self, policy: RoutingPolicy) -> None:
        self._insert_or_replace(
            "routing_policies",
            {
                "policy_id": policy.policy_id,
                "name": policy.name,
                "execution_mode": policy.execution_mode,
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def load_routing_policy(self, policy_id: str) -> RoutingPolicy:
        row = self._fetchone("SELECT * FROM routing_policies WHERE policy_id = ?", (policy_id,))
        return self._model_from_row("routing_policies", row, RoutingPolicy)

    def save_routing_decision(self, decision: RoutingDecisionRecord) -> None:
        self._insert_or_replace(
            "routing_decisions",
            {
                "decision_id": decision.decision_id,
                "task_id": decision.task_id,
                "plan_node_id": decision.plan_node_id,
                "decision_type": decision.decision_type,
                "created_at": decision.created_at.isoformat(),
                "record_version": decision.version,
                "payload_json": self.dumps(decision.to_dict()),
            },
        )

    def list_routing_decisions(self, task_id: str) -> list[RoutingDecisionRecord]:
        rows = self._fetchall(
            "SELECT * FROM routing_decisions WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        return [self._model_from_row("routing_decisions", row, RoutingDecisionRecord) for row in rows]

    def save_audit_event(self, event: AuditEvent) -> None:
        self._insert_or_replace(
            "audit_events",
            {
                "event_id": event.event_id,
                "task_id": event.task_id,
                "contract_id": event.contract_id,
                "event_type": event.event_type,
                "actor": event.actor,
                "risk_level": event.risk_level,
                "timestamp": event.timestamp.isoformat(),
                "record_version": event.version,
                "payload_json": self.dumps(event.to_dict()),
            },
        )

    def query_audit(
        self,
        task_id: str | None = None,
        event_type: str | None = None,
        actor: str | None = None,
        tool_ref: str | None = None,
        risk_level: str | None = None,
    ) -> list[AuditEvent]:
        clauses = []
        params: list[Any] = []
        if task_id:
            clauses.append("task_id = ?")
            params.append(task_id)
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if actor:
            clauses.append("actor = ?")
            params.append(actor)
        if risk_level:
            clauses.append("risk_level = ?")
            params.append(risk_level)
        query = "SELECT * FROM audit_events"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY timestamp ASC"
        rows = self._fetchall(query, tuple(params))
        events = [self._model_from_row("audit_events", row, AuditEvent) for row in rows]
        if tool_ref:
            events = [event for event in events if tool_ref in event.tool_refs]
        return events

    def save_execution_receipt(self, task_id: str, receipt: ExecutionReceipt) -> None:
        self._insert_or_replace(
            "execution_receipts",
            {
                "receipt_id": receipt.receipt_id,
                "task_id": task_id,
                "contract_id": receipt.contract_id,
                "plan_node_id": receipt.plan_node_id,
                "actor": receipt.actor,
                "tool_used": receipt.tool_used,
                "status": receipt.status,
                "timestamp": receipt.timestamp.isoformat(),
                "record_version": receipt.version,
                "payload_json": self.dumps(receipt.to_dict()),
            },
        )

    def list_execution_receipts(self, task_id: str) -> list[ExecutionReceipt]:
        rows = self._fetchall(
            "SELECT * FROM execution_receipts WHERE task_id = ? ORDER BY timestamp ASC",
            (task_id,),
        )
        return [self._model_from_row("execution_receipts", row, ExecutionReceipt) for row in rows]

    def save_checkpoint(self, record: CheckpointRecord, state: dict[str, Any]) -> None:
        latest = self.latest_checkpoint(record.task_id)
        next_sequence = 1 if latest is None else int(latest[0].metadata.get("sequence", 0)) + 1
        payload = record.to_dict()
        payload["metadata"] = dict(record.metadata)
        payload["metadata"]["sequence"] = next_sequence
        self._insert_or_replace(
            "checkpoints",
            {
                "checkpoint_id": record.checkpoint_id,
                "task_id": record.task_id,
                "plan_node_id": record.plan_node_id,
                "created_at": record.created_at.isoformat(),
                "sequence": next_sequence,
                "record_version": record.version,
                "payload_json": self.dumps(payload),
                "state_json": self.dumps(state),
            },
        )

    def latest_checkpoint(self, task_id: str) -> tuple[CheckpointRecord, dict[str, Any]] | None:
        row = self._fetchone(
            "SELECT * FROM checkpoints WHERE task_id = ? ORDER BY sequence DESC LIMIT 1",
            (task_id,),
        )
        if row is None:
            return None
        return (
            self._model_from_row("checkpoints", row, CheckpointRecord),
            self.loads(row["state_json"]),
        )

    def list_checkpoints(self, task_id: str) -> list[CheckpointRecord]:
        rows = self._fetchall(
            "SELECT * FROM checkpoints WHERE task_id = ? ORDER BY sequence ASC",
            (task_id,),
        )
        return [self._model_from_row("checkpoints", row, CheckpointRecord) for row in rows]

    def restore_checkpoint(self, checkpoint_id: str) -> dict[str, Any]:
        row = self._fetchone("SELECT state_json FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,))
        if row is None:
            raise KeyError(checkpoint_id)
        return self.loads(row["state_json"])

    def save_incident(self, report: IncidentReport) -> None:
        self._insert_or_replace(
            "incidents",
            {
                "incident_id": report.incident_id,
                "task_id": report.task_id,
                "incident_type": report.incident_type,
                "severity": report.severity,
                "resolution": report.resolution,
                "created_at": report.created_at.isoformat(),
                "record_version": report.version,
                "payload_json": self.dumps(report.to_dict()),
            },
        )

    def list_incidents(self, task_id: str) -> list[IncidentReport]:
        rows = self._fetchall(
            "SELECT * FROM incidents WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        return [self._model_from_row("incidents", row, IncidentReport) for row in rows]

    def save_memory_record(self, record: MemoryRecord) -> None:
        self._insert_or_replace(
            "memory_records",
            {
                "memory_id": record.memory_id,
                "memory_type": record.memory_type,
                "state": record.state,
                "updated_at": record.updated_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def list_memory_records(self, memory_type: str | None = None, state: str | None = None) -> list[MemoryRecord]:
        clauses = []
        params: list[Any] = []
        if memory_type:
            clauses.append("memory_type = ?")
            params.append(memory_type)
        if state:
            clauses.append("state = ?")
            params.append(state)
        query = "SELECT * FROM memory_records"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at ASC"
        rows = self._fetchall(query, tuple(params))
        return [self._model_from_row("memory_records", row, MemoryRecord) for row in rows]

    def save_memory_promotion(self, promotion: MemoryPromotionRecord) -> None:
        self._insert_or_replace(
            "memory_promotions",
            {
                "promotion_id": promotion.promotion_id,
                "memory_id": promotion.memory_id,
                "new_state": promotion.new_state,
                "promoted_at": promotion.promoted_at.isoformat(),
                "record_version": promotion.version,
                "payload_json": self.dumps(promotion.to_dict()),
            },
        )

    def save_raw_episode(self, record: RawEpisodeRecord) -> None:
        self._save_runtime_state_record(
            "memory_raw_episode",
            record.episode_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_raw_episodes(self, task_id: str | None = None, scope_key: str | None = None) -> list[RawEpisodeRecord]:
        records = self._list_runtime_state_records("memory_raw_episode", RawEpisodeRecord, scope_key=scope_key)
        if task_id is not None:
            records = [record for record in records if record.task_id == task_id]
        return records

    def save_working_memory_snapshot(self, snapshot: WorkingMemorySnapshot) -> None:
        self._save_runtime_state_record(
            "memory_working_snapshot",
            snapshot.snapshot_id,
            snapshot.scope_key,
            snapshot.captured_at.isoformat(),
            snapshot,
        )

    def list_working_memory_snapshots(
        self,
        *,
        task_id: str | None = None,
        scope_key: str | None = None,
    ) -> list[WorkingMemorySnapshot]:
        records = self._list_runtime_state_records("memory_working_snapshot", WorkingMemorySnapshot, scope_key=scope_key)
        if task_id is not None:
            records = [record for record in records if record.task_id == task_id]
        return records

    def latest_working_memory_snapshot(self, task_id: str) -> WorkingMemorySnapshot | None:
        records = self.list_working_memory_snapshots(task_id=task_id)
        return None if not records else records[0]

    def save_memory_write_candidate(self, candidate: MemoryWriteCandidate) -> None:
        self._save_runtime_state_record(
            "memory_write_candidate",
            candidate.candidate_id,
            candidate.scope_key,
            candidate.created_at.isoformat(),
            candidate,
        )

    def load_memory_write_candidate(self, candidate_id: str) -> MemoryWriteCandidate | None:
        return self._load_runtime_state_record("memory_write_candidate", candidate_id, MemoryWriteCandidate)

    def list_memory_write_candidates(
        self,
        *,
        scope_key: str | None = None,
        task_id: str | None = None,
    ) -> list[MemoryWriteCandidate]:
        records = self._list_runtime_state_records("memory_write_candidate", MemoryWriteCandidate, scope_key=scope_key)
        if task_id is not None:
            records = [record for record in records if record.task_id == task_id]
        return records

    def save_memory_admission_policy(self, policy: MemoryAdmissionPolicy) -> None:
        self._save_runtime_state_record(
            "memory_admission_policy",
            policy.policy_id,
            policy.scope_key,
            policy.updated_at.isoformat(),
            policy,
        )

    def load_memory_admission_policy(self, scope_key: str) -> MemoryAdmissionPolicy | None:
        records = self._list_runtime_state_records("memory_admission_policy", MemoryAdmissionPolicy, scope_key=scope_key)
        return None if not records else records[0]

    def save_memory_admission_decision(self, decision: MemoryAdmissionDecision) -> None:
        self._save_runtime_state_record(
            "memory_admission_decision",
            decision.decision_id,
            decision.scope_key,
            decision.decided_at.isoformat(),
            decision,
        )

    def list_memory_admission_decisions(self, scope_key: str | None = None) -> list[MemoryAdmissionDecision]:
        return self._list_runtime_state_records("memory_admission_decision", MemoryAdmissionDecision, scope_key=scope_key)

    def save_memory_admission_learning_state(self, state: MemoryAdmissionLearningState) -> None:
        self._save_runtime_state_record(
            "memory_admission_learning_state",
            state.learning_id,
            state.scope_key,
            state.trained_at.isoformat(),
            state,
        )

    def load_memory_admission_learning_state(self, scope_key: str) -> MemoryAdmissionLearningState | None:
        records = self._list_runtime_state_records(
            "memory_admission_learning_state",
            MemoryAdmissionLearningState,
            scope_key=scope_key,
        )
        return None if not records else records[0]

    def save_memory_admission_feature_score(self, score: MemoryAdmissionFeatureScore) -> None:
        self._save_runtime_state_record(
            "memory_admission_feature_score",
            score.score_id,
            score.candidate_id,
            score.created_at.isoformat(),
            score,
        )

    def list_memory_admission_feature_scores(
        self,
        candidate_id: str | None = None,
    ) -> list[MemoryAdmissionFeatureScore]:
        records = self._list_runtime_state_records(
            "memory_admission_feature_score",
            MemoryAdmissionFeatureScore,
            scope_key=candidate_id,
        )
        if candidate_id is None:
            return records
        return [record for record in records if record.candidate_id == candidate_id]

    def latest_memory_admission_feature_score(self, candidate_id: str) -> MemoryAdmissionFeatureScore | None:
        records = self.list_memory_admission_feature_scores(candidate_id)
        return None if not records else records[0]

    def save_memory_governance_decision(self, decision: MemoryGovernanceDecision) -> None:
        self._save_runtime_state_record(
            "memory_governance_decision",
            decision.decision_id,
            decision.candidate_id,
            decision.decided_at.isoformat(),
            decision,
        )

    def list_memory_governance_decisions(self, candidate_id: str | None = None) -> list[MemoryGovernanceDecision]:
        records = self._list_runtime_state_records("memory_governance_decision", MemoryGovernanceDecision, scope_key=candidate_id)
        if candidate_id is None:
            return records
        return [record for record in records if record.candidate_id == candidate_id]

    def latest_memory_governance_decision(self, candidate_id: str) -> MemoryGovernanceDecision | None:
        records = self.list_memory_governance_decisions(candidate_id)
        return None if not records else records[0]

    def save_temporal_semantic_fact(self, fact: TemporalSemanticFact) -> None:
        self._save_runtime_state_record(
            "memory_temporal_semantic_fact",
            fact.fact_id,
            fact.scope_key,
            fact.observed_at.isoformat(),
            fact,
        )

    def list_temporal_semantic_facts(
        self,
        *,
        scope_key: str | None = None,
        task_id: str | None = None,
    ) -> list[TemporalSemanticFact]:
        records = self._list_runtime_state_records("memory_temporal_semantic_fact", TemporalSemanticFact, scope_key=scope_key)
        if task_id is not None:
            records = [record for record in records if record.task_id == task_id]
        return records

    def save_durative_memory(self, record: DurativeMemoryRecord) -> None:
        self._save_runtime_state_record(
            "memory_durative_record",
            record.durative_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_durative_memories(
        self,
        *,
        scope_key: str | None = None,
        task_id: str | None = None,
    ) -> list[DurativeMemoryRecord]:
        records = self._list_runtime_state_records("memory_durative_record", DurativeMemoryRecord, scope_key=scope_key)
        if task_id is not None:
            records = [record for record in records if record.task_id == task_id]
        return records

    def save_matrix_association_pointer(self, pointer: MatrixAssociationPointer) -> None:
        self._save_runtime_state_record(
            "memory_matrix_pointer",
            pointer.pointer_id,
            pointer.scope_key,
            pointer.created_at.isoformat(),
            pointer,
        )

    def list_matrix_association_pointers(
        self,
        *,
        scope_key: str | None = None,
        task_id: str | None = None,
    ) -> list[MatrixAssociationPointer]:
        records = self._list_runtime_state_records("memory_matrix_pointer", MatrixAssociationPointer, scope_key=scope_key)
        if task_id is not None:
            records = [record for record in records if record.task_id == task_id]
        return records

    def save_procedural_pattern(self, pattern: ProceduralPattern) -> None:
        self._save_runtime_state_record(
            "memory_procedural_pattern",
            pattern.pattern_id,
            pattern.scope_key,
            pattern.created_at.isoformat(),
            pattern,
        )

    def list_procedural_patterns(
        self,
        *,
        scope_key: str | None = None,
        task_id: str | None = None,
    ) -> list[ProceduralPattern]:
        records = self._list_runtime_state_records("memory_procedural_pattern", ProceduralPattern, scope_key=scope_key)
        if task_id is not None:
            records = [record for record in records if record.task_id == task_id]
        return records

    def save_explicit_memory_record(self, record: ExplicitMemoryRecord) -> None:
        self._save_runtime_state_record(
            "memory_explicit_record",
            record.record_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_explicit_memory_records(
        self,
        *,
        scope_key: str | None = None,
        task_id: str | None = None,
    ) -> list[ExplicitMemoryRecord]:
        records = self._list_runtime_state_records("memory_explicit_record", ExplicitMemoryRecord, scope_key=scope_key)
        if task_id is not None:
            records = [record for record in records if record.task_id == task_id]
        return records

    def save_memory_evidence_pack(self, pack: MemoryEvidencePack) -> None:
        self._save_runtime_state_record(
            "memory_evidence_pack",
            pack.pack_id,
            pack.scope_key,
            pack.assembled_at.isoformat(),
            pack,
        )

    def list_memory_evidence_packs(self, scope_key: str | None = None) -> list[MemoryEvidencePack]:
        return self._list_runtime_state_records("memory_evidence_pack", MemoryEvidencePack, scope_key=scope_key)

    def save_memory_write_receipt(self, record: MemoryWriteReceipt) -> None:
        self._save_runtime_state_record(
            "memory_write_receipt",
            record.receipt_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_write_receipts(self, scope_key: str | None = None) -> list[MemoryWriteReceipt]:
        return self._list_runtime_state_records("memory_write_receipt", MemoryWriteReceipt, scope_key=scope_key)

    def save_memory_dashboard_item(self, item: MemoryDashboardItem) -> None:
        self._save_runtime_state_record(
            "memory_dashboard_item",
            item.item_id,
            item.scope_key,
            item.updated_at.isoformat(),
            item,
        )

    def list_memory_dashboard_items(self, scope_key: str | None = None) -> list[MemoryDashboardItem]:
        return self._list_runtime_state_records("memory_dashboard_item", MemoryDashboardItem, scope_key=scope_key)

    def save_memory_tombstone(self, record: MemoryTombstoneRecord) -> None:
        self._save_runtime_state_record(
            "memory_tombstone",
            record.tombstone_id,
            record.scope_key,
            record.deleted_at.isoformat(),
            record,
        )

    def list_memory_tombstones(self, scope_key: str | None = None) -> list[MemoryTombstoneRecord]:
        return self._list_runtime_state_records("memory_tombstone", MemoryTombstoneRecord, scope_key=scope_key)

    def save_memory_deletion_run(self, record: MemoryDeletionRun) -> None:
        self._save_runtime_state_record(
            "memory_deletion_run",
            record.run_id,
            record.scope_key,
            record.completed_at.isoformat(),
            record,
        )

    def list_memory_deletion_runs(self, scope_key: str | None = None) -> list[MemoryDeletionRun]:
        return self._list_runtime_state_records("memory_deletion_run", MemoryDeletionRun, scope_key=scope_key)

    def save_memory_deletion_receipt(self, record: MemoryDeletionReceipt) -> None:
        self._save_runtime_state_record(
            "memory_deletion_receipt",
            record.receipt_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_deletion_receipts(self, scope_key: str | None = None) -> list[MemoryDeletionReceipt]:
        return self._list_runtime_state_records("memory_deletion_receipt", MemoryDeletionReceipt, scope_key=scope_key)

    def save_memory_software_procedure(self, record: MemorySoftwareProcedureRecord) -> None:
        self._save_runtime_state_record(
            "memory_software_procedure",
            record.procedure_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_software_procedures(self, scope_key: str | None = None) -> list[MemorySoftwareProcedureRecord]:
        return self._list_runtime_state_records("memory_software_procedure", MemorySoftwareProcedureRecord, scope_key=scope_key)

    def save_memory_consolidation_run(self, record: MemoryConsolidationRun) -> None:
        self._save_runtime_state_record(
            "memory_consolidation_run",
            record.run_id,
            record.scope_key,
            record.completed_at.isoformat(),
            record,
        )

    def list_memory_consolidation_runs(self, scope_key: str | None = None) -> list[MemoryConsolidationRun]:
        return self._list_runtime_state_records("memory_consolidation_run", MemoryConsolidationRun, scope_key=scope_key)

    def save_memory_rebuild_run(self, record: MemoryRebuildRun) -> None:
        self._save_runtime_state_record(
            "memory_rebuild_run",
            record.run_id,
            record.scope_key,
            record.completed_at.isoformat(),
            record,
        )

    def list_memory_rebuild_runs(self, scope_key: str | None = None) -> list[MemoryRebuildRun]:
        return self._list_runtime_state_records("memory_rebuild_run", MemoryRebuildRun, scope_key=scope_key)

    def save_memory_hard_purge_run(self, record: MemoryHardPurgeRun) -> None:
        self._save_runtime_state_record(
            "memory_hard_purge_run",
            record.run_id,
            record.scope_key,
            record.completed_at.isoformat(),
            record,
        )

    def list_memory_hard_purge_runs(self, scope_key: str | None = None) -> list[MemoryHardPurgeRun]:
        return self._list_runtime_state_records("memory_hard_purge_run", MemoryHardPurgeRun, scope_key=scope_key)

    def save_memory_selective_purge_run(self, record: MemorySelectivePurgeRun) -> None:
        self._save_runtime_state_record(
            "memory_selective_purge_run",
            record.run_id,
            record.scope_key,
            record.completed_at.isoformat(),
            record,
        )

    def list_memory_selective_purge_runs(self, scope_key: str | None = None) -> list[MemorySelectivePurgeRun]:
        return self._list_runtime_state_records("memory_selective_purge_run", MemorySelectivePurgeRun, scope_key=scope_key)

    def save_memory_purge_manifest(self, record: MemoryPurgeManifest) -> None:
        self._save_runtime_state_record(
            "memory_purge_manifest",
            record.manifest_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_purge_manifests(self, scope_key: str | None = None) -> list[MemoryPurgeManifest]:
        return self._list_runtime_state_records("memory_purge_manifest", MemoryPurgeManifest, scope_key=scope_key)

    def save_memory_artifact_record(self, record: MemoryArtifactRecord) -> None:
        self._save_runtime_state_record(
            "memory_artifact_record",
            record.artifact_id,
            record.scope_key,
            record.updated_at.isoformat(),
            record,
        )

    def list_memory_artifact_records(self, scope_key: str | None = None) -> list[MemoryArtifactRecord]:
        return self._list_runtime_state_records("memory_artifact_record", MemoryArtifactRecord, scope_key=scope_key)

    def save_memory_timeline_segment(self, record: MemoryTimelineSegment) -> None:
        self._save_runtime_state_record(
            "memory_timeline_segment",
            record.segment_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_timeline_segments(self, scope_key: str | None = None) -> list[MemoryTimelineSegment]:
        return self._list_runtime_state_records("memory_timeline_segment", MemoryTimelineSegment, scope_key=scope_key)

    def save_memory_cross_scope_timeline_segment(self, record: MemoryCrossScopeTimelineSegment) -> None:
        scope_key = "|".join(record.scope_keys)
        self._save_runtime_state_record(
            "memory_cross_scope_timeline_segment",
            record.segment_id,
            scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_cross_scope_timeline_segments(
        self,
        scope_keys: list[str] | None = None,
    ) -> list[MemoryCrossScopeTimelineSegment]:
        all_records = self._list_runtime_state_records(
            "memory_cross_scope_timeline_segment",
            MemoryCrossScopeTimelineSegment,
            scope_key=None,
        )
        if scope_keys is None:
            return all_records
        expected = set(scope_keys)
        return [record for record in all_records if set(record.scope_keys) == expected]

    def save_memory_project_state_snapshot(self, record: MemoryProjectStateSnapshot) -> None:
        self._save_runtime_state_record(
            "memory_project_state_snapshot",
            record.snapshot_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_project_state_snapshots(self, scope_key: str | None = None) -> list[MemoryProjectStateSnapshot]:
        return self._list_runtime_state_records(
            "memory_project_state_snapshot",
            MemoryProjectStateSnapshot,
            scope_key=scope_key,
        )

    def save_memory_contradiction_repair_record(self, record: MemoryContradictionRepairRecord) -> None:
        scope_key = "|".join(record.scope_keys)
        self._save_runtime_state_record(
            "memory_contradiction_repair_record",
            record.repair_id,
            scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_contradiction_repair_records(
        self,
        scope_keys: list[str] | None = None,
    ) -> list[MemoryContradictionRepairRecord]:
        records = self._list_runtime_state_records(
            "memory_contradiction_repair_record",
            MemoryContradictionRepairRecord,
            scope_key=None,
        )
        if scope_keys is None:
            return records
        expected = set(scope_keys)
        return [record for record in records if set(record.scope_keys) == expected]

    def save_memory_admission_canary_run(self, record: MemoryAdmissionCanaryRun) -> None:
        self._save_runtime_state_record(
            "memory_admission_canary_run",
            record.run_id,
            record.scope_key,
            record.completed_at.isoformat(),
            record,
        )

    def list_memory_admission_canary_runs(self, scope_key: str | None = None) -> list[MemoryAdmissionCanaryRun]:
        return self._list_runtime_state_records(
            "memory_admission_canary_run",
            MemoryAdmissionCanaryRun,
            scope_key=scope_key,
        )

    def save_memory_selective_rebuild_run(self, record: MemorySelectiveRebuildRun) -> None:
        self._save_runtime_state_record(
            "memory_selective_rebuild_run",
            record.run_id,
            record.scope_key,
            record.completed_at.isoformat(),
            record,
        )

    def list_memory_selective_rebuild_runs(self, scope_key: str | None = None) -> list[MemorySelectiveRebuildRun]:
        return self._list_runtime_state_records(
            "memory_selective_rebuild_run",
            MemorySelectiveRebuildRun,
            scope_key=scope_key,
        )

    def save_memory_repair_canary_run(self, record: MemoryRepairCanaryRun) -> None:
        scope_key = "|".join(record.scope_keys)
        self._save_runtime_state_record(
            "memory_repair_canary_run",
            record.run_id,
            scope_key,
            record.completed_at.isoformat(),
            record,
        )

    def list_memory_repair_canary_runs(
        self,
        scope_keys: list[str] | None = None,
    ) -> list[MemoryRepairCanaryRun]:
        records = self._list_runtime_state_records(
            "memory_repair_canary_run",
            MemoryRepairCanaryRun,
            scope_key=None,
        )
        if scope_keys is None:
            return records
        expected = set(scope_keys)
        return [record for record in records if set(record.scope_keys) == expected]

    def save_memory_repair_safety_assessment(self, record: MemoryRepairSafetyAssessment) -> None:
        scope_key = "|".join(record.scope_keys)
        self._save_runtime_state_record(
            "memory_repair_safety_assessment",
            record.assessment_id,
            scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_repair_safety_assessments(
        self,
        scope_keys: list[str] | None = None,
    ) -> list[MemoryRepairSafetyAssessment]:
        records = self._list_runtime_state_records(
            "memory_repair_safety_assessment",
            MemoryRepairSafetyAssessment,
            scope_key=None,
        )
        if scope_keys is None:
            return records
        expected = set(scope_keys)
        return [record for record in records if set(record.scope_keys) == expected]

    def save_memory_repair_learning_state(self, record: MemoryRepairLearningState) -> None:
        scope_key = "|".join(record.scope_keys)
        self._save_runtime_state_record(
            "memory_repair_learning_state",
            record.learning_id,
            scope_key,
            record.trained_at.isoformat(),
            record,
        )

    def list_memory_repair_learning_states(
        self,
        scope_keys: list[str] | None = None,
    ) -> list[MemoryRepairLearningState]:
        records = self._list_runtime_state_records(
            "memory_repair_learning_state",
            MemoryRepairLearningState,
            scope_key=None,
        )
        if scope_keys is None:
            return records
        expected = set(scope_keys)
        return [record for record in records if set(record.scope_keys) == expected]

    def save_memory_repair_action_run(self, record: MemoryRepairActionRun) -> None:
        self._save_runtime_state_record(
            "memory_repair_action_run",
            record.run_id,
            record.repair_id,
            record.completed_at.isoformat(),
            record,
        )

    def list_memory_repair_action_runs(self, repair_id: str | None = None) -> list[MemoryRepairActionRun]:
        records = self._list_runtime_state_records(
            "memory_repair_action_run",
            MemoryRepairActionRun,
            scope_key=repair_id,
        )
        if repair_id is None:
            return records
        return [record for record in records if record.repair_id == repair_id]

    def save_memory_repair_rollout_analytics_record(self, record: MemoryRepairRolloutAnalyticsRecord) -> None:
        self._save_runtime_state_record(
            "memory_repair_rollout_analytics_record",
            record.analytics_id,
            record.repair_id,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_repair_rollout_analytics_records(
        self,
        repair_id: str | None = None,
    ) -> list[MemoryRepairRolloutAnalyticsRecord]:
        records = self._list_runtime_state_records(
            "memory_repair_rollout_analytics_record",
            MemoryRepairRolloutAnalyticsRecord,
            scope_key=repair_id,
        )
        if repair_id is None:
            return records
        return [record for record in records if record.repair_id == repair_id]

    def save_memory_operations_loop_run(self, record: MemoryOperationsLoopRun) -> None:
        self._save_runtime_state_record(
            "memory_operations_loop_run",
            record.run_id,
            record.scope_key,
            record.completed_at.isoformat(),
            record,
        )

    def list_memory_operations_loop_runs(self, scope_key: str | None = None) -> list[MemoryOperationsLoopRun]:
        return self._list_runtime_state_records(
            "memory_operations_loop_run",
            MemoryOperationsLoopRun,
            scope_key=scope_key,
        )

    def save_memory_admission_promotion_recommendation(self, record: MemoryAdmissionPromotionRecommendation) -> None:
        self._save_runtime_state_record(
            "memory_admission_promotion_recommendation",
            record.recommendation_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_admission_promotion_recommendations(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryAdmissionPromotionRecommendation]:
        return self._list_runtime_state_records(
            "memory_admission_promotion_recommendation",
            MemoryAdmissionPromotionRecommendation,
            scope_key=scope_key,
        )

    def save_memory_operations_loop_schedule(self, record: MemoryOperationsLoopSchedule) -> None:
        self._save_runtime_state_record(
            "memory_operations_loop_schedule",
            record.schedule_id,
            record.scope_key,
            record.updated_at.isoformat(),
            record,
        )

    def list_memory_operations_loop_schedules(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryOperationsLoopSchedule]:
        return self._list_runtime_state_records(
            "memory_operations_loop_schedule",
            MemoryOperationsLoopSchedule,
            scope_key=scope_key,
        )

    def save_memory_operations_loop_recovery_record(self, record: MemoryOperationsLoopRecoveryRecord) -> None:
        self._save_runtime_state_record(
            "memory_operations_loop_recovery_record",
            record.recovery_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_operations_loop_recovery_records(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryOperationsLoopRecoveryRecord]:
        return self._list_runtime_state_records(
            "memory_operations_loop_recovery_record",
            MemoryOperationsLoopRecoveryRecord,
            scope_key=scope_key,
        )

    def save_memory_operations_diagnostic_record(self, record: MemoryOperationsDiagnosticRecord) -> None:
        self._save_runtime_state_record(
            "memory_operations_diagnostic_record",
            record.diagnostic_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_operations_diagnostic_records(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryOperationsDiagnosticRecord]:
        return self._list_runtime_state_records(
            "memory_operations_diagnostic_record",
            MemoryOperationsDiagnosticRecord,
            scope_key=scope_key,
        )

    def save_memory_artifact_backend_health_record(self, record: MemoryArtifactBackendHealthRecord) -> None:
        self._save_runtime_state_record(
            "memory_artifact_backend_health_record",
            record.health_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_artifact_backend_health_records(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryArtifactBackendHealthRecord]:
        return self._list_runtime_state_records(
            "memory_artifact_backend_health_record",
            MemoryArtifactBackendHealthRecord,
            scope_key=scope_key,
        )

    def save_memory_artifact_backend_repair_run(self, record: MemoryArtifactBackendRepairRun) -> None:
        self._save_runtime_state_record(
            "memory_artifact_backend_repair_run",
            record.run_id,
            record.scope_key,
            record.completed_at.isoformat(),
            record,
        )

    def list_memory_artifact_backend_repair_runs(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryArtifactBackendRepairRun]:
        return self._list_runtime_state_records(
            "memory_artifact_backend_repair_run",
            MemoryArtifactBackendRepairRun,
            scope_key=scope_key,
        )

    def save_memory_artifact_drift_record(self, record: MemoryArtifactDriftRecord) -> None:
        self._save_runtime_state_record(
            "memory_artifact_drift_record",
            record.drift_id,
            record.scope_key,
            record.detected_at.isoformat(),
            record,
        )

    def list_memory_artifact_drift_records(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryArtifactDriftRecord]:
        return self._list_runtime_state_records(
            "memory_artifact_drift_record",
            MemoryArtifactDriftRecord,
            scope_key=scope_key,
        )

    def save_memory_maintenance_recommendation(self, record: MemoryMaintenanceRecommendation) -> None:
        self._save_runtime_state_record(
            "memory_maintenance_recommendation",
            record.recommendation_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_maintenance_recommendations(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceRecommendation]:
        return self._list_runtime_state_records(
            "memory_maintenance_recommendation",
            MemoryMaintenanceRecommendation,
            scope_key=scope_key,
        )

    def save_memory_maintenance_run(self, record: MemoryMaintenanceRun) -> None:
        self._save_runtime_state_record(
            "memory_maintenance_run",
            record.run_id,
            record.scope_key,
            record.completed_at.isoformat(),
            record,
        )

    def list_memory_maintenance_runs(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceRun]:
        return self._list_runtime_state_records(
            "memory_maintenance_run",
            MemoryMaintenanceRun,
            scope_key=scope_key,
        )

    def save_memory_maintenance_learning_state(self, record: MemoryMaintenanceLearningState) -> None:
        self._save_runtime_state_record(
            "memory_maintenance_learning_state",
            record.learning_id,
            record.scope_key,
            record.trained_at.isoformat(),
            record,
        )

    def list_memory_maintenance_learning_states(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceLearningState]:
        return self._list_runtime_state_records(
            "memory_maintenance_learning_state",
            MemoryMaintenanceLearningState,
            scope_key=scope_key,
        )

    def save_memory_maintenance_canary_run(self, record: MemoryMaintenanceCanaryRun) -> None:
        self._save_runtime_state_record(
            "memory_maintenance_canary_run",
            record.run_id,
            record.scope_key,
            record.completed_at.isoformat(),
            record,
        )

    def list_memory_maintenance_canary_runs(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceCanaryRun]:
        return self._list_runtime_state_records(
            "memory_maintenance_canary_run",
            MemoryMaintenanceCanaryRun,
            scope_key=scope_key,
        )

    def save_memory_maintenance_promotion_recommendation(self, record: MemoryMaintenancePromotionRecommendation) -> None:
        self._save_runtime_state_record(
            "memory_maintenance_promotion_recommendation",
            record.recommendation_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_maintenance_promotion_recommendations(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenancePromotionRecommendation]:
        return self._list_runtime_state_records(
            "memory_maintenance_promotion_recommendation",
            MemoryMaintenancePromotionRecommendation,
            scope_key=scope_key,
        )

    def save_memory_maintenance_controller_state(self, record: MemoryMaintenanceControllerState) -> None:
        self._save_runtime_state_record(
            "memory_maintenance_controller_state",
            record.state_id,
            record.scope_key,
            record.updated_at.isoformat(),
            record,
        )

    def list_memory_maintenance_controller_states(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceControllerState]:
        return self._list_runtime_state_records(
            "memory_maintenance_controller_state",
            MemoryMaintenanceControllerState,
            scope_key=scope_key,
        )

    def save_memory_maintenance_rollout_record(self, record: MemoryMaintenanceRolloutRecord) -> None:
        self._save_runtime_state_record(
            "memory_maintenance_rollout_record",
            record.rollout_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_maintenance_rollout_records(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceRolloutRecord]:
        return self._list_runtime_state_records(
            "memory_maintenance_rollout_record",
            MemoryMaintenanceRolloutRecord,
            scope_key=scope_key,
        )

    def save_memory_maintenance_worker_record(self, record: MemoryMaintenanceWorkerRecord) -> None:
        self._save_runtime_state_record(
            "memory_maintenance_worker_record",
            record.worker_id,
            f"maintenance-worker:{record.worker_id}",
            record.last_heartbeat_at.isoformat(),
            record,
        )

    def list_memory_maintenance_worker_records(self) -> list[MemoryMaintenanceWorkerRecord]:
        return self._list_runtime_state_records(
            "memory_maintenance_worker_record",
            MemoryMaintenanceWorkerRecord,
            scope_key=None,
        )

    def save_memory_maintenance_schedule(self, record: MemoryMaintenanceSchedule) -> None:
        self._save_runtime_state_record(
            "memory_maintenance_schedule",
            record.schedule_id,
            record.scope_key,
            record.updated_at.isoformat(),
            record,
        )

    def list_memory_maintenance_schedules(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceSchedule]:
        return self._list_runtime_state_records(
            "memory_maintenance_schedule",
            MemoryMaintenanceSchedule,
            scope_key=scope_key,
        )

    def save_memory_maintenance_recovery_record(self, record: MemoryMaintenanceRecoveryRecord) -> None:
        self._save_runtime_state_record(
            "memory_maintenance_recovery_record",
            record.recovery_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_maintenance_recovery_records(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceRecoveryRecord]:
        return self._list_runtime_state_records(
            "memory_maintenance_recovery_record",
            MemoryMaintenanceRecoveryRecord,
            scope_key=scope_key,
        )

    def save_memory_maintenance_analytics_record(self, record: MemoryMaintenanceAnalyticsRecord) -> None:
        self._save_runtime_state_record(
            "memory_maintenance_analytics_record",
            record.analytics_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_maintenance_analytics_records(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceAnalyticsRecord]:
        return self._list_runtime_state_records(
            "memory_maintenance_analytics_record",
            MemoryMaintenanceAnalyticsRecord,
            scope_key=scope_key,
        )

    def save_memory_maintenance_incident_record(self, record: MemoryMaintenanceIncidentRecord) -> None:
        self._save_runtime_state_record(
            "memory_maintenance_incident_record",
            record.incident_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_maintenance_incident_records(
        self,
        scope_key: str | None = None,
    ) -> list[MemoryMaintenanceIncidentRecord]:
        return self._list_runtime_state_records(
            "memory_maintenance_incident_record",
            MemoryMaintenanceIncidentRecord,
            scope_key=scope_key,
        )

    def save_skill_capsule(self, capsule: SkillCapsule) -> None:
        self._insert_or_replace(
            "skill_capsules",
            {
                "skill_id": capsule.skill_id,
                "promotion_status": capsule.promotion_status,
                "record_version": capsule.version,
                "payload_json": self.dumps(capsule.to_dict()),
            },
        )

    def save_memory_lifecycle_trace(self, trace: MemoryLifecycleTrace) -> None:
        self._save_runtime_state_record(
            "memory_lifecycle_trace",
            trace.trace_id,
            trace.scope_key,
            trace.created_at.isoformat(),
            trace,
        )

    def list_memory_lifecycle_traces(self, scope_key: str | None = None) -> list[MemoryLifecycleTrace]:
        return self._list_runtime_state_records("memory_lifecycle_trace", MemoryLifecycleTrace, scope_key=scope_key)

    def save_memory_policy_mining_run(self, record: MemoryPolicyMiningRun) -> None:
        self._save_runtime_state_record(
            "memory_policy_mining_run",
            record.run_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_policy_mining_runs(self, scope_key: str | None = None) -> list[MemoryPolicyMiningRun]:
        return self._list_runtime_state_records("memory_policy_mining_run", MemoryPolicyMiningRun, scope_key=scope_key)

    def save_memory_policy_analytics_record(self, record: MemoryPolicyAnalyticsRecord) -> None:
        self._save_runtime_state_record(
            "memory_policy_analytics_record",
            record.analytics_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_policy_analytics_records(self, scope_key: str | None = None) -> list[MemoryPolicyAnalyticsRecord]:
        return self._list_runtime_state_records(
            "memory_policy_analytics_record",
            MemoryPolicyAnalyticsRecord,
            scope_key=scope_key,
        )

    def save_evolution_candidate(self, candidate: EvolutionCandidate) -> None:
        self._insert_or_replace(
            "evolution_candidates",
            {
                "candidate_id": candidate.candidate_id,
                "candidate_type": candidate.candidate_type,
                "target_component": candidate.target_component,
                "promotion_result": candidate.promotion_result,
                "record_version": candidate.version,
                "payload_json": self.dumps(candidate.to_dict()),
            },
        )

    def load_evolution_candidate(self, candidate_id: str) -> EvolutionCandidate:
        row = self._fetchone("SELECT * FROM evolution_candidates WHERE candidate_id = ?", (candidate_id,))
        return self._model_from_row("evolution_candidates", row, EvolutionCandidate)

    def list_evolution_candidates(self) -> list[EvolutionCandidate]:
        rows = self._fetchall("SELECT * FROM evolution_candidates ORDER BY candidate_id ASC", ())
        return [self._model_from_row("evolution_candidates", row, EvolutionCandidate) for row in rows]

    def save_evaluation_run(self, run: EvaluationRun) -> None:
        self._insert_or_replace(
            "evaluation_runs",
            {
                "run_id": run.run_id,
                "candidate_id": run.candidate_id,
                "suite_name": run.suite_name,
                "status": run.status,
                "completed_at": run.completed_at.isoformat(),
                "record_version": run.version,
                "payload_json": self.dumps(run.to_dict()),
            },
        )

    def list_evaluation_runs(self, candidate_id: str) -> list[EvaluationRun]:
        rows = self._fetchall(
            "SELECT * FROM evaluation_runs WHERE candidate_id = ? ORDER BY completed_at ASC",
            (candidate_id,),
        )
        return [self._model_from_row("evaluation_runs", row, EvaluationRun) for row in rows]

    def save_canary_run(self, run: CanaryRun) -> None:
        self._insert_or_replace(
            "canary_runs",
            {
                "run_id": run.run_id,
                "candidate_id": run.candidate_id,
                "scope": run.scope,
                "status": run.status,
                "completed_at": run.completed_at.isoformat(),
                "record_version": run.version,
                "payload_json": self.dumps(run.to_dict()),
            },
        )

    def list_canary_runs(self, candidate_id: str) -> list[CanaryRun]:
        rows = self._fetchall(
            "SELECT * FROM canary_runs WHERE candidate_id = ? ORDER BY completed_at ASC",
            (candidate_id,),
        )
        return [self._model_from_row("canary_runs", row, CanaryRun) for row in rows]

    def evidence_lineage(self, task_id: str, node_id: str) -> dict[str, list[Any]]:
        edge_rows = self._fetchall(
            """
            WITH RECURSIVE ancestry(edge_id, source_node_id, target_node_id) AS (
                SELECT edge_id, source_node_id, target_node_id
                FROM evidence_edges
                WHERE task_id = ? AND target_node_id = ?
                UNION ALL
                SELECT e.edge_id, e.source_node_id, e.target_node_id
                FROM evidence_edges e
                JOIN ancestry a ON e.target_node_id = a.source_node_id
                WHERE e.task_id = ?
            )
            SELECT * FROM evidence_edges
            WHERE edge_id IN (SELECT edge_id FROM ancestry)
            ORDER BY rowid ASC
            """,
            (task_id, node_id, task_id),
        )
        node_ids = {node_id}
        for row in edge_rows:
            node_ids.add(str(row["source_node_id"]))
            node_ids.add(str(row["target_node_id"]))
        if not node_ids:
            node_ids.add(node_id)
        placeholders = ", ".join("?" for _ in node_ids)
        node_rows = self._fetchall(
            f"SELECT * FROM evidence_nodes WHERE task_id = ? AND node_id IN ({placeholders}) ORDER BY created_at ASC",
            (task_id, *sorted(node_ids)),
        )
        return {
            "nodes": [self._model_from_row("evidence_nodes", row, EvidenceNode) for row in node_rows],
            "edges": [self._model_from_row("evidence_edges", row, EvidenceEdge) for row in edge_rows],
        }

    def replay_task(self, task_id: str) -> dict[str, Any]:
        task = self.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        contract = None if task["contract_id"] is None else self.load_contract(str(task["contract_id"]))
        plan = self.load_plan(task_id)
        lattice = self.load_contract_lattice(task_id)
        evidence_graph = self.load_evidence_graph(task_id)
        claims = self.load_claims(task_id)
        validation_report = self.load_latest_validation_report(task_id)
        handoff = self.latest_handoff_packet(task_id)
        context_compaction = self.latest_context_compaction(task_id)
        working_set = self.latest_continuity_working_set(task_id)
        return {
            "task": task,
            "contract": None if contract is None else contract.to_dict(),
            "plan": None if plan is None else plan.to_dict(),
            "contract_lattice": None if lattice is None else lattice.to_dict(),
            "evidence_graph": evidence_graph.to_dict(),
            "claims": [claim.to_dict() for claim in claims],
            "validation_report": None if validation_report is None else validation_report.to_dict(),
            "audit_events": [event.to_dict() for event in self.query_audit(task_id=task_id)],
            "execution_receipts": [receipt.to_dict() for receipt in self.list_execution_receipts(task_id)],
            "routing_receipts": [receipt.to_dict() for receipt in self.list_routing_receipts(task_id)],
            "provider_usage_records": [record.to_dict() for record in self.list_provider_usage_records(task_id)],
            "provider_capabilities": [item.to_dict() for item in self.list_provider_capabilities()],
            "provider_scorecards": [item.to_dict() for item in self.list_provider_scorecards()],
            "routing_decisions": [item.to_dict() for item in self.list_routing_decisions(task_id)],
            "tool_invocations": [invocation.to_dict() for invocation in self.list_tool_invocations(task_id)],
            "tool_results": [result.to_dict() for result in self.list_tool_results(task_id)],
            "plan_revisions": [item.to_dict() for item in self.list_plan_revisions(task_id)],
            "execution_branches": [item.to_dict() for item in self.list_execution_branches(task_id)],
            "scheduler_state": None
            if self.latest_scheduler_state(task_id) is None
            else self.latest_scheduler_state(task_id).to_dict(),
            "budget_policy": None if self.load_budget_policy(task_id) is None else self.load_budget_policy(task_id).to_dict(),
            "budget_ledger": None if self.latest_budget_ledger(task_id) is None else self.latest_budget_ledger(task_id).to_dict(),
            "budget_events": [item.to_dict() for item in self.list_budget_events(task_id)],
            "budget_consumption": [item.to_dict() for item in self.list_budget_consumption_records(task_id)],
            "execution_mode": None if self.latest_execution_mode(task_id) is None else self.latest_execution_mode(task_id).to_dict(),
            "governance_events": [item.to_dict() for item in self.list_governance_events(task_id)],
            "concurrency_state": None if self.latest_concurrency_state(task_id) is None else self.latest_concurrency_state(task_id).to_dict(),
            "queue_items": [item.to_dict() for item in self.list_queue_items()],
            "queue_leases": [item.to_dict() for item in self.list_queue_leases()],
            "admission_decisions": [item.to_dict() for item in self.list_admission_decisions(task_id)],
            "dispatch_records": [item.to_dict() for item in self.list_dispatch_records(task_id)],
            "capacity_snapshot": None if self.latest_capacity_snapshot() is None else self.latest_capacity_snapshot().to_dict(),
            "load_shedding_events": [item.to_dict() for item in self.list_load_shedding_events(task_id)],
            "global_execution_mode": None if self.latest_global_execution_mode() is None else self.latest_global_execution_mode().to_dict(),
            "operator_overrides": [item.to_dict() for item in self.list_operator_overrides()],
            "provider_health_records": [item.to_dict() for item in self.list_provider_health_records()],
            "provider_health_snapshot": None if self.latest_provider_health_snapshot() is None else self.latest_provider_health_snapshot().to_dict(),
            "rate_limit_states": [
                item.to_dict()
                for item in [
                    self.load_rate_limit_state(policy.provider_name)
                    for policy in self.list_provider_availability_policies()
                ]
                if item is not None
            ],
            "provider_cooldown_windows": [
                item.to_dict()
                for item in [
                    self.load_provider_cooldown_window(policy.provider_name)
                    for policy in self.list_provider_availability_policies()
                ]
                if item is not None
            ],
            "provider_degradation_events": [item.to_dict() for item in self.list_provider_degradation_events()],
            "provider_pool_state": None if self.latest_provider_pool_state() is None else self.latest_provider_pool_state().to_dict(),
            "provider_pressure_snapshot": None if self.latest_provider_pressure_snapshot() is None else self.latest_provider_pressure_snapshot().to_dict(),
            "provider_capacity_records": [item.to_dict() for item in self.list_provider_capacity_records()],
            "provider_reservations": [item.to_dict() for item in self.list_provider_reservations()],
            "provider_balance_decisions": [item.to_dict() for item in self.list_provider_balance_decisions(task_id)],
            "provider_pool_events": [item.to_dict() for item in self.list_provider_pool_events()],
            "provider_fairness_records": [item.to_dict() for item in self.list_provider_fairness_records()],
            "policy_scopes": [item.to_dict() for item in self.list_policy_scopes()],
            "policy_candidates": [item.to_dict() for item in self.list_policy_candidates()],
            "policy_versions": [item.to_dict() for scope in self.list_policy_scopes() for item in self.list_policy_versions(scope.scope_id)],
            "policy_promotion_runs": [item.to_dict() for item in self.list_policy_promotion_runs()],
            "policy_rollbacks": [item.to_dict() for item in self.list_policy_rollback_records()],
            "worker_registry": [item.to_dict() for item in self.list_workers()],
            "host_records": [item.to_dict() for item in self.list_host_records()],
            "worker_host_bindings": [item.to_dict() for item in self.list_worker_host_bindings()],
            "worker_endpoints": [item.to_dict() for item in self.list_worker_endpoints()],
            "worker_capabilities": [item.to_dict() for item in self.list_worker_capabilities()],
            "worker_heartbeats": [
                heartbeat.to_dict()
                for worker in self.list_workers()
                if (heartbeat := self.latest_worker_heartbeat(worker.worker_id)) is not None
            ],
            "worker_pressure_snapshot": None if self.latest_worker_pressure_snapshot() is None else self.latest_worker_pressure_snapshot().to_dict(),
            "renewal_attempts": [item.to_dict() for item in self.list_renewal_attempts()],
            "lease_expiry_forecasts": [item.to_dict() for item in [self.latest_lease_expiry_forecast(lease.lease_id) for lease in self.list_queue_leases()] if item is not None],
            "lease_contention_records": [item.to_dict() for item in self.list_lease_contention_records()],
            "work_steal_decisions": [item.to_dict() for item in self.list_work_steal_decisions()],
            "lease_transfer_records": [item.to_dict() for item in self.list_lease_transfer_records()],
            "ownership_conflict_events": [item.to_dict() for item in self.list_ownership_conflict_events()],
            "lease_ownerships": [item.to_dict() for item in self.list_lease_ownerships()],
            "dispatch_ownerships": [item.to_dict() for item in self.list_dispatch_ownerships()],
            "backend_descriptors": [item.to_dict() for item in self.list_backend_descriptors()],
            "backend_health_records": [item.to_dict() for item in self.list_backend_health_records()],
            "backend_pressure_snapshots": [item.to_dict() for item in self.list_backend_pressure_snapshots()],
            "auth_scopes": [item.to_dict() for item in self.list_auth_scopes()],
            "auth_events": [item.to_dict() for item in self.list_auth_events()],
            "auth_failure_events": [item.to_dict() for item in self.list_auth_failure_events()],
            "service_principals": [item.to_dict() for item in self.list_service_principals()],
            "service_credentials": [item.to_dict() for item in self.list_service_credentials()],
            "credential_rotation_records": [item.to_dict() for item in self.list_credential_rotation_records()],
            "handoff": None if handoff is None else handoff.to_dict(),
            "context_compaction": None if context_compaction is None else context_compaction.to_dict(),
            "continuity_working_set": None if working_set is None else working_set.to_dict(),
            "open_questions": [item.to_dict() for item in self.list_open_questions(task_id)],
            "next_actions": [item.to_dict() for item in self.list_next_actions(task_id)],
            "approval_requests": [item.to_dict() for item in self.list_approval_requests(task_id=task_id)],
            "approval_decisions": [item.to_dict() for item in self.list_approval_decisions(task_id=task_id)],
            "remote_approval_operations": [item.to_dict() for item in self.list_remote_approval_operations(task_id=task_id)],
            "telemetry": [item.to_dict() for item in self.query_telemetry(task_id=task_id)],
            "delivery": None if task["result"] is None else task["result"].get("delivery"),
        }

    def incident_packet(self, task_id: str) -> dict[str, Any]:
        checkpoint = self.latest_checkpoint(task_id)
        return {
            "task": self.get_task(task_id),
            "incidents": [incident.to_dict() for incident in self.list_incidents(task_id)],
            "latest_checkpoint": None
            if checkpoint is None
            else {"record": checkpoint[0].to_dict(), "state": checkpoint[1]},
            "audit_events": [event.to_dict() for event in self.query_audit(task_id=task_id)],
            "execution_receipts": [receipt.to_dict() for receipt in self.list_execution_receipts(task_id)],
            "handoff": None if self.latest_handoff_packet(task_id) is None else self.latest_handoff_packet(task_id).to_dict(),
            "open_questions": [item.to_dict() for item in self.list_open_questions(task_id)],
            "next_actions": [item.to_dict() for item in self.list_next_actions(task_id)],
            "recovery_recommendation": (
                "resume from latest checkpoint"
                if checkpoint is not None
                else "inspect audit and recreate task context"
            ),
        }

    def save_evidence_delta(self, delta: EvidenceDeltaSummary) -> None:
        self._insert_or_replace(
            "evidence_deltas",
            {
                "delta_id": delta.delta_id,
                "task_id": delta.task_id,
                "checkpoint_id": delta.checkpoint_id,
                "created_at": delta.created_at.isoformat(),
                "record_version": delta.version,
                "payload_json": self.dumps(delta.to_dict()),
            },
        )

    def latest_evidence_delta(self, task_id: str) -> EvidenceDeltaSummary | None:
        row = self._fetchone(
            "SELECT * FROM evidence_deltas WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
            (task_id,),
        )
        return None if row is None else self._model_from_row("evidence_deltas", row, EvidenceDeltaSummary)

    def save_handoff_packet(
        self,
        packet: HandoffPacket,
        version: HandoffPacketVersion,
        sections: list[HandoffSummarySection],
    ) -> None:
        self._insert_or_replace(
            "handoff_packets",
            {
                "packet_id": packet.packet_id,
                "task_id": packet.task_id,
                "contract_id": packet.contract_id,
                "plan_graph_id": packet.plan_graph_id,
                "created_at": packet.created_at.isoformat(),
                "record_version": packet.version,
                "payload_json": self.dumps(packet.to_dict()),
            },
        )
        self._insert_or_replace(
            "handoff_packet_versions",
            {
                "packet_version_id": version.packet_version_id,
                "packet_id": version.packet_id,
                "task_id": version.task_id,
                "created_at": version.created_at.isoformat(),
                "record_version": version.version,
                "payload_json": self.dumps(version.to_dict()),
            },
        )
        with self._connect() as connection:
            connection.execute("DELETE FROM handoff_sections WHERE packet_id = ?", (packet.packet_id,))
            for section in sections:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO handoff_sections (
                        section_id, packet_id, priority, record_version, payload_json
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        section.section_id,
                        packet.packet_id,
                        section.priority,
                        section.version,
                        self.dumps(section.to_dict()),
                    ),
                )
            connection.commit()

    def latest_handoff_packet(self, task_id: str) -> HandoffPacket | None:
        row = self._fetchone(
            "SELECT * FROM handoff_packets WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
            (task_id,),
        )
        if row is None:
            return None
        packet = self._model_from_row("handoff_packets", row, HandoffPacket)
        section_rows = self._fetchall(
            "SELECT * FROM handoff_sections WHERE packet_id = ? ORDER BY priority ASC",
            (packet.packet_id,),
        )
        packet.summary_sections = [
            self._model_from_row("handoff_sections", section_row, HandoffSummarySection)
            for section_row in section_rows
        ]
        return packet

    def save_open_questions(self, task_id: str, questions: list[OpenQuestion]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM open_questions WHERE task_id = ?", (task_id,))
            for question in questions:
                connection.execute(
                    """
                    INSERT INTO open_questions (
                        question_id, task_id, contract_id, related_plan_node, blocking_severity,
                        owner_role, status, record_version, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        question.question_id,
                        task_id,
                        question.contract_id,
                        question.related_plan_node,
                        question.blocking_severity,
                        question.owner_role,
                        question.status,
                        question.version,
                        self.dumps(question.to_dict()),
                    ),
                )
            connection.commit()

    def list_open_questions(self, task_id: str, status: str | None = None) -> list[OpenQuestion]:
        query = "SELECT * FROM open_questions WHERE task_id = ?"
        params: tuple[Any, ...] = (task_id,)
        if status is not None:
            query += " AND status = ?"
            params = (task_id, status)
        query += " ORDER BY rowid ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("open_questions", row, OpenQuestion) for row in rows]

    def save_next_actions(self, task_id: str, actions: list[NextAction]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM next_actions WHERE task_id = ?", (task_id,))
            for action in actions:
                connection.execute(
                    """
                    INSERT INTO next_actions (
                        action_id, task_id, contract_id, related_plan_node, urgency,
                        status, record_version, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        action.action_id,
                        task_id,
                        action.contract_id,
                        action.related_plan_node,
                        action.urgency,
                        action.status,
                        action.version,
                        self.dumps(action.to_dict()),
                    ),
                )
            connection.commit()

    def list_next_actions(self, task_id: str, status: str | None = None) -> list[NextAction]:
        query = "SELECT * FROM next_actions WHERE task_id = ?"
        params: tuple[Any, ...] = (task_id,)
        if status is not None:
            query += " AND status = ?"
            params = (task_id, status)
        query += " ORDER BY rowid ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("next_actions", row, NextAction) for row in rows]

    def save_workspace_snapshot(self, snapshot: WorkspaceSnapshot) -> None:
        self._insert_or_replace(
            "workspace_snapshots",
            {
                "snapshot_id": snapshot.snapshot_id,
                "task_id": snapshot.task_id,
                "created_at": snapshot.created_at.isoformat(),
                "record_version": snapshot.version,
                "payload_json": self.dumps(snapshot.to_dict()),
            },
        )

    def latest_workspace_snapshot(self, task_id: str) -> WorkspaceSnapshot | None:
        row = self._fetchone(
            "SELECT * FROM workspace_snapshots WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
            (task_id,),
        )
        return None if row is None else self._model_from_row("workspace_snapshots", row, WorkspaceSnapshot)

    def save_context_compaction(self, compaction: ContextCompaction) -> None:
        self._insert_or_replace(
            "context_compactions",
            {
                "context_id": compaction.context_id,
                "task_id": compaction.task_id,
                "created_at": compaction.created_at.isoformat(),
                "record_version": compaction.version,
                "payload_json": self.dumps(compaction.to_dict()),
            },
        )

    def latest_context_compaction(self, task_id: str) -> ContextCompaction | None:
        row = self._fetchone(
            "SELECT * FROM context_compactions WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
            (task_id,),
        )
        return None if row is None else self._model_from_row("context_compactions", row, ContextCompaction)

    def save_prompt_budget_allocation(self, allocation: PromptBudgetAllocation) -> None:
        self._insert_or_replace(
            "prompt_budget_allocations",
            {
                "allocation_id": allocation.allocation_id,
                "task_id": allocation.task_id,
                "role_name": allocation.role_name,
                "created_at": allocation.created_at.isoformat(),
                "record_version": allocation.version,
                "payload_json": self.dumps(allocation.to_dict()),
            },
        )

    def latest_prompt_budget_allocation(
        self,
        task_id: str,
        role_name: str | None = None,
    ) -> PromptBudgetAllocation | None:
        query = "SELECT * FROM prompt_budget_allocations WHERE task_id = ?"
        params: tuple[Any, ...] = (task_id,)
        if role_name is not None:
            query += " AND role_name = ?"
            params = (task_id, role_name)
        query += " ORDER BY created_at DESC LIMIT 1"
        row = self._fetchone(query, params)
        return None if row is None else self._model_from_row("prompt_budget_allocations", row, PromptBudgetAllocation)

    def save_continuity_working_set(self, working_set: ContinuityWorkingSet) -> None:
        self._insert_or_replace(
            "continuity_working_sets",
            {
                "working_set_id": working_set.working_set_id,
                "task_id": working_set.task_id,
                "handoff_packet_id": working_set.handoff_packet_id,
                "created_at": working_set.created_at.isoformat(),
                "record_version": working_set.version,
                "payload_json": self.dumps(working_set.to_dict()),
            },
        )

    def latest_continuity_working_set(self, task_id: str) -> ContinuityWorkingSet | None:
        row = self._fetchone(
            "SELECT * FROM continuity_working_sets WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
            (task_id,),
        )
        return None if row is None else self._model_from_row("continuity_working_sets", row, ContinuityWorkingSet)

    def save_plan_revision(self, revision: PlanRevision) -> None:
        self._insert_or_replace(
            "plan_revisions",
            {
                "revision_id": revision.revision_id,
                "task_id": revision.task_id,
                "plan_graph_id": revision.plan_graph_id,
                "cause": revision.cause,
                "branch_id": revision.branch_id,
                "created_at": revision.created_at.isoformat(),
                "record_version": revision.version,
                "payload_json": self.dumps(revision.to_dict()),
            },
        )

    def list_plan_revisions(self, task_id: str) -> list[PlanRevision]:
        rows = self._fetchall(
            "SELECT * FROM plan_revisions WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        return [self._model_from_row("plan_revisions", row, PlanRevision) for row in rows]

    def save_execution_branch(self, branch: ExecutionBranch) -> None:
        self._insert_or_replace(
            "execution_branches",
            {
                "branch_id": branch.branch_id,
                "task_id": branch.task_id,
                "plan_graph_id": branch.plan_graph_id,
                "parent_branch_id": branch.parent_branch_id,
                "status": branch.status,
                "selected": 1 if branch.selected else 0,
                "created_at": branch.created_at.isoformat(),
                "record_version": branch.version,
                "payload_json": self.dumps(branch.to_dict()),
            },
        )

    def list_execution_branches(self, task_id: str) -> list[ExecutionBranch]:
        rows = self._fetchall(
            "SELECT * FROM execution_branches WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        return [self._model_from_row("execution_branches", row, ExecutionBranch) for row in rows]

    def save_scheduler_state(self, state: SchedulerState) -> None:
        self._insert_or_replace(
            "scheduler_states",
            {
                "scheduler_id": state.scheduler_id,
                "task_id": state.task_id,
                "plan_graph_id": state.plan_graph_id,
                "active_branch_id": state.active_branch_id,
                "status": state.status,
                "updated_at": state.updated_at.isoformat(),
                "record_version": state.version,
                "payload_json": self.dumps(state.to_dict()),
            },
        )

    def latest_scheduler_state(self, task_id: str) -> SchedulerState | None:
        row = self._fetchone(
            "SELECT * FROM scheduler_states WHERE task_id = ? ORDER BY updated_at DESC LIMIT 1",
            (task_id,),
        )
        return None if row is None else self._model_from_row("scheduler_states", row, SchedulerState)

    def save_budget_policy(self, policy: BudgetPolicy) -> None:
        self._insert_or_replace(
            "budget_policies",
            {
                "policy_id": policy.policy_id,
                "task_id": policy.task_id,
                "created_at": policy.created_at.isoformat(),
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def load_budget_policy(self, task_id: str) -> BudgetPolicy | None:
        row = self._fetchone(
            "SELECT * FROM budget_policies WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
            (task_id,),
        )
        return None if row is None else self._model_from_row("budget_policies", row, BudgetPolicy)

    def save_budget_ledger(self, ledger: BudgetLedger) -> None:
        self._insert_or_replace(
            "budget_ledgers",
            {
                "ledger_id": ledger.ledger_id,
                "task_id": ledger.task_id,
                "updated_at": ledger.updated_at.isoformat(),
                "record_version": ledger.version,
                "payload_json": self.dumps(ledger.to_dict()),
            },
        )

    def latest_budget_ledger(self, task_id: str) -> BudgetLedger | None:
        row = self._fetchone(
            "SELECT * FROM budget_ledgers WHERE task_id = ? ORDER BY updated_at DESC LIMIT 1",
            (task_id,),
        )
        return None if row is None else self._model_from_row("budget_ledgers", row, BudgetLedger)

    def save_budget_event(self, event: BudgetEvent) -> None:
        self._insert_or_replace(
            "budget_events",
            {
                "event_id": event.event_id,
                "task_id": event.task_id,
                "event_type": event.event_type,
                "created_at": event.created_at.isoformat(),
                "record_version": event.version,
                "payload_json": self.dumps(event.to_dict()),
            },
        )

    def list_budget_events(self, task_id: str) -> list[BudgetEvent]:
        rows = self._fetchall(
            "SELECT * FROM budget_events WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        return [self._model_from_row("budget_events", row, BudgetEvent) for row in rows]

    def save_budget_consumption_record(self, record: BudgetConsumptionRecord) -> None:
        self._insert_or_replace(
            "budget_consumption_records",
            {
                "consumption_id": record.consumption_id,
                "task_id": record.task_id,
                "category": record.category,
                "created_at": record.created_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def list_budget_consumption_records(self, task_id: str) -> list[BudgetConsumptionRecord]:
        rows = self._fetchall(
            "SELECT * FROM budget_consumption_records WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        return [self._model_from_row("budget_consumption_records", row, BudgetConsumptionRecord) for row in rows]

    def save_execution_mode(self, state: ExecutionModeState) -> None:
        self._insert_or_replace(
            "execution_modes",
            {
                "mode_id": state.mode_id,
                "task_id": state.task_id,
                "mode_name": state.mode_name,
                "updated_at": state.updated_at.isoformat(),
                "record_version": state.version,
                "payload_json": self.dumps(state.to_dict()),
            },
        )

    def latest_execution_mode(self, task_id: str) -> ExecutionModeState | None:
        row = self._fetchone(
            "SELECT * FROM execution_modes WHERE task_id = ? ORDER BY updated_at DESC LIMIT 1",
            (task_id,),
        )
        return None if row is None else self._model_from_row("execution_modes", row, ExecutionModeState)

    def save_governance_event(self, event: GovernanceEvent) -> None:
        self._insert_or_replace(
            "governance_events",
            {
                "event_id": event.event_id,
                "task_id": event.task_id,
                "event_type": event.event_type,
                "created_at": event.created_at.isoformat(),
                "record_version": event.version,
                "payload_json": self.dumps(event.to_dict()),
            },
        )

    def list_governance_events(self, task_id: str) -> list[GovernanceEvent]:
        rows = self._fetchall(
            "SELECT * FROM governance_events WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        return [self._model_from_row("governance_events", row, GovernanceEvent) for row in rows]

    def save_concurrency_state(self, state: ConcurrencyState) -> None:
        self._insert_or_replace(
            "concurrency_states",
            {
                "concurrency_id": state.concurrency_id,
                "task_id": state.task_id,
                "updated_at": state.updated_at.isoformat(),
                "record_version": state.version,
                "payload_json": self.dumps(state.to_dict()),
            },
        )

    def latest_concurrency_state(self, task_id: str) -> ConcurrencyState | None:
        row = self._fetchone(
            "SELECT * FROM concurrency_states WHERE task_id = ? ORDER BY updated_at DESC LIMIT 1",
            (task_id,),
        )
        return None if row is None else self._model_from_row("concurrency_states", row, ConcurrencyState)

    def list_concurrency_states(self, task_id: str) -> list[ConcurrencyState]:
        rows = self._fetchall(
            "SELECT * FROM concurrency_states WHERE task_id = ? ORDER BY updated_at ASC",
            (task_id,),
        )
        return [self._model_from_row("concurrency_states", row, ConcurrencyState) for row in rows]

    def save_approval_request(self, request: ApprovalRequest) -> None:
        self._insert_or_replace(
            "approval_requests",
            {
                "request_id": request.request_id,
                "task_id": request.task_id,
                "contract_id": request.contract_id,
                "plan_node_id": request.plan_node_id,
                "status": request.status,
                "risk_level": request.risk_level,
                "expiry_at": None if request.expiry_at is None else request.expiry_at.isoformat(),
                "record_version": request.version,
                "payload_json": self.dumps(request.to_dict()),
            },
        )

    def list_approval_requests(self, task_id: str | None = None, status: str | None = None) -> list[ApprovalRequest]:
        clauses = []
        params: list[Any] = []
        if task_id:
            clauses.append("task_id = ?")
            params.append(task_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        query = "SELECT * FROM approval_requests"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY rowid ASC"
        rows = self._fetchall(query, tuple(params))
        return [self._model_from_row("approval_requests", row, ApprovalRequest) for row in rows]

    def save_approval_decision(self, decision: ApprovalDecision) -> None:
        self._insert_or_replace(
            "approval_decisions",
            {
                "decision_id": decision.decision_id,
                "request_id": decision.request_id,
                "task_id": decision.task_id,
                "plan_node_id": decision.plan_node_id,
                "status": decision.status,
                "decided_at": decision.decided_at.isoformat(),
                "record_version": decision.version,
                "payload_json": self.dumps(decision.to_dict()),
            },
        )

    def list_approval_decisions(self, task_id: str | None = None) -> list[ApprovalDecision]:
        query = "SELECT * FROM approval_decisions"
        params: tuple[Any, ...] = ()
        if task_id:
            query += " WHERE task_id = ?"
            params = (task_id,)
        query += " ORDER BY decided_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("approval_decisions", row, ApprovalDecision) for row in rows]

    def save_human_intervention(self, intervention: HumanIntervention) -> None:
        self._insert_or_replace(
            "human_interventions",
            {
                "intervention_id": intervention.intervention_id,
                "task_id": intervention.task_id,
                "action": intervention.action,
                "created_at": intervention.created_at.isoformat(),
                "record_version": intervention.version,
                "payload_json": self.dumps(intervention.to_dict()),
            },
        )

    def list_human_interventions(self, task_id: str) -> list[HumanIntervention]:
        rows = self._fetchall(
            "SELECT * FROM human_interventions WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        )
        return [self._model_from_row("human_interventions", row, HumanIntervention) for row in rows]

    def save_remote_approval_operation(self, operation: RemoteApprovalOperation) -> None:
        self._insert_or_replace(
            "remote_approval_operations",
            {
                "operation_id": operation.operation_id,
                "request_id": operation.request_id,
                "task_id": operation.task_id,
                "contract_id": operation.contract_id,
                "plan_node_id": operation.plan_node_id,
                "operator": operation.operator,
                "action": operation.action,
                "status": operation.status,
                "created_at": operation.created_at.isoformat(),
                "record_version": operation.version,
                "payload_json": self.dumps(operation.to_dict()),
            },
        )

    def list_remote_approval_operations(self, task_id: str | None = None) -> list[RemoteApprovalOperation]:
        query = "SELECT * FROM remote_approval_operations"
        params: tuple[Any, ...] = ()
        if task_id is not None:
            query += " WHERE task_id = ?"
            params = (task_id,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("remote_approval_operations", row, RemoteApprovalOperation) for row in rows]

    def save_telemetry_event(self, event: TelemetryEvent) -> None:
        self._insert_or_replace(
            "telemetry_events",
            {
                "event_id": event.event_id,
                "task_id": event.task_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "record_version": event.version,
                "payload_json": self.dumps(event.to_dict()),
            },
        )

    def query_telemetry(self, task_id: str | None = None, event_type: str | None = None) -> list[TelemetryEvent]:
        query = "SELECT * FROM telemetry_events"
        clauses = []
        params: list[Any] = []
        if task_id:
            clauses.append("task_id = ?")
            params.append(task_id)
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY timestamp ASC"
        rows = self._fetchall(query, tuple(params))
        return [self._model_from_row("telemetry_events", row, TelemetryEvent) for row in rows]

    def save_observability_metric_snapshot(self, record: ObservabilityMetricSnapshot) -> None:
        self._save_runtime_state_record(
            "observability_metric_snapshot",
            record.snapshot_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_observability_metric_snapshots(self, scope_key: str | None = None) -> list[ObservabilityMetricSnapshot]:
        return self._list_runtime_state_records("observability_metric_snapshot", ObservabilityMetricSnapshot, scope_key=scope_key)

    def save_observability_trend_report(self, record: ObservabilityTrendReport) -> None:
        self._save_runtime_state_record(
            "observability_trend_report",
            record.report_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_observability_trend_reports(self, scope_key: str | None = None) -> list[ObservabilityTrendReport]:
        return self._list_runtime_state_records("observability_trend_report", ObservabilityTrendReport, scope_key=scope_key)

    def save_observability_alert_record(self, record: ObservabilityAlertRecord) -> None:
        self._save_runtime_state_record(
            "observability_alert_record",
            record.alert_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_observability_alert_records(self, scope_key: str | None = None) -> list[ObservabilityAlertRecord]:
        return self._list_runtime_state_records("observability_alert_record", ObservabilityAlertRecord, scope_key=scope_key)

    def save_software_control_telemetry_record(self, record: SoftwareControlTelemetryRecord) -> None:
        self._save_runtime_state_record(
            "software_control_telemetry_record",
            record.telemetry_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_software_control_telemetry_records(self, scope_key: str | None = None) -> list[SoftwareControlTelemetryRecord]:
        return self._list_runtime_state_records("software_control_telemetry_record", SoftwareControlTelemetryRecord, scope_key=scope_key)

    def save_backend_descriptor(self, descriptor: BackendCapabilityDescriptor | QueueBackendDescriptor | CoordinationBackendDescriptor) -> None:
        scope = getattr(descriptor, "scope", "")
        if not scope and isinstance(descriptor, QueueBackendDescriptor):
            scope = "queue"
        if not scope and isinstance(descriptor, CoordinationBackendDescriptor):
            scope = "coordination"
        if isinstance(descriptor, QueueBackendDescriptor):
            normalized = BackendCapabilityDescriptor(
                version=descriptor.version,
                backend_name=descriptor.backend_name,
                backend_kind=descriptor.backend_kind,
                scope=scope,
                durability_guarantee=descriptor.durability_guarantee,
                lease_semantics="queue fenced leases",
                heartbeat_support=False,
                ordering_assumption="available_at then runtime priority policy",
                reconnect_behavior="recreate client and continue",
                operational_limit="single redis/sqlite backend instance per namespace",
                deployment_assumption="shared queue backend for dispatching",
            )
        elif isinstance(descriptor, CoordinationBackendDescriptor):
            normalized = BackendCapabilityDescriptor(
                version=descriptor.version,
                backend_name=descriptor.backend_name,
                backend_kind=descriptor.backend_kind,
                scope=scope,
                durability_guarantee=descriptor.durability_guarantee,
                lease_semantics=descriptor.lease_semantics,
                heartbeat_support=descriptor.supports_heartbeats,
                ordering_assumption="latest ownership record is authoritative",
                reconnect_behavior="re-register worker and heartbeat after reconnect",
                operational_limit="bounded by shared coordination backend latency",
                deployment_assumption="shared coordination backend across workers",
            )
        else:
            normalized = descriptor
        self._insert_or_replace(
            "backend_capability_descriptors",
            {
                "backend_name": normalized.backend_name,
                "backend_kind": normalized.backend_kind,
                "scope": scope,
                "record_version": normalized.version,
                "payload_json": self.dumps(normalized.to_dict()),
            },
        )

    def list_backend_descriptors(self) -> list[BackendCapabilityDescriptor]:
        rows = self._fetchall("SELECT * FROM backend_capability_descriptors ORDER BY backend_name ASC", ())
        return [self._model_from_row("backend_capability_descriptors", row, BackendCapabilityDescriptor) for row in rows]

    def save_backend_health_record(self, record: BackendHealthRecord) -> None:
        self._insert_or_replace(
            "backend_health_records",
            {
                "backend_name": record.backend_name,
                "backend_kind": record.backend_kind,
                "status": record.status,
                "updated_at": record.updated_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def list_backend_health_records(self) -> list[BackendHealthRecord]:
        rows = self._fetchall("SELECT * FROM backend_health_records ORDER BY updated_at DESC", ())
        return [self._model_from_row("backend_health_records", row, BackendHealthRecord) for row in rows]

    def save_backend_pressure_snapshot(self, snapshot: BackendPressureSnapshot) -> None:
        self._insert_or_replace(
            "backend_pressure_snapshots",
            {
                "snapshot_id": snapshot.snapshot_id,
                "backend_name": snapshot.backend_name,
                "created_at": snapshot.created_at.isoformat(),
                "record_version": snapshot.version,
                "payload_json": self.dumps(snapshot.to_dict()),
            },
        )

    def list_backend_pressure_snapshots(self, backend_name: str | None = None) -> list[BackendPressureSnapshot]:
        query = "SELECT * FROM backend_pressure_snapshots"
        params: tuple[Any, ...] = ()
        if backend_name is not None:
            query += " WHERE backend_name = ?"
            params = (backend_name,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("backend_pressure_snapshots", row, BackendPressureSnapshot) for row in rows]

    def save_tool_scorecard(self, scorecard: ToolScorecard) -> None:
        self._insert_or_replace(
            "tool_scorecards",
            {
                "tool_name": scorecard.tool_name,
                "variant": scorecard.variant,
                "updated_at": scorecard.last_updated.isoformat(),
                "record_version": scorecard.version,
                "payload_json": self.dumps(scorecard.to_dict()),
            },
        )

    def get_tool_scorecard(self, tool_name: str, variant: str) -> ToolScorecard | None:
        row = self._fetchone(
            "SELECT * FROM tool_scorecards WHERE tool_name = ? AND variant = ?",
            (tool_name, variant),
        )
        return None if row is None else self._model_from_row("tool_scorecards", row, ToolScorecard)

    def list_tool_scorecards(self) -> list[ToolScorecard]:
        rows = self._fetchall("SELECT * FROM tool_scorecards ORDER BY updated_at DESC", ())
        return [self._model_from_row("tool_scorecards", row, ToolScorecard) for row in rows]

    def save_queue_item(self, item: QueueItem) -> None:
        self._insert_or_replace(
            "queue_items",
            {
                "queue_item_id": item.queue_item_id,
                "task_id": item.task_id,
                "contract_id": item.contract_id,
                "queue_name": item.queue_name,
                "priority_class": item.priority_class,
                "status": item.status,
                "available_at": item.available_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
                "record_version": item.version,
                "payload_json": self.dumps(item.to_dict()),
            },
        )

    def get_queue_item(self, queue_item_id: str) -> QueueItem | None:
        row = self._fetchone("SELECT * FROM queue_items WHERE queue_item_id = ?", (queue_item_id,))
        return None if row is None else self._model_from_row("queue_items", row, QueueItem)

    def list_queue_items(self, statuses: list[str] | None = None) -> list[QueueItem]:
        query = "SELECT * FROM queue_items"
        params: tuple[Any, ...] = ()
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            query += f" WHERE status IN ({placeholders})"
            params = tuple(statuses)
        query += " ORDER BY updated_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("queue_items", row, QueueItem) for row in rows]

    def save_queue_lease(self, lease: QueueLease) -> None:
        self._insert_or_replace(
            "queue_leases",
            {
                "lease_id": lease.lease_id,
                "queue_item_id": lease.queue_item_id,
                "task_id": lease.task_id,
                "worker_id": lease.worker_id,
                "status": lease.status,
                "acquired_at": lease.acquired_at.isoformat(),
                "expires_at": lease.expires_at.isoformat(),
                "record_version": lease.version,
                "payload_json": self.dumps(lease.to_dict()),
            },
        )

    def get_queue_lease(self, lease_id: str) -> QueueLease | None:
        row = self._fetchone("SELECT * FROM queue_leases WHERE lease_id = ?", (lease_id,))
        return None if row is None else self._model_from_row("queue_leases", row, QueueLease)

    def list_queue_leases(self, status: str | None = None) -> list[QueueLease]:
        query = "SELECT * FROM queue_leases"
        params: tuple[Any, ...] = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY acquired_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("queue_leases", row, QueueLease) for row in rows]

    def save_admission_decision(self, decision: AdmissionDecision) -> None:
        self._insert_or_replace(
            "admission_decisions",
            {
                "decision_id": decision.decision_id,
                "queue_item_id": decision.queue_item_id,
                "task_id": decision.task_id,
                "status": decision.status,
                "active_mode": decision.active_mode,
                "created_at": decision.created_at.isoformat(),
                "record_version": decision.version,
                "payload_json": self.dumps(decision.to_dict()),
            },
        )

    def list_admission_decisions(self, task_id: str | None = None) -> list[AdmissionDecision]:
        query = "SELECT * FROM admission_decisions"
        params: tuple[Any, ...] = ()
        if task_id is not None:
            query += " WHERE task_id = ?"
            params = (task_id,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("admission_decisions", row, AdmissionDecision) for row in rows]

    def save_dispatch_record(self, record: DispatchRecord) -> None:
        self._insert_or_replace(
            "dispatch_records",
            {
                "dispatch_id": record.dispatch_id,
                "queue_item_id": record.queue_item_id,
                "task_id": record.task_id,
                "lease_id": record.lease_id,
                "worker_id": record.worker_id,
                "status": record.status,
                "created_at": record.created_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def latest_dispatch_record(self, task_id: str) -> DispatchRecord | None:
        row = self._fetchone(
            "SELECT * FROM dispatch_records WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
            (task_id,),
        )
        return None if row is None else self._model_from_row("dispatch_records", row, DispatchRecord)

    def list_dispatch_records(self, task_id: str | None = None) -> list[DispatchRecord]:
        query = "SELECT * FROM dispatch_records"
        params: tuple[Any, ...] = ()
        if task_id is not None:
            query += " WHERE task_id = ?"
            params = (task_id,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("dispatch_records", row, DispatchRecord) for row in rows]

    def save_queue_policy(self, policy: QueuePolicy) -> None:
        self._insert_or_replace(
            "queue_policies",
            {
                "policy_id": policy.policy_id,
                "queue_name": policy.queue_name,
                "created_at": policy.created_at.isoformat(),
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def load_queue_policy(self, queue_name: str) -> QueuePolicy | None:
        row = self._fetchone(
            "SELECT * FROM queue_policies WHERE queue_name = ? ORDER BY created_at DESC LIMIT 1",
            (queue_name,),
        )
        return None if row is None else self._model_from_row("queue_policies", row, QueuePolicy)

    def save_capacity_snapshot(self, snapshot: CapacitySnapshot) -> None:
        self._insert_or_replace(
            "capacity_snapshots",
            {
                "snapshot_id": snapshot.snapshot_id,
                "created_at": snapshot.created_at.isoformat(),
                "record_version": snapshot.version,
                "payload_json": self.dumps(snapshot.to_dict()),
            },
        )

    def latest_capacity_snapshot(self) -> CapacitySnapshot | None:
        row = self._fetchone("SELECT * FROM capacity_snapshots ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("capacity_snapshots", row, CapacitySnapshot)

    def save_load_shedding_event(self, event: LoadSheddingEvent) -> None:
        self._insert_or_replace(
            "load_shedding_events",
            {
                "event_id": event.event_id,
                "queue_item_id": event.queue_item_id,
                "task_id": event.task_id,
                "action": event.action,
                "created_at": event.created_at.isoformat(),
                "record_version": event.version,
                "payload_json": self.dumps(event.to_dict()),
            },
        )

    def list_load_shedding_events(self, task_id: str | None = None) -> list[LoadSheddingEvent]:
        query = "SELECT * FROM load_shedding_events"
        params: tuple[Any, ...] = ()
        if task_id is not None:
            query += " WHERE task_id = ?"
            params = (task_id,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("load_shedding_events", row, LoadSheddingEvent) for row in rows]

    def save_admission_policy(self, policy: AdmissionPolicy) -> None:
        self._insert_or_replace(
            "admission_policies",
            {
                "policy_id": policy.policy_id,
                "created_at": policy.created_at.isoformat(),
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def latest_admission_policy(self) -> AdmissionPolicy | None:
        row = self._fetchone("SELECT * FROM admission_policies ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("admission_policies", row, AdmissionPolicy)

    def save_queue_priority_policy(self, policy: QueuePriorityPolicy) -> None:
        self._insert_or_replace(
            "queue_priority_policies",
            {
                "policy_id": policy.policy_id,
                "created_at": policy.created_at.isoformat(),
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def latest_queue_priority_policy(self) -> QueuePriorityPolicy | None:
        row = self._fetchone("SELECT * FROM queue_priority_policies ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("queue_priority_policies", row, QueuePriorityPolicy)

    def save_capacity_policy(self, policy: CapacityPolicy) -> None:
        self._insert_or_replace(
            "capacity_policies",
            {
                "policy_id": policy.policy_id,
                "created_at": policy.created_at.isoformat(),
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def latest_capacity_policy(self) -> CapacityPolicy | None:
        row = self._fetchone("SELECT * FROM capacity_policies ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("capacity_policies", row, CapacityPolicy)

    def save_load_shedding_policy(self, policy: LoadSheddingPolicy) -> None:
        self._insert_or_replace(
            "load_shedding_policies",
            {
                "policy_id": policy.policy_id,
                "created_at": policy.created_at.isoformat(),
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def latest_load_shedding_policy(self) -> LoadSheddingPolicy | None:
        row = self._fetchone("SELECT * FROM load_shedding_policies ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("load_shedding_policies", row, LoadSheddingPolicy)

    def save_recovery_reservation_policy(self, policy: RecoveryReservationPolicy) -> None:
        self._insert_or_replace(
            "recovery_reservation_policies",
            {
                "policy_id": policy.policy_id,
                "created_at": policy.created_at.isoformat(),
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def latest_recovery_reservation_policy(self) -> RecoveryReservationPolicy | None:
        row = self._fetchone("SELECT * FROM recovery_reservation_policies ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("recovery_reservation_policies", row, RecoveryReservationPolicy)

    def save_global_execution_mode(self, mode: GlobalExecutionModeState) -> None:
        self._insert_or_replace(
            "global_execution_modes",
            {
                "mode_id": mode.mode_id,
                "mode_name": mode.mode_name,
                "updated_at": mode.updated_at.isoformat(),
                "record_version": mode.version,
                "payload_json": self.dumps(mode.to_dict()),
            },
        )

    def latest_global_execution_mode(self) -> GlobalExecutionModeState | None:
        row = self._fetchone("SELECT * FROM global_execution_modes ORDER BY updated_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("global_execution_modes", row, GlobalExecutionModeState)

    def save_operator_override(self, override: OperatorOverrideRecord) -> None:
        self._insert_or_replace(
            "operator_overrides",
            {
                "override_id": override.override_id,
                "action": override.action,
                "scope": override.scope,
                "status": override.status,
                "idempotency_key": override.idempotency_key,
                "created_at": override.created_at.isoformat(),
                "record_version": override.version,
                "payload_json": self.dumps(override.to_dict()),
            },
        )

    def find_operator_override(self, idempotency_key: str) -> OperatorOverrideRecord | None:
        if not idempotency_key:
            return None
        row = self._fetchone(
            "SELECT * FROM operator_overrides WHERE idempotency_key = ? ORDER BY created_at DESC LIMIT 1",
            (idempotency_key,),
        )
        return None if row is None else self._model_from_row("operator_overrides", row, OperatorOverrideRecord)

    def list_operator_overrides(self) -> list[OperatorOverrideRecord]:
        rows = self._fetchall("SELECT * FROM operator_overrides ORDER BY created_at ASC", ())
        return [self._model_from_row("operator_overrides", row, OperatorOverrideRecord) for row in rows]

    def save_provider_health_record(self, record: ProviderHealthRecord) -> None:
        self._insert_or_replace(
            "provider_health_records",
            {
                "provider_name": record.provider_name,
                "availability_state": record.availability_state,
                "updated_at": record.updated_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def load_provider_health_record(self, provider_name: str) -> ProviderHealthRecord | None:
        row = self._fetchone("SELECT * FROM provider_health_records WHERE provider_name = ?", (provider_name,))
        return None if row is None else self._model_from_row("provider_health_records", row, ProviderHealthRecord)

    def list_provider_health_records(self) -> list[ProviderHealthRecord]:
        rows = self._fetchall("SELECT * FROM provider_health_records ORDER BY updated_at DESC", ())
        return [self._model_from_row("provider_health_records", row, ProviderHealthRecord) for row in rows]

    def save_provider_health_snapshot(self, snapshot: ProviderHealthSnapshot) -> None:
        self._insert_or_replace(
            "provider_health_snapshots",
            {
                "snapshot_id": snapshot.snapshot_id,
                "created_at": snapshot.created_at.isoformat(),
                "record_version": snapshot.version,
                "payload_json": self.dumps(snapshot.to_dict()),
            },
        )

    def latest_provider_health_snapshot(self) -> ProviderHealthSnapshot | None:
        row = self._fetchone("SELECT * FROM provider_health_snapshots ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("provider_health_snapshots", row, ProviderHealthSnapshot)

    def save_rate_limit_state(self, state: RateLimitState) -> None:
        self._insert_or_replace(
            "rate_limit_states",
            {
                "provider_name": state.provider_name,
                "limited_until": None if state.limited_until is None else state.limited_until.isoformat(),
                "record_version": state.version,
                "payload_json": self.dumps(state.to_dict()),
            },
        )

    def load_rate_limit_state(self, provider_name: str) -> RateLimitState | None:
        row = self._fetchone("SELECT * FROM rate_limit_states WHERE provider_name = ?", (provider_name,))
        return None if row is None else self._model_from_row("rate_limit_states", row, RateLimitState)

    def save_provider_cooldown_window(self, window: ProviderCooldownWindow) -> None:
        self._insert_or_replace(
            "provider_cooldown_windows",
            {
                "provider_name": window.provider_name,
                "state": window.state,
                "cooldown_until": window.cooldown_until.isoformat(),
                "record_version": window.version,
                "payload_json": self.dumps(window.to_dict()),
            },
        )

    def load_provider_cooldown_window(self, provider_name: str) -> ProviderCooldownWindow | None:
        row = self._fetchone("SELECT * FROM provider_cooldown_windows WHERE provider_name = ?", (provider_name,))
        return None if row is None else self._model_from_row("provider_cooldown_windows", row, ProviderCooldownWindow)

    def save_provider_degradation_event(self, event: ProviderDegradationEvent) -> None:
        self._insert_or_replace(
            "provider_degradation_events",
            {
                "event_id": event.event_id,
                "provider_name": event.provider_name,
                "event_type": event.event_type,
                "created_at": event.created_at.isoformat(),
                "record_version": event.version,
                "payload_json": self.dumps(event.to_dict()),
            },
        )

    def list_provider_degradation_events(self, provider_name: str | None = None) -> list[ProviderDegradationEvent]:
        query = "SELECT * FROM provider_degradation_events"
        params: tuple[Any, ...] = ()
        if provider_name is not None:
            query += " WHERE provider_name = ?"
            params = (provider_name,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("provider_degradation_events", row, ProviderDegradationEvent) for row in rows]

    def save_provider_availability_policy(self, policy: ProviderAvailabilityPolicy) -> None:
        self._insert_or_replace(
            "provider_availability_policies",
            {
                "policy_id": policy.policy_id,
                "provider_name": policy.provider_name,
                "created_at": policy.created_at.isoformat(),
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def load_provider_availability_policy(self, provider_name: str) -> ProviderAvailabilityPolicy | None:
        row = self._fetchone(
            "SELECT * FROM provider_availability_policies WHERE provider_name = ? ORDER BY created_at DESC LIMIT 1",
            (provider_name,),
        )
        return None if row is None else self._model_from_row("provider_availability_policies", row, ProviderAvailabilityPolicy)

    def list_provider_availability_policies(self) -> list[ProviderAvailabilityPolicy]:
        rows = self._fetchall("SELECT * FROM provider_availability_policies ORDER BY created_at ASC", ())
        return [self._model_from_row("provider_availability_policies", row, ProviderAvailabilityPolicy) for row in rows]

    def save_policy_scope(self, scope: PolicyScope) -> None:
        self._insert_or_replace(
            "policy_scopes",
            {
                "scope_id": scope.scope_id,
                "scope_type": scope.scope_type,
                "target_component": scope.target_component,
                "created_at": scope.created_at.isoformat(),
                "record_version": scope.version,
                "payload_json": self.dumps(scope.to_dict()),
            },
        )

    def load_policy_scope(self, scope_id: str) -> PolicyScope:
        row = self._fetchone("SELECT * FROM policy_scopes WHERE scope_id = ?", (scope_id,))
        return self._model_from_row("policy_scopes", row, PolicyScope)

    def list_policy_scopes(self) -> list[PolicyScope]:
        rows = self._fetchall("SELECT * FROM policy_scopes ORDER BY created_at ASC", ())
        return [self._model_from_row("policy_scopes", row, PolicyScope) for row in rows]

    def save_policy_version(self, version: PolicyVersion) -> None:
        self._insert_or_replace(
            "policy_versions",
            {
                "version_id": version.version_id,
                "scope_id": version.scope_id,
                "status": version.status,
                "created_at": version.created_at.isoformat(),
                "record_version": version.version,
                "payload_json": self.dumps(version.to_dict()),
            },
        )

    def list_policy_versions(self, scope_id: str) -> list[PolicyVersion]:
        rows = self._fetchall(
            "SELECT * FROM policy_versions WHERE scope_id = ? ORDER BY created_at ASC",
            (scope_id,),
        )
        return [self._model_from_row("policy_versions", row, PolicyVersion) for row in rows]

    def save_policy_evidence_bundle(self, bundle: PolicyEvidenceBundle) -> None:
        self._insert_or_replace(
            "policy_evidence_bundles",
            {
                "bundle_id": bundle.bundle_id,
                "scope_id": bundle.scope_id,
                "created_at": bundle.created_at.isoformat(),
                "record_version": bundle.version,
                "payload_json": self.dumps(bundle.to_dict()),
            },
        )

    def load_policy_evidence_bundle(self, bundle_id: str) -> PolicyEvidenceBundle:
        row = self._fetchone("SELECT * FROM policy_evidence_bundles WHERE bundle_id = ?", (bundle_id,))
        return self._model_from_row("policy_evidence_bundles", row, PolicyEvidenceBundle)

    def save_policy_candidate(self, candidate: PolicyCandidate) -> None:
        self._insert_or_replace(
            "policy_candidates",
            {
                "candidate_id": candidate.candidate_id,
                "scope_id": candidate.scope_id,
                "base_version_id": candidate.base_version_id,
                "status": candidate.status,
                "created_at": candidate.created_at.isoformat(),
                "record_version": candidate.version,
                "payload_json": self.dumps(candidate.to_dict()),
            },
        )

    def load_policy_candidate(self, candidate_id: str) -> PolicyCandidate:
        row = self._fetchone("SELECT * FROM policy_candidates WHERE candidate_id = ?", (candidate_id,))
        return self._model_from_row("policy_candidates", row, PolicyCandidate)

    def list_policy_candidates(self, scope_id: str | None = None) -> list[PolicyCandidate]:
        query = "SELECT * FROM policy_candidates"
        params: tuple[Any, ...] = ()
        if scope_id is not None:
            query += " WHERE scope_id = ?"
            params = (scope_id,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("policy_candidates", row, PolicyCandidate) for row in rows]

    def save_policy_promotion_run(self, run: PolicyPromotionRun) -> None:
        self._insert_or_replace(
            "policy_promotion_runs",
            {
                "run_id": run.run_id,
                "candidate_id": run.candidate_id,
                "status": run.status,
                "created_at": run.created_at.isoformat(),
                "record_version": run.version,
                "payload_json": self.dumps(run.to_dict()),
            },
        )

    def latest_policy_promotion_run(self, candidate_id: str) -> PolicyPromotionRun | None:
        row = self._fetchone(
            "SELECT * FROM policy_promotion_runs WHERE candidate_id = ? ORDER BY created_at DESC LIMIT 1",
            (candidate_id,),
        )
        return None if row is None else self._model_from_row("policy_promotion_runs", row, PolicyPromotionRun)

    def list_policy_promotion_runs(self, candidate_id: str | None = None) -> list[PolicyPromotionRun]:
        query = "SELECT * FROM policy_promotion_runs"
        params: tuple[Any, ...] = ()
        if candidate_id is not None:
            query += " WHERE candidate_id = ?"
            params = (candidate_id,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("policy_promotion_runs", row, PolicyPromotionRun) for row in rows]

    def save_policy_rollback_record(self, record: PolicyRollbackRecord) -> None:
        self._insert_or_replace(
            "policy_rollback_records",
            {
                "rollback_id": record.rollback_id,
                "scope_id": record.scope_id,
                "created_at": record.created_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def list_policy_rollback_records(self, scope_id: str | None = None) -> list[PolicyRollbackRecord]:
        query = "SELECT * FROM policy_rollback_records"
        params: tuple[Any, ...] = ()
        if scope_id is not None:
            query += " WHERE scope_id = ?"
            params = (scope_id,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("policy_rollback_records", row, PolicyRollbackRecord) for row in rows]

    def save_worker(self, worker: WorkerLifecycleRecord) -> None:
        self._insert_or_replace(
            "workers",
            {
                "worker_id": worker.worker_id,
                "worker_role": worker.worker_role,
                "process_identity": worker.process_identity,
                "heartbeat_state": worker.heartbeat_state,
                "shutdown_state": worker.shutdown_state,
                "updated_at": worker.updated_at.isoformat(),
                "record_version": worker.version,
                "payload_json": self.dumps(worker.to_dict()),
            },
        )

    def load_worker(self, worker_id: str) -> WorkerLifecycleRecord | None:
        row = self._fetchone("SELECT * FROM workers WHERE worker_id = ?", (worker_id,))
        return None if row is None else self._model_from_row("workers", row, WorkerLifecycleRecord)

    def list_workers(self, states: list[str] | None = None) -> list[WorkerLifecycleRecord]:
        query = "SELECT * FROM workers"
        params: tuple[Any, ...] = ()
        if states:
            placeholders = ", ".join("?" for _ in states)
            query += f" WHERE heartbeat_state IN ({placeholders}) OR shutdown_state IN ({placeholders})"
            params = tuple(states + states)
        query += " ORDER BY updated_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("workers", row, WorkerLifecycleRecord) for row in rows]

    def save_worker_capability(self, record: WorkerCapabilityRecord) -> None:
        self._insert_or_replace(
            "worker_capabilities",
            {
                "worker_id": record.worker_id,
                "created_at": record.created_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def load_worker_capability(self, worker_id: str) -> WorkerCapabilityRecord | None:
        row = self._fetchone("SELECT * FROM worker_capabilities WHERE worker_id = ?", (worker_id,))
        return None if row is None else self._model_from_row("worker_capabilities", row, WorkerCapabilityRecord)

    def list_worker_capabilities(self) -> list[WorkerCapabilityRecord]:
        rows = self._fetchall("SELECT * FROM worker_capabilities ORDER BY created_at ASC", ())
        return [self._model_from_row("worker_capabilities", row, WorkerCapabilityRecord) for row in rows]

    def save_worker_heartbeat(self, heartbeat: WorkerHeartbeatRecord) -> None:
        self._insert_or_replace(
            "worker_heartbeats",
            {
                "heartbeat_id": heartbeat.heartbeat_id,
                "worker_id": heartbeat.worker_id,
                "created_at": heartbeat.created_at.isoformat(),
                "expires_at": heartbeat.expires_at.isoformat(),
                "record_version": heartbeat.version,
                "payload_json": self.dumps(heartbeat.to_dict()),
            },
        )

    def latest_worker_heartbeat(self, worker_id: str) -> WorkerHeartbeatRecord | None:
        row = self._fetchone(
            "SELECT * FROM worker_heartbeats WHERE worker_id = ? ORDER BY created_at DESC LIMIT 1",
            (worker_id,),
        )
        return None if row is None else self._model_from_row("worker_heartbeats", row, WorkerHeartbeatRecord)

    def save_worker_pressure_snapshot(self, snapshot: WorkerPressureSnapshot) -> None:
        self._insert_or_replace(
            "worker_pressure_snapshots",
            {
                "snapshot_id": snapshot.snapshot_id,
                "created_at": snapshot.created_at.isoformat(),
                "record_version": snapshot.version,
                "payload_json": self.dumps(snapshot.to_dict()),
            },
        )

    def latest_worker_pressure_snapshot(self) -> WorkerPressureSnapshot | None:
        row = self._fetchone("SELECT * FROM worker_pressure_snapshots ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("worker_pressure_snapshots", row, WorkerPressureSnapshot)

    def save_host_record(self, record: HostRecord) -> None:
        self._insert_or_replace(
            "host_records",
            {
                "host_id": record.host_id,
                "status": record.status,
                "drain_state": record.drain_state,
                "last_seen_at": record.last_seen_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def load_host_record(self, host_id: str) -> HostRecord | None:
        row = self._fetchone("SELECT * FROM host_records WHERE host_id = ?", (host_id,))
        return None if row is None else self._model_from_row("host_records", row, HostRecord)

    def list_host_records(self) -> list[HostRecord]:
        rows = self._fetchall("SELECT * FROM host_records ORDER BY last_seen_at ASC", ())
        return [self._model_from_row("host_records", row, HostRecord) for row in rows]

    def save_worker_host_binding(self, record: WorkerHostBinding) -> None:
        self._insert_or_replace(
            "worker_host_bindings",
            {
                "binding_id": record.binding_id,
                "worker_id": record.worker_id,
                "host_id": record.host_id,
                "status": record.status,
                "bound_at": record.bound_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def list_worker_host_bindings(self, worker_id: str | None = None) -> list[WorkerHostBinding]:
        query = "SELECT * FROM worker_host_bindings"
        params: tuple[Any, ...] = ()
        if worker_id is not None:
            query += " WHERE worker_id = ?"
            params = (worker_id,)
        query += " ORDER BY bound_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("worker_host_bindings", row, WorkerHostBinding) for row in rows]

    def save_worker_endpoint(self, record: WorkerEndpointRecord) -> None:
        self._insert_or_replace(
            "worker_endpoint_records",
            {
                "endpoint_id": record.endpoint_id,
                "worker_id": record.worker_id,
                "host_id": record.host_id,
                "last_seen_at": record.last_seen_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def load_worker_endpoint(self, worker_id: str) -> WorkerEndpointRecord | None:
        row = self._fetchone(
            "SELECT * FROM worker_endpoint_records WHERE worker_id = ? ORDER BY last_seen_at DESC LIMIT 1",
            (worker_id,),
        )
        return None if row is None else self._model_from_row("worker_endpoint_records", row, WorkerEndpointRecord)

    def list_worker_endpoints(self, host_id: str | None = None) -> list[WorkerEndpointRecord]:
        query = "SELECT * FROM worker_endpoint_records"
        params: tuple[Any, ...] = ()
        if host_id is not None:
            query += " WHERE host_id = ?"
            params = (host_id,)
        query += " ORDER BY last_seen_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("worker_endpoint_records", row, WorkerEndpointRecord) for row in rows]

    def save_lease_renewal_policy(self, policy: LeaseRenewalPolicy) -> None:
        self._insert_or_replace(
            "lease_renewal_policies",
            {
                "policy_id": policy.policy_id,
                "created_at": policy.created_at.isoformat(),
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def latest_lease_renewal_policy(self) -> LeaseRenewalPolicy | None:
        row = self._fetchone("SELECT * FROM lease_renewal_policies ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("lease_renewal_policies", row, LeaseRenewalPolicy)

    def save_renewal_attempt(self, record: RenewalAttemptRecord) -> None:
        self._insert_or_replace(
            "renewal_attempt_records",
            {
                "attempt_id": record.attempt_id,
                "lease_id": record.lease_id,
                "worker_id": record.worker_id,
                "host_id": record.host_id,
                "outcome": record.outcome,
                "created_at": record.created_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def list_renewal_attempts(self, lease_id: str | None = None) -> list[RenewalAttemptRecord]:
        query = "SELECT * FROM renewal_attempt_records"
        params: tuple[Any, ...] = ()
        if lease_id is not None:
            query += " WHERE lease_id = ?"
            params = (lease_id,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("renewal_attempt_records", row, RenewalAttemptRecord) for row in rows]

    def save_lease_expiry_forecast(self, forecast: LeaseExpiryForecast) -> None:
        self._insert_or_replace(
            "lease_expiry_forecasts",
            {
                "forecast_id": forecast.forecast_id,
                "lease_id": forecast.lease_id,
                "created_at": forecast.created_at.isoformat(),
                "record_version": forecast.version,
                "payload_json": self.dumps(forecast.to_dict()),
            },
        )

    def latest_lease_expiry_forecast(self, lease_id: str) -> LeaseExpiryForecast | None:
        row = self._fetchone(
            "SELECT * FROM lease_expiry_forecasts WHERE lease_id = ? ORDER BY created_at DESC LIMIT 1",
            (lease_id,),
        )
        return None if row is None else self._model_from_row("lease_expiry_forecasts", row, LeaseExpiryForecast)

    def save_lease_contention_record(self, record: LeaseContentionRecord) -> None:
        self._insert_or_replace(
            "lease_contention_records",
            {
                "contention_id": record.contention_id,
                "lease_id": record.lease_id,
                "created_at": record.created_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def list_lease_contention_records(self, lease_id: str | None = None) -> list[LeaseContentionRecord]:
        query = "SELECT * FROM lease_contention_records"
        params: tuple[Any, ...] = ()
        if lease_id is not None:
            query += " WHERE lease_id = ?"
            params = (lease_id,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("lease_contention_records", row, LeaseContentionRecord) for row in rows]

    def save_work_steal_policy(self, policy: WorkStealPolicy) -> None:
        self._insert_or_replace(
            "work_steal_policies",
            {
                "policy_id": policy.policy_id,
                "created_at": policy.created_at.isoformat(),
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def latest_work_steal_policy(self) -> WorkStealPolicy | None:
        row = self._fetchone("SELECT * FROM work_steal_policies ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("work_steal_policies", row, WorkStealPolicy)

    def save_work_steal_decision(self, decision: WorkStealDecision) -> None:
        self._insert_or_replace(
            "work_steal_decisions",
            {
                "decision_id": decision.decision_id,
                "lease_id": decision.lease_id,
                "from_worker_id": decision.from_worker_id,
                "to_worker_id": decision.to_worker_id,
                "status": decision.status,
                "created_at": decision.created_at.isoformat(),
                "record_version": decision.version,
                "payload_json": self.dumps(decision.to_dict()),
            },
        )

    def list_work_steal_decisions(self, lease_id: str | None = None) -> list[WorkStealDecision]:
        query = "SELECT * FROM work_steal_decisions"
        params: tuple[Any, ...] = ()
        if lease_id is not None:
            query += " WHERE lease_id = ?"
            params = (lease_id,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("work_steal_decisions", row, WorkStealDecision) for row in rows]

    def save_lease_transfer_record(self, record: LeaseTransferRecord) -> None:
        self._insert_or_replace(
            "lease_transfer_records",
            {
                "transfer_id": record.transfer_id,
                "lease_id": record.lease_id,
                "from_worker_id": record.from_worker_id,
                "to_worker_id": record.to_worker_id,
                "created_at": record.created_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def list_lease_transfer_records(self, lease_id: str | None = None) -> list[LeaseTransferRecord]:
        query = "SELECT * FROM lease_transfer_records"
        params: tuple[Any, ...] = ()
        if lease_id is not None:
            query += " WHERE lease_id = ?"
            params = (lease_id,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("lease_transfer_records", row, LeaseTransferRecord) for row in rows]

    def save_ownership_conflict_event(self, event: OwnershipConflictEvent) -> None:
        self._insert_or_replace(
            "ownership_conflict_events",
            {
                "event_id": event.event_id,
                "lease_id": event.lease_id,
                "stale_worker_id": event.stale_worker_id,
                "active_worker_id": event.active_worker_id,
                "created_at": event.created_at.isoformat(),
                "record_version": event.version,
                "payload_json": self.dumps(event.to_dict()),
            },
        )

    def list_ownership_conflict_events(self, lease_id: str | None = None) -> list[OwnershipConflictEvent]:
        query = "SELECT * FROM ownership_conflict_events"
        params: tuple[Any, ...] = ()
        if lease_id is not None:
            query += " WHERE lease_id = ?"
            params = (lease_id,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("ownership_conflict_events", row, OwnershipConflictEvent) for row in rows]

    def save_lease_ownership(self, record: LeaseOwnershipRecord) -> None:
        self._insert_or_replace(
            "lease_ownerships",
            {
                "ownership_id": record.ownership_id,
                "lease_id": record.lease_id,
                "worker_id": record.worker_id,
                "lease_epoch": record.lease_epoch,
                "status": record.status,
                "expires_at": record.expires_at.isoformat(),
                "acquired_at": record.acquired_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def latest_lease_ownership(self, lease_id: str) -> LeaseOwnershipRecord | None:
        row = self._fetchone(
            "SELECT * FROM lease_ownerships WHERE lease_id = ? ORDER BY lease_epoch DESC, acquired_at DESC LIMIT 1",
            (lease_id,),
        )
        return None if row is None else self._model_from_row("lease_ownerships", row, LeaseOwnershipRecord)

    def list_lease_ownerships(
        self,
        lease_id: str | None = None,
        worker_id: str | None = None,
        statuses: list[str] | None = None,
    ) -> list[LeaseOwnershipRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if lease_id is not None:
            clauses.append("lease_id = ?")
            params.append(lease_id)
        if worker_id is not None:
            clauses.append("worker_id = ?")
            params.append(worker_id)
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            clauses.append(f"status IN ({placeholders})")
            params.extend(statuses)
        query = "SELECT * FROM lease_ownerships"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY acquired_at ASC"
        rows = self._fetchall(query, tuple(params))
        return [self._model_from_row("lease_ownerships", row, LeaseOwnershipRecord) for row in rows]

    def save_dispatch_ownership(self, record: DispatchOwnershipRecord) -> None:
        self._insert_or_replace(
            "dispatch_ownerships",
            {
                "ownership_id": record.ownership_id,
                "dispatch_id": record.dispatch_id,
                "worker_id": record.worker_id,
                "status": record.status,
                "updated_at": record.updated_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def latest_dispatch_ownership(self, dispatch_id: str) -> DispatchOwnershipRecord | None:
        row = self._fetchone(
            "SELECT * FROM dispatch_ownerships WHERE dispatch_id = ? ORDER BY updated_at DESC LIMIT 1",
            (dispatch_id,),
        )
        return None if row is None else self._model_from_row("dispatch_ownerships", row, DispatchOwnershipRecord)

    def list_dispatch_ownerships(self, worker_id: str | None = None) -> list[DispatchOwnershipRecord]:
        query = "SELECT * FROM dispatch_ownerships"
        params: tuple[Any, ...] = ()
        if worker_id is not None:
            query += " WHERE worker_id = ?"
            params = (worker_id,)
        query += " ORDER BY updated_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("dispatch_ownerships", row, DispatchOwnershipRecord) for row in rows]

    def save_provider_capacity_record(self, record: ProviderCapacityRecord) -> None:
        self._insert_or_replace(
            "provider_capacity_records",
            {
                "provider_name": record.provider_name,
                "updated_at": record.updated_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def load_provider_capacity_record(self, provider_name: str) -> ProviderCapacityRecord | None:
        row = self._fetchone("SELECT * FROM provider_capacity_records WHERE provider_name = ?", (provider_name,))
        return None if row is None else self._model_from_row("provider_capacity_records", row, ProviderCapacityRecord)

    def list_provider_capacity_records(self) -> list[ProviderCapacityRecord]:
        rows = self._fetchall("SELECT * FROM provider_capacity_records ORDER BY updated_at ASC", ())
        return [self._model_from_row("provider_capacity_records", row, ProviderCapacityRecord) for row in rows]

    def save_provider_pool_state(self, state: ProviderPoolState) -> None:
        self._insert_or_replace(
            "provider_pool_states",
            {
                "pool_id": state.pool_id,
                "created_at": state.created_at.isoformat(),
                "record_version": state.version,
                "payload_json": self.dumps(state.to_dict()),
            },
        )

    def latest_provider_pool_state(self) -> ProviderPoolState | None:
        row = self._fetchone("SELECT * FROM provider_pool_states ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("provider_pool_states", row, ProviderPoolState)

    def save_provider_pressure_snapshot(self, snapshot: ProviderPressureSnapshot) -> None:
        self._insert_or_replace(
            "provider_pressure_snapshots",
            {
                "snapshot_id": snapshot.snapshot_id,
                "created_at": snapshot.created_at.isoformat(),
                "record_version": snapshot.version,
                "payload_json": self.dumps(snapshot.to_dict()),
            },
        )

    def latest_provider_pressure_snapshot(self) -> ProviderPressureSnapshot | None:
        row = self._fetchone("SELECT * FROM provider_pressure_snapshots ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("provider_pressure_snapshots", row, ProviderPressureSnapshot)

    def save_provider_reservation(self, reservation: ProviderReservation) -> None:
        self._insert_or_replace(
            "provider_reservations",
            {
                "reservation_id": reservation.reservation_id,
                "provider_name": reservation.provider_name,
                "reservation_type": reservation.reservation_type,
                "task_id": reservation.task_id,
                "worker_id": reservation.worker_id,
                "status": reservation.status,
                "created_at": reservation.created_at.isoformat(),
                "expires_at": reservation.expires_at.isoformat(),
                "record_version": reservation.version,
                "payload_json": self.dumps(reservation.to_dict()),
            },
        )

    def load_provider_reservation(self, reservation_id: str) -> ProviderReservation | None:
        row = self._fetchone("SELECT * FROM provider_reservations WHERE reservation_id = ?", (reservation_id,))
        return None if row is None else self._model_from_row("provider_reservations", row, ProviderReservation)

    def list_provider_reservations(self, provider_name: str | None = None) -> list[ProviderReservation]:
        query = "SELECT * FROM provider_reservations"
        params: tuple[Any, ...] = ()
        if provider_name is not None:
            query += " WHERE provider_name = ?"
            params = (provider_name,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("provider_reservations", row, ProviderReservation) for row in rows]

    def save_provider_balance_decision(self, decision: ProviderBalanceDecision) -> None:
        self._insert_or_replace(
            "provider_balance_decisions",
            {
                "decision_id": decision.decision_id,
                "task_id": decision.task_id,
                "worker_id": decision.worker_id,
                "workload": decision.workload,
                "created_at": decision.created_at.isoformat(),
                "record_version": decision.version,
                "payload_json": self.dumps(decision.to_dict()),
            },
        )

    def list_provider_balance_decisions(self, task_id: str | None = None) -> list[ProviderBalanceDecision]:
        query = "SELECT * FROM provider_balance_decisions"
        params: tuple[Any, ...] = ()
        if task_id is not None:
            query += " WHERE task_id = ?"
            params = (task_id,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("provider_balance_decisions", row, ProviderBalanceDecision) for row in rows]

    def save_provider_pool_event(self, event: ProviderPoolEvent) -> None:
        self._insert_or_replace(
            "provider_pool_events",
            {
                "event_id": event.event_id,
                "provider_name": event.provider_name,
                "event_type": event.event_type,
                "created_at": event.created_at.isoformat(),
                "record_version": event.version,
                "payload_json": self.dumps(event.to_dict()),
            },
        )

    def list_provider_pool_events(self, provider_name: str | None = None) -> list[ProviderPoolEvent]:
        query = "SELECT * FROM provider_pool_events"
        params: tuple[Any, ...] = ()
        if provider_name is not None:
            query += " WHERE provider_name = ?"
            params = (provider_name,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("provider_pool_events", row, ProviderPoolEvent) for row in rows]

    def save_provider_fairness_record(self, record: ProviderFairnessRecord) -> None:
        self._insert_or_replace(
            "provider_fairness_records",
            {
                "record_id": record.record_id,
                "provider_name": record.provider_name,
                "created_at": record.created_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def list_provider_fairness_records(self, provider_name: str | None = None) -> list[ProviderFairnessRecord]:
        query = "SELECT * FROM provider_fairness_records"
        params: tuple[Any, ...] = ()
        if provider_name is not None:
            query += " WHERE provider_name = ?"
            params = (provider_name,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("provider_fairness_records", row, ProviderFairnessRecord) for row in rows]

    def save_provider_pool_balance_policy(self, policy: ProviderPoolBalancePolicy) -> None:
        self._insert_or_replace(
            "provider_pool_balance_policies",
            {
                "policy_id": policy.policy_id,
                "created_at": policy.created_at.isoformat(),
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def latest_provider_pool_balance_policy(self) -> ProviderPoolBalancePolicy | None:
        row = self._fetchone("SELECT * FROM provider_pool_balance_policies ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("provider_pool_balance_policies", row, ProviderPoolBalancePolicy)

    def save_reservation_policy(self, policy: ReservationPolicy) -> None:
        self._insert_or_replace(
            "reservation_policies",
            {
                "policy_id": policy.policy_id,
                "created_at": policy.created_at.isoformat(),
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def latest_reservation_policy(self) -> ReservationPolicy | None:
        row = self._fetchone("SELECT * FROM reservation_policies ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("reservation_policies", row, ReservationPolicy)

    def save_provider_fairness_policy(self, policy: ProviderFairnessPolicy) -> None:
        self._insert_or_replace(
            "fairness_policies",
            {
                "policy_id": policy.policy_id,
                "created_at": policy.created_at.isoformat(),
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def latest_provider_fairness_policy(self) -> ProviderFairnessPolicy | None:
        row = self._fetchone("SELECT * FROM fairness_policies ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("fairness_policies", row, ProviderFairnessPolicy)

    def save_sustained_pressure_policy(self, policy: SustainedPressurePolicy) -> None:
        self._insert_or_replace(
            "sustained_pressure_policies",
            {
                "policy_id": policy.policy_id,
                "created_at": policy.created_at.isoformat(),
                "record_version": policy.version,
                "payload_json": self.dumps(policy.to_dict()),
            },
        )

    def latest_sustained_pressure_policy(self) -> SustainedPressurePolicy | None:
        row = self._fetchone("SELECT * FROM sustained_pressure_policies ORDER BY created_at DESC LIMIT 1", ())
        return None if row is None else self._model_from_row("sustained_pressure_policies", row, SustainedPressurePolicy)

    def save_auth_scope(self, scope: AuthScope) -> None:
        self._insert_or_replace(
            "auth_scopes",
            {
                "scope_name": scope.scope_name,
                "record_version": scope.version,
                "payload_json": self.dumps(scope.to_dict()),
            },
        )

    def list_auth_scopes(self) -> list[AuthScope]:
        rows = self._fetchall("SELECT * FROM auth_scopes ORDER BY scope_name ASC", ())
        return [self._model_from_row("auth_scopes", row, AuthScope) for row in rows]

    def save_auth_principal(self, principal: AuthPrincipal) -> None:
        self._insert_or_replace(
            "auth_principals",
            {
                "principal_id": principal.principal_id,
                "principal_name": principal.principal_name,
                "principal_type": principal.principal_type,
                "status": principal.status,
                "created_at": principal.created_at.isoformat(),
                "record_version": principal.version,
                "payload_json": self.dumps(principal.to_dict()),
            },
        )

    def load_auth_principal(self, principal_id: str) -> AuthPrincipal | None:
        row = self._fetchone("SELECT * FROM auth_principals WHERE principal_id = ?", (principal_id,))
        return None if row is None else self._model_from_row("auth_principals", row, AuthPrincipal)

    def save_auth_credential(self, credential: AuthCredential) -> None:
        self._insert_or_replace(
            "auth_credentials",
            {
                "credential_id": credential.credential_id,
                "principal_id": credential.principal_id,
                "token_hash": credential.token_hash,
                "status": credential.status,
                "issued_at": credential.issued_at.isoformat(),
                "expires_at": None if credential.expires_at is None else credential.expires_at.isoformat(),
                "record_version": credential.version,
                "payload_json": self.dumps(credential.to_dict()),
            },
        )

    def load_auth_credential(self, credential_id: str) -> AuthCredential | None:
        row = self._fetchone("SELECT * FROM auth_credentials WHERE credential_id = ?", (credential_id,))
        return None if row is None else self._model_from_row("auth_credentials", row, AuthCredential)

    def load_auth_credential_by_hash(self, token_hash: str) -> AuthCredential | None:
        row = self._fetchone("SELECT * FROM auth_credentials WHERE token_hash = ?", (token_hash,))
        return None if row is None else self._model_from_row("auth_credentials", row, AuthCredential)

    def save_auth_session(self, session: AuthSession) -> None:
        self._insert_or_replace(
            "auth_sessions",
            {
                "session_id": session.session_id,
                "principal_id": session.principal_id,
                "credential_id": session.credential_id,
                "request_id": session.request_id,
                "authenticated_at": session.authenticated_at.isoformat(),
                "record_version": session.version,
                "payload_json": self.dumps(session.to_dict()),
            },
        )

    def save_auth_event(self, event: AuthEvent) -> None:
        self._insert_or_replace(
            "auth_events",
            {
                "event_id": event.event_id,
                "principal_id": event.principal_id,
                "credential_id": event.credential_id,
                "request_id": event.request_id,
                "action": event.action,
                "status": event.status,
                "created_at": event.created_at.isoformat(),
                "record_version": event.version,
                "payload_json": self.dumps(event.to_dict()),
            },
        )

    def list_auth_events(self, request_id: str | None = None) -> list[AuthEvent]:
        query = "SELECT * FROM auth_events"
        params: tuple[Any, ...] = ()
        if request_id is not None:
            query += " WHERE request_id = ?"
            params = (request_id,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("auth_events", row, AuthEvent) for row in rows]

    def save_service_principal(self, principal: ServicePrincipal) -> None:
        self._insert_or_replace(
            "service_principals",
            {
                "principal_id": principal.principal_id,
                "service_role": principal.service_role,
                "status": principal.status,
                "created_at": principal.created_at.isoformat(),
                "record_version": principal.version,
                "payload_json": self.dumps(principal.to_dict()),
            },
        )

    def load_service_principal(self, principal_id: str) -> ServicePrincipal | None:
        row = self._fetchone("SELECT * FROM service_principals WHERE principal_id = ?", (principal_id,))
        return None if row is None else self._model_from_row("service_principals", row, ServicePrincipal)

    def list_service_principals(self) -> list[ServicePrincipal]:
        rows = self._fetchall("SELECT * FROM service_principals ORDER BY created_at ASC", ())
        return [self._model_from_row("service_principals", row, ServicePrincipal) for row in rows]

    def save_service_credential(self, credential: ServiceCredential) -> None:
        self._insert_or_replace(
            "service_credentials",
            {
                "credential_id": credential.credential_id,
                "principal_id": credential.principal_id,
                "status": credential.status,
                "issued_at": credential.issued_at.isoformat(),
                "expires_at": None if credential.expires_at is None else credential.expires_at.isoformat(),
                "record_version": credential.version,
                "payload_json": self.dumps(credential.to_dict()),
            },
        )

    def load_service_credential(self, credential_id: str) -> ServiceCredential | None:
        row = self._fetchone("SELECT * FROM service_credentials WHERE credential_id = ?", (credential_id,))
        return None if row is None else self._model_from_row("service_credentials", row, ServiceCredential)

    def list_service_credentials(self, principal_id: str | None = None) -> list[ServiceCredential]:
        query = "SELECT * FROM service_credentials"
        params: tuple[Any, ...] = ()
        if principal_id is not None:
            query += " WHERE principal_id = ?"
            params = (principal_id,)
        query += " ORDER BY issued_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("service_credentials", row, ServiceCredential) for row in rows]

    def save_service_trust_record(self, record: ServiceTrustRecord) -> None:
        self._insert_or_replace(
            "service_trust_records",
            {
                "trust_id": record.trust_id,
                "principal_id": record.principal_id,
                "created_at": record.created_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def load_service_trust_record(self, principal_id: str) -> ServiceTrustRecord | None:
        row = self._fetchone(
            "SELECT * FROM service_trust_records WHERE principal_id = ? ORDER BY created_at DESC LIMIT 1",
            (principal_id,),
        )
        return None if row is None else self._model_from_row("service_trust_records", row, ServiceTrustRecord)

    def save_credential_rotation_record(self, record: CredentialRotationRecord) -> None:
        self._insert_or_replace(
            "credential_rotation_records",
            {
                "rotation_id": record.rotation_id,
                "old_credential_id": record.old_credential_id,
                "new_credential_id": record.new_credential_id,
                "rotated_at": record.rotated_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def list_credential_rotation_records(self, credential_id: str | None = None) -> list[CredentialRotationRecord]:
        query = "SELECT * FROM credential_rotation_records"
        params: tuple[Any, ...] = ()
        if credential_id is not None:
            query += " WHERE old_credential_id = ? OR new_credential_id = ?"
            params = (credential_id, credential_id)
        query += " ORDER BY rotated_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("credential_rotation_records", row, CredentialRotationRecord) for row in rows]

    def save_auth_failure_event(self, event: AuthFailureEvent) -> None:
        self._insert_or_replace(
            "auth_failure_events",
            {
                "event_id": event.event_id,
                "principal_id": event.principal_id,
                "action": event.action,
                "created_at": event.created_at.isoformat(),
                "record_version": event.version,
                "payload_json": self.dumps(event.to_dict()),
            },
        )

    def list_auth_failure_events(self, action: str | None = None) -> list[AuthFailureEvent]:
        query = "SELECT * FROM auth_failure_events"
        params: tuple[Any, ...] = ()
        if action is not None:
            query += " WHERE action = ?"
            params = (action,)
        query += " ORDER BY created_at ASC"
        rows = self._fetchall(query, params)
        return [self._model_from_row("auth_failure_events", row, AuthFailureEvent) for row in rows]

    def save_revoked_credential(self, record: RevokedCredentialRecord) -> None:
        self._insert_or_replace(
            "revoked_credentials",
            {
                "revocation_id": record.revocation_id,
                "credential_id": record.credential_id,
                "revoked_at": record.revoked_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def load_revoked_credential(self, credential_id: str) -> RevokedCredentialRecord | None:
        row = self._fetchone(
            "SELECT * FROM revoked_credentials WHERE credential_id = ? ORDER BY revoked_at DESC LIMIT 1",
            (credential_id,),
        )
        return None if row is None else self._model_from_row("revoked_credentials", row, RevokedCredentialRecord)

    def save_control_plane_request(self, record: ControlPlaneRequestRecord) -> None:
        self._insert_or_replace(
            "control_plane_requests",
            {
                "request_id": record.request_id,
                "principal_id": record.principal_id,
                "action": record.action,
                "nonce": record.nonce,
                "idempotency_key": record.idempotency_key,
                "sensitive": int(record.sensitive),
                "accepted": int(record.accepted),
                "created_at": record.created_at.isoformat(),
                "record_version": record.version,
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def save_shared_state_backend_descriptor(self, descriptor: SharedStateBackendDescriptor) -> None:
        self._save_runtime_state_record("shared_state_backend_descriptor", descriptor.backend_name, descriptor.backend_kind, descriptor.created_at.isoformat(), descriptor)

    def list_shared_state_backend_descriptors(self) -> list[SharedStateBackendDescriptor]:
        return self._list_runtime_state_records("shared_state_backend_descriptor", SharedStateBackendDescriptor)

    def save_fault_domain(self, record: FaultDomain) -> None:
        self._save_runtime_state_record("fault_domain", record.fault_domain_id, record.domain_type, record.created_at.isoformat(), record)

    def list_fault_domains(self) -> list[FaultDomain]:
        return self._list_runtime_state_records("fault_domain", FaultDomain)

    def save_fault_domain_event(self, record: FaultDomainEvent) -> None:
        self._save_runtime_state_record("fault_domain_event", record.event_id, record.fault_domain_id, record.created_at.isoformat(), record)

    def list_fault_domain_events(self, fault_domain_id: str | None = None) -> list[FaultDomainEvent]:
        return self._list_runtime_state_records("fault_domain_event", FaultDomainEvent, scope_key=fault_domain_id)

    def save_reliability_incident(self, record: ReliabilityIncident) -> None:
        self._save_runtime_state_record("reliability_incident", record.incident_id, record.task_id, record.created_at.isoformat(), record)

    def list_reliability_incidents(self, task_id: str | None = None) -> list[ReliabilityIncident]:
        return self._list_runtime_state_records("reliability_incident", ReliabilityIncident, scope_key=task_id)

    def save_reliability_recovery_plan(self, record: ReliabilityRecoveryPlan) -> None:
        self._save_runtime_state_record("reliability_recovery_plan", record.plan_id, record.incident_id, record.created_at.isoformat(), record)

    def list_reliability_recovery_plans(self, incident_id: str | None = None) -> list[ReliabilityRecoveryPlan]:
        return self._list_runtime_state_records("reliability_recovery_plan", ReliabilityRecoveryPlan, scope_key=incident_id)

    def save_conflict_resolution_record(self, record: ConflictResolutionRecord) -> None:
        self._save_runtime_state_record("conflict_resolution_record", record.resolution_id, record.lease_id, record.created_at.isoformat(), record)

    def list_conflict_resolution_records(self, lease_id: str | None = None) -> list[ConflictResolutionRecord]:
        return self._list_runtime_state_records("conflict_resolution_record", ConflictResolutionRecord, scope_key=lease_id)

    def save_runtime_degradation_record(self, record: RuntimeDegradationRecord) -> None:
        self._save_runtime_state_record("runtime_degradation_record", record.record_id, record.fault_domain, record.created_at.isoformat(), record)

    def list_runtime_degradation_records(self, fault_domain: str | None = None) -> list[RuntimeDegradationRecord]:
        return self._list_runtime_state_records("runtime_degradation_record", RuntimeDegradationRecord, scope_key=fault_domain)

    def save_lease_prediction_record(self, record: LeasePredictionRecord) -> None:
        self._save_runtime_state_record("lease_prediction_record", record.prediction_id, record.lease_id, record.created_at.isoformat(), record)

    def list_lease_prediction_records(self, lease_id: str | None = None) -> list[LeasePredictionRecord]:
        return self._list_runtime_state_records("lease_prediction_record", LeasePredictionRecord, scope_key=lease_id)

    def save_lease_renewal_forecast_record(self, record: LeaseRenewalForecast) -> None:
        self._save_runtime_state_record("lease_renewal_forecast_record", record.forecast_id, record.lease_id, record.created_at.isoformat(), record)

    def list_lease_renewal_forecasts(self, lease_id: str | None = None) -> list[LeaseRenewalForecast]:
        return self._list_runtime_state_records("lease_renewal_forecast_record", LeaseRenewalForecast, scope_key=lease_id)

    def save_renewal_risk_score(self, record: RenewalRiskScore) -> None:
        self._save_runtime_state_record("renewal_risk_score", record.score_id, record.lease_id, record.created_at.isoformat(), record)

    def list_renewal_risk_scores(self, lease_id: str | None = None) -> list[RenewalRiskScore]:
        return self._list_runtime_state_records("renewal_risk_score", RenewalRiskScore, scope_key=lease_id)

    def save_lease_safety_margin(self, record: LeaseSafetyMargin) -> None:
        self._save_runtime_state_record("lease_safety_margin", record.margin_id, record.lease_id, record.created_at.isoformat(), record)

    def list_lease_safety_margins(self, lease_id: str | None = None) -> list[LeaseSafetyMargin]:
        return self._list_runtime_state_records("lease_safety_margin", LeaseSafetyMargin, scope_key=lease_id)

    def save_lease_pressure_signal(self, record: LeasePressureSignal) -> None:
        self._save_runtime_state_record("lease_pressure_signal", record.signal_id, record.lease_id, record.created_at.isoformat(), record)

    def list_lease_pressure_signals(self, lease_id: str | None = None) -> list[LeasePressureSignal]:
        return self._list_runtime_state_records("lease_pressure_signal", LeasePressureSignal, scope_key=lease_id)

    def save_backend_outage_record(self, record: BackendOutageRecord) -> None:
        self._save_runtime_state_record("backend_outage_record", record.outage_id, record.backend_name, record.created_at.isoformat(), record)

    def list_backend_outage_records(self, backend_name: str | None = None) -> list[BackendOutageRecord]:
        return self._list_runtime_state_records("backend_outage_record", BackendOutageRecord, scope_key=backend_name)

    def save_provider_outage_record(self, record: ProviderOutageRecord) -> None:
        self._save_runtime_state_record("provider_outage_record", record.outage_id, record.provider_name, record.created_at.isoformat(), record)

    def list_provider_outage_records(self, provider_name: str | None = None) -> list[ProviderOutageRecord]:
        return self._list_runtime_state_records("provider_outage_record", ProviderOutageRecord, scope_key=provider_name)

    def save_network_partition_record(self, record: NetworkPartitionRecord) -> None:
        self._save_runtime_state_record("network_partition_record", record.partition_id, record.boundary, record.created_at.isoformat(), record)

    def list_network_partition_records(self, boundary: str | None = None) -> list[NetworkPartitionRecord]:
        return self._list_runtime_state_records("network_partition_record", NetworkPartitionRecord, scope_key=boundary)

    def save_reconciliation_run(self, record: ReconciliationRun) -> None:
        self._save_runtime_state_record("reconciliation_run", record.run_id, "runtime", record.created_at.isoformat(), record)

    def list_reconciliation_runs(self) -> list[ReconciliationRun]:
        return self._list_runtime_state_records("reconciliation_run", ReconciliationRun)

    def save_recovery_backlog_record(self, record: RecoveryBacklogRecord) -> None:
        self._save_runtime_state_record("recovery_backlog_record", record.backlog_id, "runtime", record.created_at.isoformat(), record)

    def list_recovery_backlog_records(self) -> list[RecoveryBacklogRecord]:
        return self._list_runtime_state_records("recovery_backlog_record", RecoveryBacklogRecord)

    def save_provider_demand_forecast(self, record: ProviderDemandForecast) -> None:
        self._save_runtime_state_record("provider_demand_forecast", record.forecast_id, record.provider_name, record.created_at.isoformat(), record)

    def list_provider_demand_forecasts(self, provider_name: str | None = None) -> list[ProviderDemandForecast]:
        return self._list_runtime_state_records("provider_demand_forecast", ProviderDemandForecast, scope_key=provider_name)

    def save_provider_capacity_forecast(self, record: ProviderCapacityForecast) -> None:
        self._save_runtime_state_record("provider_capacity_forecast", record.forecast_id, record.provider_name, record.created_at.isoformat(), record)

    def list_provider_capacity_forecasts(self, provider_name: str | None = None) -> list[ProviderCapacityForecast]:
        return self._list_runtime_state_records("provider_capacity_forecast", ProviderCapacityForecast, scope_key=provider_name)

    def save_provider_quota_policy(self, record: ProviderQuotaPolicy) -> None:
        self._save_runtime_state_record("provider_quota_policy", record.policy_id, record.provider_name, record.created_at.isoformat(), record)

    def load_provider_quota_policy(self, provider_name: str) -> ProviderQuotaPolicy | None:
        policies = self._list_runtime_state_records("provider_quota_policy", ProviderQuotaPolicy, scope_key=provider_name)
        return None if not policies else policies[0]

    def list_provider_quota_policies(self) -> list[ProviderQuotaPolicy]:
        return self._list_runtime_state_records("provider_quota_policy", ProviderQuotaPolicy)

    def save_reservation_forecast(self, record: ReservationForecast) -> None:
        self._save_runtime_state_record("reservation_forecast", record.forecast_id, record.provider_name, record.created_at.isoformat(), record)

    def list_reservation_forecasts(self, provider_name: str | None = None) -> list[ReservationForecast]:
        return self._list_runtime_state_records("reservation_forecast", ReservationForecast, scope_key=provider_name)

    def save_capacity_trend_record(self, record: CapacityTrendRecord) -> None:
        self._save_runtime_state_record("capacity_trend_record", record.trend_id, record.provider_name, record.created_at.isoformat(), record)

    def list_capacity_trend_records(self, provider_name: str | None = None) -> list[CapacityTrendRecord]:
        return self._list_runtime_state_records("capacity_trend_record", CapacityTrendRecord, scope_key=provider_name)

    def save_quota_exhaustion_risk(self, record: QuotaExhaustionRisk) -> None:
        self._save_runtime_state_record("quota_exhaustion_risk", record.risk_id, record.provider_name, record.created_at.isoformat(), record)

    def list_quota_exhaustion_risks(self, provider_name: str | None = None) -> list[QuotaExhaustionRisk]:
        return self._list_runtime_state_records("quota_exhaustion_risk", QuotaExhaustionRisk, scope_key=provider_name)

    def save_quota_governance_decision(self, record: QuotaGovernanceDecision) -> None:
        self._save_runtime_state_record("quota_governance_decision", record.decision_id, record.provider_name, record.created_at.isoformat(), record)

    def list_quota_governance_decisions(self, provider_name: str | None = None) -> list[QuotaGovernanceDecision]:
        return self._list_runtime_state_records("quota_governance_decision", QuotaGovernanceDecision, scope_key=provider_name)

    def save_service_trust_policy(self, record: ServiceTrustPolicy) -> None:
        self._save_runtime_state_record("service_trust_policy", record.policy_id, record.trust_mode, record.created_at.isoformat(), record)

    def load_service_trust_policy(self, policy_id: str) -> ServiceTrustPolicy | None:
        return self._load_runtime_state_record("service_trust_policy", policy_id, ServiceTrustPolicy)

    def list_service_trust_policies(self) -> list[ServiceTrustPolicy]:
        return self._list_runtime_state_records("service_trust_policy", ServiceTrustPolicy)

    def save_trust_boundary_descriptor(self, record: TrustBoundaryDescriptor) -> None:
        self._save_runtime_state_record("trust_boundary_descriptor", record.boundary_id, record.boundary_name, record.created_at.isoformat(), record)

    def list_trust_boundary_descriptors(self) -> list[TrustBoundaryDescriptor]:
        return self._list_runtime_state_records("trust_boundary_descriptor", TrustBoundaryDescriptor)

    def save_network_identity_record(self, record: NetworkIdentityRecord) -> None:
        self._save_runtime_state_record("network_identity_record", record.network_identity_id, record.principal_id, record.created_at.isoformat(), record)

    def list_network_identity_records(self, principal_id: str | None = None) -> list[NetworkIdentityRecord]:
        return self._list_runtime_state_records("network_identity_record", NetworkIdentityRecord, scope_key=principal_id)

    def save_credential_binding_record(self, record: CredentialBindingRecord) -> None:
        self._save_runtime_state_record("credential_binding_record", record.binding_id, record.credential_id, record.created_at.isoformat(), record)

    def load_credential_binding_record(self, credential_id: str) -> CredentialBindingRecord | None:
        records = self._list_runtime_state_records("credential_binding_record", CredentialBindingRecord, scope_key=credential_id)
        return None if not records else records[0]

    def list_credential_binding_records(self, credential_id: str | None = None) -> list[CredentialBindingRecord]:
        return self._list_runtime_state_records("credential_binding_record", CredentialBindingRecord, scope_key=credential_id)

    def save_security_incident(self, record: SecurityIncidentRecord) -> None:
        self._save_runtime_state_record("security_incident_record", record.incident_id, record.credential_id, record.created_at.isoformat(), record)

    def list_security_incidents(self, credential_id: str | None = None) -> list[SecurityIncidentRecord]:
        return self._list_runtime_state_records("security_incident_record", SecurityIncidentRecord, scope_key=credential_id)

    def save_trust_replay_record(self, record: TrustReplayRecord) -> None:
        self._save_runtime_state_record("trust_replay_record", record.replay_id, record.credential_id, record.created_at.isoformat(), record)

    def load_trust_replay_record(self, *, request_id: str | None = None, nonce: str | None = None) -> TrustReplayRecord | None:
        records = self._list_runtime_state_records("trust_replay_record", TrustReplayRecord)
        for record in records:
            if request_id is not None and record.request_id == request_id:
                return record
            if nonce is not None and record.nonce == nonce:
                return record
        return None

    def load_control_plane_request(
        self,
        *,
        request_id: str | None = None,
        nonce: str | None = None,
        idempotency_key: str | None = None,
    ) -> ControlPlaneRequestRecord | None:
        if request_id is not None:
            row = self._fetchone("SELECT * FROM control_plane_requests WHERE request_id = ?", (request_id,))
            return None if row is None else self._model_from_row("control_plane_requests", row, ControlPlaneRequestRecord)
        if nonce is not None:
            row = self._fetchone(
                "SELECT * FROM control_plane_requests WHERE nonce = ? ORDER BY created_at DESC LIMIT 1",
                (nonce,),
            )
            return None if row is None else self._model_from_row("control_plane_requests", row, ControlPlaneRequestRecord)
        if idempotency_key is not None:
            row = self._fetchone(
                "SELECT * FROM control_plane_requests WHERE idempotency_key = ? ORDER BY created_at DESC LIMIT 1",
                (idempotency_key,),
            )
            return None if row is None else self._model_from_row("control_plane_requests", row, ControlPlaneRequestRecord)
        return None

    def save_software_harness(self, record: SoftwareHarnessRecord) -> None:
        self._save_runtime_state_record("software_harness_record", record.harness_id, record.software_name, record.created_at.isoformat(), record)

    def load_software_harness(self, harness_id: str) -> SoftwareHarnessRecord | None:
        return self._load_runtime_state_record("software_harness_record", harness_id, SoftwareHarnessRecord)

    def list_software_harnesses(self, software_name: str | None = None) -> list[SoftwareHarnessRecord]:
        return self._list_runtime_state_records("software_harness_record", SoftwareHarnessRecord, scope_key=software_name)

    def save_software_command(self, record: SoftwareCommandDescriptor) -> None:
        self._save_runtime_state_record("software_command_descriptor", record.command_id, record.harness_id, record.created_at.isoformat(), record)

    def list_software_commands(self, harness_id: str | None = None) -> list[SoftwareCommandDescriptor]:
        return self._list_runtime_state_records("software_command_descriptor", SoftwareCommandDescriptor, scope_key=harness_id)

    def save_software_control_policy(self, record: SoftwareControlPolicy) -> None:
        self._save_runtime_state_record("software_control_policy", record.policy_id, record.harness_id, record.created_at.isoformat(), record)

    def load_software_control_policy(self, harness_id: str) -> SoftwareControlPolicy | None:
        policies = self._list_runtime_state_records("software_control_policy", SoftwareControlPolicy, scope_key=harness_id)
        return None if not policies else policies[0]

    def save_software_harness_validation(self, record: SoftwareHarnessValidation) -> None:
        self._save_runtime_state_record("software_harness_validation", record.validation_id, record.harness_id, record.validated_at.isoformat(), record)

    def latest_software_harness_validation(self, harness_id: str) -> SoftwareHarnessValidation | None:
        records = self._list_runtime_state_records("software_harness_validation", SoftwareHarnessValidation, scope_key=harness_id)
        return None if not records else records[0]

    def save_software_control_bridge(self, record: SoftwareControlBridgeConfig) -> None:
        self._save_runtime_state_record("software_control_bridge", record.bridge_id, record.source_kind, record.last_synced_at.isoformat(), record)

    def list_software_control_bridges(self, source_kind: str | None = None) -> list[SoftwareControlBridgeConfig]:
        return self._list_runtime_state_records("software_control_bridge", SoftwareControlBridgeConfig, scope_key=source_kind)

    def save_software_build_request(self, record: SoftwareBuildRequest) -> None:
        self._save_runtime_state_record("software_build_request", record.build_request_id, record.source_kind, record.created_at.isoformat(), record)

    def list_software_build_requests(self, source_kind: str | None = None) -> list[SoftwareBuildRequest]:
        return self._list_runtime_state_records("software_build_request", SoftwareBuildRequest, scope_key=source_kind)

    def save_software_risk_class(self, record: SoftwareRiskClass) -> None:
        self._save_runtime_state_record("software_risk_class", record.risk_level, record.risk_level, utc_now().isoformat(), record)

    def list_software_risk_classes(self) -> list[SoftwareRiskClass]:
        return self._list_runtime_state_records("software_risk_class", SoftwareRiskClass, scope_key=None)

    def save_app_capability(self, record: AppCapabilityRecord) -> None:
        self._save_runtime_state_record("app_capability_record", record.capability_id, record.harness_id, record.created_at.isoformat(), record)

    def load_app_capability(self, harness_id: str) -> AppCapabilityRecord | None:
        records = self._list_runtime_state_records("app_capability_record", AppCapabilityRecord, scope_key=harness_id)
        return None if not records else records[0]

    def save_harness_manifest(self, record: HarnessManifest) -> None:
        self._save_runtime_state_record("harness_manifest", record.manifest_id, record.harness_id, record.created_at.isoformat(), record)

    def load_harness_manifest(self, harness_id: str) -> HarnessManifest | None:
        records = self._list_runtime_state_records("harness_manifest", HarnessManifest, scope_key=harness_id)
        return None if not records else records[0]

    def save_software_action_receipt(self, record: SoftwareActionReceipt) -> None:
        self._save_runtime_state_record("software_action_receipt", record.action_id, record.task_id, record.created_at.isoformat(), record)

    def list_software_action_receipts(self, task_id: str | None = None) -> list[SoftwareActionReceipt]:
        return self._list_runtime_state_records("software_action_receipt", SoftwareActionReceipt, scope_key=task_id)

    def save_software_replay_record(self, record: SoftwareReplayRecord) -> None:
        self._save_runtime_state_record("software_replay_record", record.replay_id, record.task_id, record.created_at.isoformat(), record)

    def list_software_replay_records(self, task_id: str | None = None) -> list[SoftwareReplayRecord]:
        return self._list_runtime_state_records("software_replay_record", SoftwareReplayRecord, scope_key=task_id)

    def save_software_failure_pattern(self, record: SoftwareFailurePattern) -> None:
        self._save_runtime_state_record("software_failure_pattern", record.pattern_id, record.harness_id, record.updated_at.isoformat(), record)

    def list_software_failure_patterns(self, harness_id: str | None = None) -> list[SoftwareFailurePattern]:
        return self._list_runtime_state_records("software_failure_pattern", SoftwareFailurePattern, scope_key=harness_id)

    def save_software_automation_macro(self, record: SoftwareAutomationMacro) -> None:
        self._save_runtime_state_record("software_automation_macro", record.macro_id, record.harness_id, record.created_at.isoformat(), record)

    def load_software_automation_macro(self, macro_id: str) -> SoftwareAutomationMacro | None:
        return self._load_runtime_state_record("software_automation_macro", macro_id, SoftwareAutomationMacro)

    def list_software_automation_macros(self, harness_id: str | None = None) -> list[SoftwareAutomationMacro]:
        return self._list_runtime_state_records("software_automation_macro", SoftwareAutomationMacro, scope_key=harness_id)

    def save_software_replay_diagnostic(self, record: SoftwareReplayDiagnostic) -> None:
        self._save_runtime_state_record(
            "software_replay_diagnostic",
            record.diagnostic_id,
            record.task_id,
            record.created_at.isoformat(),
            record,
        )

    def list_software_replay_diagnostics(self, task_id: str | None = None) -> list[SoftwareReplayDiagnostic]:
        return self._list_runtime_state_records("software_replay_diagnostic", SoftwareReplayDiagnostic, scope_key=task_id)

    def save_software_recovery_hint(self, record: SoftwareRecoveryHint) -> None:
        self._save_runtime_state_record("software_recovery_hint", record.hint_id, record.harness_id, record.created_at.isoformat(), record)

    def list_software_recovery_hints(self, harness_id: str | None = None) -> list[SoftwareRecoveryHint]:
        return self._list_runtime_state_records("software_recovery_hint", SoftwareRecoveryHint, scope_key=harness_id)

    def save_software_failure_cluster(self, record: SoftwareFailureCluster) -> None:
        self._save_runtime_state_record("software_failure_cluster", record.cluster_id, record.harness_id, record.created_at.isoformat(), record)

    def list_software_failure_clusters(self, harness_id: str | None = None) -> list[SoftwareFailureCluster]:
        return self._list_runtime_state_records("software_failure_cluster", SoftwareFailureCluster, scope_key=harness_id)

    def save_maintenance_daemon_run(self, record: MaintenanceDaemonRun) -> None:
        self._save_runtime_state_record("maintenance_daemon_run", record.daemon_run_id, record.worker_id, record.completed_at.isoformat(), record)

    def list_maintenance_daemon_runs(self, worker_id: str | None = None) -> list[MaintenanceDaemonRun]:
        return self._list_runtime_state_records("maintenance_daemon_run", MaintenanceDaemonRun, scope_key=worker_id)

    def save_maintenance_worker_lease_state(self, record: MaintenanceWorkerLeaseState) -> None:
        self._save_runtime_state_record(
            "maintenance_worker_lease_state",
            record.lease_state_id,
            record.worker_id,
            record.captured_at.isoformat(),
            record,
        )

    def list_maintenance_worker_lease_states(self, worker_id: str | None = None) -> list[MaintenanceWorkerLeaseState]:
        return self._list_runtime_state_records("maintenance_worker_lease_state", MaintenanceWorkerLeaseState, scope_key=worker_id)

    def save_maintenance_incident_recommendation(self, record: MaintenanceIncidentRecommendation) -> None:
        self._save_runtime_state_record(
            "maintenance_incident_recommendation",
            record.recommendation_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_maintenance_incident_recommendations(self, scope_key: str | None = None) -> list[MaintenanceIncidentRecommendation]:
        return self._list_runtime_state_records("maintenance_incident_recommendation", MaintenanceIncidentRecommendation, scope_key=scope_key)

    def save_maintenance_resolution_analytics(self, record: MaintenanceResolutionAnalytics) -> None:
        self._save_runtime_state_record(
            "maintenance_resolution_analytics",
            record.resolution_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_maintenance_resolution_analytics(self, scope_key: str | None = None) -> list[MaintenanceResolutionAnalytics]:
        return self._list_runtime_state_records("maintenance_resolution_analytics", MaintenanceResolutionAnalytics, scope_key=scope_key)

    def export_trace_bundle(self, task_id: str) -> dict[str, Any]:
        return {
            "replay": self.replay_task(task_id),
            "handoff": None
            if self.latest_handoff_packet(task_id) is None
            else self.latest_handoff_packet(task_id).to_dict(),
            "open_questions": [item.to_dict() for item in self.list_open_questions(task_id)],
            "next_actions": [item.to_dict() for item in self.list_next_actions(task_id)],
            "telemetry": [item.to_dict() for item in self.query_telemetry(task_id=task_id)],
        }

    def _save_runtime_state_record(
        self,
        record_type: str,
        record_id: str,
        scope_key: str,
        created_at: str,
        record: Any,
    ) -> None:
        self._insert_or_replace(
            "runtime_state_records",
            {
                "record_type": record_type,
                "record_id": record_id,
                "scope_key": scope_key,
                "created_at": created_at,
                "record_version": getattr(record, "version", "1.0"),
                "payload_json": self.dumps(record.to_dict()),
            },
        )

    def _load_runtime_state_record(self, record_type: str, record_id: str, model_cls: type[Any]) -> Any | None:
        row = self._fetchone(
            "SELECT * FROM runtime_state_records WHERE record_type = ? AND record_id = ?",
            (record_type, record_id),
        )
        return None if row is None else self._model_from_row("runtime_state_records", row, model_cls)

    def _list_runtime_state_records(self, record_type: str, model_cls: type[Any], scope_key: str | None = None) -> list[Any]:
        if scope_key is None:
            rows = self._fetchall(
                "SELECT * FROM runtime_state_records WHERE record_type = ? ORDER BY created_at DESC",
                (record_type,),
            )
        else:
            rows = self._fetchall(
                "SELECT * FROM runtime_state_records WHERE record_type = ? AND scope_key = ? ORDER BY created_at DESC",
                (record_type, scope_key),
            )
        return [self._model_from_row("runtime_state_records", row, model_cls) for row in rows]

    def _delete_runtime_state_records(
        self,
        *,
        record_type: str,
        scope_key: str | None = None,
        record_ids: list[str] | None = None,
    ) -> int:
        clauses = ["record_type = ?"]
        params: list[Any] = [record_type]
        if scope_key is not None:
            clauses.append("scope_key = ?")
            params.append(scope_key)
        if record_ids:
            placeholders = ", ".join("?" for _ in record_ids)
            clauses.append(f"record_id IN ({placeholders})")
            params.extend(record_ids)
        query = "DELETE FROM runtime_state_records WHERE " + " AND ".join(clauses)
        with self._connect() as connection:
            cursor = connection.execute(query, tuple(params))
            connection.commit()
            return int(cursor.rowcount)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _execute(self, query: str, params: tuple[Any, ...]) -> None:
        with self._connect() as connection:
            connection.execute(query, params)
            connection.commit()

    def _insert_or_replace(self, table: str, values: dict[str, Any]) -> None:
        columns = ", ".join(values.keys())
        placeholders = ", ".join("?" for _ in values)
        query = f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})"
        with self._connect() as connection:
            connection.execute(query, tuple(values.values()))
            connection.commit()

    def _fetchone(self, query: str, params: tuple[Any, ...]) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(query, params).fetchone()

    def _fetchall(self, query: str, params: tuple[Any, ...]) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return list(connection.execute(query, params).fetchall())

    def _model_from_row(self, table: str, row: sqlite3.Row | None, model_cls: type[Any]) -> Any:
        if row is None:
            raise KeyError(table)
        record_version = str(row["record_version"]) if "record_version" in row.keys() else "1.0"
        payload = self.loads(str(row["payload_json"]))
        payload = migrate_payload(table, payload, record_version)
        defaults = {
            field.name: field.default
            for field in fields(model_cls)
            if field.default is not MISSING
        }
        defaults.update(payload)
        return model_cls.from_dict(defaults)

    def _now_iso(self) -> str:
        from contract_evidence_os.base import utc_now

        return utc_now().isoformat()
