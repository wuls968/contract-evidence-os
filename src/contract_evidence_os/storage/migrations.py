"""SQLite schema migrations."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class Migration:
    """One schema migration step."""

    name: str
    statements: tuple[str, ...]


class MigrationRunner:
    """Apply incremental schema migrations to the SQLite store."""

    MIGRATIONS: tuple[Migration, ...] = (
        Migration(
            "001_initial_core",
            (
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    current_phase TEXT,
                    request_json TEXT NOT NULL,
                    result_json TEXT,
                    contract_id TEXT,
                    plan_graph_id TEXT,
                    latest_checkpoint_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS contracts (
                    contract_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    normalized_goal TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS contract_deltas (
                    delta_id TEXT PRIMARY KEY,
                    contract_id TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS contract_lattices (
                    root_contract_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS plan_graphs (
                    graph_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS plan_nodes (
                    task_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    role_owner TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    approval_gate TEXT,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (task_id, node_id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS plan_edges (
                    edge_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    source_node_id TEXT NOT NULL,
                    target_node_id TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS source_records (
                    source_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    locator TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    credibility REAL NOT NULL,
                    retrieved_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS evidence_nodes (
                    node_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    node_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS evidence_edges (
                    edge_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    source_node_id TEXT NOT NULL,
                    target_node_id TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS claim_records (
                    claim_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    claim_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS validation_reports (
                    report_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    contract_id TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    validator TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS tool_invocations (
                    invocation_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    tool_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS tool_results (
                    invocation_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    tool_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    confidence REAL,
                    provider_mode TEXT NOT NULL,
                    deterministic INTEGER NOT NULL DEFAULT 0,
                    provenance_json TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    contract_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS execution_receipts (
                    receipt_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    contract_id TEXT NOT NULL,
                    plan_node_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    tool_used TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    plan_node_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    state_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    incident_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS memory_records (
                    memory_id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    state TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS memory_promotions (
                    promotion_id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    new_state TEXT NOT NULL,
                    promoted_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS skill_capsules (
                    skill_id TEXT PRIMARY KEY,
                    promotion_status TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS evolution_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    candidate_type TEXT NOT NULL,
                    target_component TEXT NOT NULL,
                    promotion_result TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    run_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    suite_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS canary_runs (
                    run_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    status TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
            ),
        ),
        Migration(
            "002_query_indexes",
            (
                "CREATE INDEX IF NOT EXISTS idx_tasks_status_updated ON tasks(status, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_tasks_phase ON tasks(current_phase)",
                "CREATE INDEX IF NOT EXISTS idx_audit_query ON audit_events(task_id, event_type, actor, risk_level, timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_evidence_nodes_type ON evidence_nodes(task_id, node_type, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_evidence_edges_lineage ON evidence_edges(task_id, source_node_id, target_node_id)",
                "CREATE INDEX IF NOT EXISTS idx_checkpoints_task_sequence ON checkpoints(task_id, sequence DESC)",
                "CREATE INDEX IF NOT EXISTS idx_incidents_task_created ON incidents(task_id, created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_tool_invocations_task_idempotency ON tool_invocations(task_id, idempotency_key)",
                "CREATE INDEX IF NOT EXISTS idx_plan_nodes_task_status ON plan_nodes(task_id, status, position)",
                "CREATE INDEX IF NOT EXISTS idx_validation_reports_task ON validation_reports(task_id, status)",
            ),
        ),
        Migration(
            "003_routing_and_eval",
            (
                """
                CREATE TABLE IF NOT EXISTS routing_receipts (
                    routing_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    workload TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    provider_name TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    cost_tier TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    fallback_used INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_routing_receipts_task ON routing_receipts(task_id, role, workload, created_at)",
            ),
        ),
        Migration(
            "004_long_horizon_and_ops",
            (
                """
                CREATE TABLE IF NOT EXISTS evidence_deltas (
                    delta_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS handoff_packets (
                    packet_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    contract_id TEXT NOT NULL,
                    plan_graph_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS handoff_packet_versions (
                    packet_version_id TEXT PRIMARY KEY,
                    packet_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS handoff_sections (
                    section_id TEXT PRIMARY KEY,
                    packet_id TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS open_questions (
                    question_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    contract_id TEXT NOT NULL,
                    related_plan_node TEXT,
                    blocking_severity TEXT NOT NULL,
                    owner_role TEXT NOT NULL,
                    status TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS next_actions (
                    action_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    contract_id TEXT NOT NULL,
                    related_plan_node TEXT,
                    urgency TEXT NOT NULL,
                    status TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS workspace_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS context_compactions (
                    context_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS prompt_budget_allocations (
                    allocation_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    role_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS continuity_working_sets (
                    working_set_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    handoff_packet_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS approval_requests (
                    request_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    contract_id TEXT NOT NULL,
                    plan_node_id TEXT,
                    status TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    expiry_at TEXT,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS approval_decisions (
                    decision_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    plan_node_id TEXT,
                    status TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS human_interventions (
                    intervention_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS telemetry_events (
                    event_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS tool_scorecards (
                    tool_name TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (tool_name, variant)
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_open_questions_task ON open_questions(task_id, status, blocking_severity)",
                "CREATE INDEX IF NOT EXISTS idx_next_actions_task ON next_actions(task_id, status, urgency)",
                "CREATE INDEX IF NOT EXISTS idx_handoff_packets_task ON handoff_packets(task_id, created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_workspace_snapshots_task ON workspace_snapshots(task_id, created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_context_compactions_task ON context_compactions(task_id, created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_approval_requests_task ON approval_requests(task_id, status, risk_level)",
                "CREATE INDEX IF NOT EXISTS idx_telemetry_events_task ON telemetry_events(task_id, event_type, timestamp)",
            ),
        ),
        Migration(
            "005_execution_depth_and_remote_ops",
            (
                """
                CREATE TABLE IF NOT EXISTS provider_usage_records (
                    usage_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    plan_node_id TEXT NOT NULL,
                    correlation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    provider_name TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS plan_revisions (
                    revision_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    plan_graph_id TEXT NOT NULL,
                    cause TEXT NOT NULL,
                    branch_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS execution_branches (
                    branch_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    plan_graph_id TEXT NOT NULL,
                    parent_branch_id TEXT,
                    status TEXT NOT NULL,
                    selected INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS scheduler_states (
                    scheduler_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    plan_graph_id TEXT NOT NULL,
                    active_branch_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS remote_approval_operations (
                    operation_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    contract_id TEXT NOT NULL,
                    plan_node_id TEXT,
                    operator TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_provider_usage_task ON provider_usage_records(task_id, plan_node_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_plan_revisions_task ON plan_revisions(task_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_execution_branches_task ON execution_branches(task_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_scheduler_states_task ON scheduler_states(task_id, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_remote_approval_ops_task ON remote_approval_operations(task_id, request_id, created_at)",
            ),
        ),
        Migration(
            "006_operations_governance_and_budgeting",
            (
                """
                CREATE TABLE IF NOT EXISTS provider_capabilities (
                    provider_name TEXT PRIMARY KEY,
                    availability_state TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS provider_scorecards (
                    provider_name TEXT NOT NULL,
                    profile TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (provider_name, profile)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS routing_policies (
                    policy_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    execution_mode TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS routing_decisions (
                    decision_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    plan_node_id TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS budget_policies (
                    policy_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS budget_ledgers (
                    ledger_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS budget_events (
                    event_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS budget_consumption_records (
                    consumption_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS execution_modes (
                    mode_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    mode_name TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS governance_events (
                    event_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS concurrency_states (
                    concurrency_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_provider_capabilities_state ON provider_capabilities(availability_state)",
                "CREATE INDEX IF NOT EXISTS idx_provider_scorecards_provider ON provider_scorecards(provider_name, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_routing_decisions_task ON routing_decisions(task_id, plan_node_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_budget_ledgers_task ON budget_ledgers(task_id, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_budget_events_task ON budget_events(task_id, event_type, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_execution_modes_task ON execution_modes(task_id, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_governance_events_task ON governance_events(task_id, event_type, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_concurrency_states_task ON concurrency_states(task_id, updated_at)",
            ),
        ),
        Migration(
            "007_system_scale_operations_and_policy_registry",
            (
                """
                CREATE TABLE IF NOT EXISTS queue_items (
                    queue_item_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    contract_id TEXT NOT NULL,
                    queue_name TEXT NOT NULL,
                    priority_class TEXT NOT NULL,
                    status TEXT NOT NULL,
                    available_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS queue_leases (
                    lease_id TEXT PRIMARY KEY,
                    queue_item_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS admission_decisions (
                    decision_id TEXT PRIMARY KEY,
                    queue_item_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    active_mode TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS dispatch_records (
                    dispatch_id TEXT PRIMARY KEY,
                    queue_item_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    lease_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS queue_policies (
                    policy_id TEXT PRIMARY KEY,
                    queue_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS capacity_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS load_shedding_events (
                    event_id TEXT PRIMARY KEY,
                    queue_item_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS admission_policies (
                    policy_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS queue_priority_policies (
                    policy_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS capacity_policies (
                    policy_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS load_shedding_policies (
                    policy_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS recovery_reservation_policies (
                    policy_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS global_execution_modes (
                    mode_id TEXT PRIMARY KEY,
                    mode_name TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS operator_overrides (
                    override_id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    status TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS provider_health_records (
                    provider_name TEXT PRIMARY KEY,
                    availability_state TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS provider_health_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS rate_limit_states (
                    provider_name TEXT PRIMARY KEY,
                    limited_until TEXT,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS provider_cooldown_windows (
                    provider_name TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    cooldown_until TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS provider_degradation_events (
                    event_id TEXT PRIMARY KEY,
                    provider_name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS provider_availability_policies (
                    policy_id TEXT PRIMARY KEY,
                    provider_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS policy_scopes (
                    scope_id TEXT PRIMARY KEY,
                    scope_type TEXT NOT NULL,
                    target_component TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS policy_versions (
                    version_id TEXT PRIMARY KEY,
                    scope_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS policy_evidence_bundles (
                    bundle_id TEXT PRIMARY KEY,
                    scope_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS policy_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    scope_id TEXT NOT NULL,
                    base_version_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS policy_promotion_runs (
                    run_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS policy_rollback_records (
                    rollback_id TEXT PRIMARY KEY,
                    scope_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_queue_items_status ON queue_items(status, queue_name, available_at, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_queue_leases_status ON queue_leases(status, expires_at)",
                "CREATE INDEX IF NOT EXISTS idx_admission_decisions_task ON admission_decisions(task_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_dispatch_records_task ON dispatch_records(task_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_load_shedding_task ON load_shedding_events(task_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_operator_overrides_scope ON operator_overrides(scope, action, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_provider_health_state ON provider_health_records(availability_state, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_provider_degradation_provider ON provider_degradation_events(provider_name, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_policy_versions_scope ON policy_versions(scope_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_policy_candidates_scope ON policy_candidates(scope_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_policy_runs_candidate ON policy_promotion_runs(candidate_id, created_at)",
            ),
        ),
        Migration(
            "008_multi_worker_coordination_and_secure_control_plane",
            (
                """
                CREATE TABLE IF NOT EXISTS workers (
                    worker_id TEXT PRIMARY KEY,
                    worker_role TEXT NOT NULL,
                    process_identity TEXT NOT NULL,
                    heartbeat_state TEXT NOT NULL,
                    shutdown_state TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS worker_capabilities (
                    worker_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS worker_heartbeats (
                    heartbeat_id TEXT PRIMARY KEY,
                    worker_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS worker_pressure_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS lease_ownerships (
                    ownership_id TEXT PRIMARY KEY,
                    lease_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    lease_epoch INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS dispatch_ownerships (
                    ownership_id TEXT PRIMARY KEY,
                    dispatch_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS provider_capacity_records (
                    provider_name TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS provider_pool_states (
                    pool_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS provider_pressure_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS provider_reservations (
                    reservation_id TEXT PRIMARY KEY,
                    provider_name TEXT NOT NULL,
                    reservation_type TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS provider_balance_decisions (
                    decision_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    workload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS provider_pool_events (
                    event_id TEXT PRIMARY KEY,
                    provider_name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS auth_scopes (
                    scope_name TEXT PRIMARY KEY,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS auth_principals (
                    principal_id TEXT PRIMARY KEY,
                    principal_name TEXT NOT NULL,
                    principal_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS auth_credentials (
                    credential_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    session_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    credential_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    authenticated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS auth_events (
                    event_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    credential_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS revoked_credentials (
                    revocation_id TEXT PRIMARY KEY,
                    credential_id TEXT NOT NULL,
                    revoked_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS control_plane_requests (
                    request_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    sensitive INTEGER NOT NULL DEFAULT 0,
                    accepted INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_workers_state ON workers(heartbeat_state, shutdown_state, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_worker_heartbeats_worker ON worker_heartbeats(worker_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_lease_ownerships_lease ON lease_ownerships(lease_id, lease_epoch, acquired_at)",
                "CREATE INDEX IF NOT EXISTS idx_dispatch_ownerships_dispatch ON dispatch_ownerships(dispatch_id, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_provider_reservations_provider ON provider_reservations(provider_name, status, expires_at)",
                "CREATE INDEX IF NOT EXISTS idx_provider_balance_task ON provider_balance_decisions(task_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_auth_credentials_hash ON auth_credentials(token_hash, status)",
                "CREATE INDEX IF NOT EXISTS idx_auth_events_request ON auth_events(request_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_control_plane_nonce ON control_plane_requests(nonce, created_at)",
            ),
        ),
        Migration(
            "009_external_backends_cross_host_and_network_security",
            (
                """
                CREATE TABLE IF NOT EXISTS backend_capability_descriptors (
                    backend_name TEXT PRIMARY KEY,
                    backend_kind TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS backend_health_records (
                    backend_name TEXT PRIMARY KEY,
                    backend_kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS backend_pressure_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    backend_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS host_records (
                    host_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    drain_state TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS worker_host_bindings (
                    binding_id TEXT PRIMARY KEY,
                    worker_id TEXT NOT NULL,
                    host_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    bound_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS worker_endpoint_records (
                    endpoint_id TEXT PRIMARY KEY,
                    worker_id TEXT NOT NULL,
                    host_id TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS lease_renewal_policies (
                    policy_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS renewal_attempt_records (
                    attempt_id TEXT PRIMARY KEY,
                    lease_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    host_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS lease_expiry_forecasts (
                    forecast_id TEXT PRIMARY KEY,
                    lease_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS lease_contention_records (
                    contention_id TEXT PRIMARY KEY,
                    lease_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS work_steal_policies (
                    policy_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS work_steal_decisions (
                    decision_id TEXT PRIMARY KEY,
                    lease_id TEXT NOT NULL,
                    from_worker_id TEXT NOT NULL,
                    to_worker_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS lease_transfer_records (
                    transfer_id TEXT PRIMARY KEY,
                    lease_id TEXT NOT NULL,
                    from_worker_id TEXT NOT NULL,
                    to_worker_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS ownership_conflict_events (
                    event_id TEXT PRIMARY KEY,
                    lease_id TEXT NOT NULL,
                    stale_worker_id TEXT NOT NULL,
                    active_worker_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS provider_fairness_records (
                    record_id TEXT PRIMARY KEY,
                    provider_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS provider_pool_balance_policies (
                    policy_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS reservation_policies (
                    policy_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS fairness_policies (
                    policy_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS sustained_pressure_policies (
                    policy_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS service_principals (
                    principal_id TEXT PRIMARY KEY,
                    service_role TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS service_credentials (
                    credential_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS service_trust_records (
                    trust_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS credential_rotation_records (
                    rotation_id TEXT PRIMARY KEY,
                    old_credential_id TEXT NOT NULL,
                    new_credential_id TEXT NOT NULL,
                    rotated_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS auth_failure_events (
                    event_id TEXT PRIMARY KEY,
                    principal_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS host_drain_events (
                    event_id TEXT PRIMARY KEY,
                    host_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_backend_health_status ON backend_health_records(status, updated_at)",
                "CREATE INDEX IF NOT EXISTS idx_backend_pressure_name ON backend_pressure_snapshots(backend_name, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_host_records_state ON host_records(status, drain_state, last_seen_at)",
                "CREATE INDEX IF NOT EXISTS idx_worker_host_bindings_worker ON worker_host_bindings(worker_id, host_id, bound_at)",
                "CREATE INDEX IF NOT EXISTS idx_worker_endpoint_worker ON worker_endpoint_records(worker_id, host_id, last_seen_at)",
                "CREATE INDEX IF NOT EXISTS idx_renewal_attempts_lease ON renewal_attempt_records(lease_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_lease_contention_lease ON lease_contention_records(lease_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_work_steal_lease ON work_steal_decisions(lease_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_lease_transfer_lease ON lease_transfer_records(lease_id, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_provider_fairness_provider ON provider_fairness_records(provider_name, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_service_credentials_principal ON service_credentials(principal_id, issued_at)",
                "CREATE INDEX IF NOT EXISTS idx_auth_failures_action ON auth_failure_events(action, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_host_drain_events_host ON host_drain_events(host_id, created_at)",
            ),
        ),
        Migration(
            "010_durable_shared_state_reliability_forecasts_and_trust",
            (
                """
                CREATE TABLE IF NOT EXISTS runtime_state_records (
                    record_type TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (record_type, record_id)
                )
                """,
                "CREATE INDEX IF NOT EXISTS idx_runtime_state_type_scope ON runtime_state_records(record_type, scope_key, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_runtime_state_created ON runtime_state_records(created_at, record_type)",
            ),
        ),
        Migration(
            "011_software_control_harness_indexes",
            (
                "CREATE INDEX IF NOT EXISTS idx_tool_invocations_tool_requested ON tool_invocations(tool_id, requested_at)",
                "CREATE INDEX IF NOT EXISTS idx_tool_results_tool_completed ON tool_results(tool_id, completed_at)",
                "CREATE INDEX IF NOT EXISTS idx_runtime_state_software_control ON runtime_state_records(record_type, scope_key, record_id)",
            ),
        ),
    )

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def current_version(self) -> str | None:
        with self._connect() as connection:
            self._ensure_migration_table(connection)
            row = connection.execute(
                "SELECT name FROM schema_migrations ORDER BY applied_at DESC, name DESC LIMIT 1"
            ).fetchone()
            return None if row is None else str(row["name"])

    def apply_up_to(self, target_name: str) -> None:
        with self._connect() as connection:
            self._ensure_migration_table(connection)
            applied = self._applied(connection)
            for migration in self.MIGRATIONS:
                if migration.name in applied:
                    if migration.name == target_name:
                        break
                    continue
                self._apply(connection, migration)
                if migration.name == target_name:
                    break
            connection.commit()

    def apply_all(self) -> None:
        with self._connect() as connection:
            self._ensure_migration_table(connection)
            applied = self._applied(connection)
            for migration in self.MIGRATIONS:
                if migration.name not in applied:
                    self._apply(connection, migration)
            connection.commit()

    def _apply(self, connection: sqlite3.Connection, migration: Migration) -> None:
        for statement in migration.statements:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations(name, applied_at) VALUES (?, ?)",
            (migration.name, datetime.now(tz=UTC).isoformat()),
        )

    def _applied(self, connection: sqlite3.Connection) -> set[str]:
        rows = connection.execute("SELECT name FROM schema_migrations").fetchall()
        return {str(row["name"]) for row in rows}

    def _ensure_migration_table(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection
