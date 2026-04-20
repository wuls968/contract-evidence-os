"""Trusted-runtime and dashboard read models for the browser console."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from contract_evidence_os.api.operator import OperatorAPI
from contract_evidence_os.base import SchemaModel, utc_now
from contract_evidence_os.console._base import ConsoleSubservice
from contract_evidence_os.contracts.models import TaskContract
from contract_evidence_os.evidence.models import ClaimRecord, EvidenceSpan, SourceRecord, ValidationReport
from contract_evidence_os.runtime.providers import ProviderUsageRecord
from contract_evidence_os.trusted_runtime.models import (
    AuditEventBundle,
    AuditLogEntry,
    AuditTrendReport,
    BenchmarkRun,
    BenchmarkSuite,
    BenchmarkSummaryView,
    CollaborationSummaryView,
    EvidenceTraceView,
    HumanReviewCase,
    HumanReviewDecision,
    MCPInvocationRecord,
    MCPPermissionDecision,
    MCPServerRecord,
    MCPToolRecord,
    PlaybookRecord,
    PlaybookStep,
    ReproEvalRun,
    StructuredSchemaRecord,
    TaskCollaborationBinding,
    TaskTimelineView,
)


class ConsoleProjectionService(ConsoleSubservice):
    """Own trusted-runtime projections and browser-ready read models."""

    def schema_registry(self) -> dict[str, Any]:
        schema_specs: list[tuple[str, str, type[SchemaModel], list[str]]] = [
            ("contract-input", "Contract input schema", TaskContract, ["Structured contract payloads remain JSON-schema governed."]),
            ("evidence-source", "Evidence source schema", SourceRecord, ["Source metadata is the anchor for evidence spans."]),
            ("evidence-span", "Evidence span schema", EvidenceSpan, ["Claims and validation reports can point at exact source spans."]),
            ("claim-record", "Claim record schema", ClaimRecord, ["Claims must remain evidence-linked and span-addressable."]),
            ("validation-report", "Validation report schema", ValidationReport, ["Verifier output stays evidence-bound and reviewable."]),
            ("audit-log-entry", "Audit log entry schema", AuditLogEntry, ["The audit ledger is append-only and human-readable."]),
            ("playbook-record", "Playbook schema", PlaybookRecord, ["High-value delivery paths become explicit playbooks."]),
            ("human-review-case", "Human review schema", HumanReviewCase, ["Approvals, evidence review, and benchmark sign-off share one review model."]),
            ("benchmark-run", "Benchmark run schema", BenchmarkRun, ["Benchmark and repro-eval summaries stay structured and exportable."]),
            ("mcp-tool-record", "MCP tool descriptor schema", MCPToolRecord, ["MCP tools must publish structured descriptors and permission modes."]),
        ]
        items: list[dict[str, Any]] = []
        for schema_id, title, model_cls, notes in schema_specs:
            record = StructuredSchemaRecord(
                version="1.0",
                schema_id=schema_id,
                schema_kind=model_cls.__name__,
                title=title,
                json_schema=model_cls.json_schema(),
                compatibility_notes=notes,
            )
            self._save_model("trusted_schema_record", record.schema_id, schema_id, record.created_at.isoformat(), record)
            items.append(record.to_dict())
        return {"items": items}

    def _synthesized_evidence_spans(self, task_id: str) -> list[EvidenceSpan]:
        sources = self.repository.list_source_records(task_id)
        spans: list[EvidenceSpan] = []
        for source in sources:
            text = source.snippet.strip() or source.locator
            span = EvidenceSpan(
                version="1.0",
                span_id=f"span-{source.source_id}",
                source_id=source.source_id,
                locator=source.locator,
                label=source.source_type,
                start_offset=0,
                end_offset=len(text),
                text=text,
                metadata={"credibility": source.credibility, "time_relevance": source.time_relevance},
                created_at=source.retrieved_at,
            )
            self._save_model("trusted_evidence_span", span.span_id, task_id, span.created_at.isoformat(), span)
            spans.append(span)
        return spans

    def _audit_log_entries(self, task_id: str | None = None) -> list[AuditLogEntry]:
        entries: list[AuditLogEntry] = []
        tasks = [task_id] if task_id else [str(item["task_id"]) for item in self.repository.list_tasks()]
        for current_task_id in tasks:
            for event in self.repository.query_audit(task_id=current_task_id):
                entry = AuditLogEntry(
                    version="1.0",
                    entry_id=f"audit-log-{event.event_id}",
                    task_id=event.task_id,
                    event_type=event.event_type,
                    actor=event.actor,
                    status=event.result,
                    summary=event.why,
                    evidence_refs=list(event.evidence_refs),
                    evidence_span_refs=[],
                    related_refs=list(event.tool_refs) + list(event.approval_refs),
                    created_at=event.timestamp,
                    risk_level=event.risk_level,
                )
                self._save_model("trusted_audit_log_entry", entry.entry_id, current_task_id, entry.created_at.isoformat(), entry)
                entries.append(entry)
            for receipt in self.repository.list_execution_receipts(current_task_id):
                entry = AuditLogEntry(
                    version="1.0",
                    entry_id=f"audit-log-{receipt.receipt_id}",
                    task_id=current_task_id,
                    event_type="execution_receipt",
                    actor=receipt.actor,
                    status=receipt.status,
                    summary=receipt.output_summary,
                    evidence_refs=list(receipt.evidence_refs),
                    evidence_span_refs=[],
                    related_refs=list(receipt.artifacts) + list(receipt.validation_refs) + list(receipt.approval_refs),
                    created_at=receipt.timestamp,
                )
                self._save_model("trusted_audit_log_entry", entry.entry_id, current_task_id, entry.created_at.isoformat(), entry)
                entries.append(entry)
        entries.sort(key=lambda item: item.created_at)
        return entries

    def _audit_trend(self, task_id: str | None = None) -> AuditTrendReport:
        buckets: dict[str, int] = {}
        entries = self._audit_log_entries(task_id)
        for entry in entries:
            bucket = entry.created_at.replace(minute=0, second=0, microsecond=0).isoformat()
            buckets[bucket] = buckets.get(bucket, 0) + 1
        report = AuditTrendReport(
            version="1.0",
            report_id=f"audit-trend-{uuid4().hex[:10]}",
            points=[{"timestamp": key, "count": value} for key, value in sorted(buckets.items())],
            summary={"total_events": len(entries), "task_id": task_id or "all"},
        )
        self._save_model("trusted_audit_trend", report.report_id, task_id or "all", report.created_at.isoformat(), report)
        return report

    def _synthesized_playbook(self, task_id: str) -> PlaybookRecord:
        plan = self.repository.load_plan(task_id)
        task = self.repository.get_task(task_id) or {"status": "draft"}
        steps: list[PlaybookStep] = []
        if plan is not None and plan.nodes:
            for node in plan.nodes:
                steps.append(
                    PlaybookStep(
                        version="1.0",
                        step_id=f"playbook-step-{node.node_id}",
                        playbook_id=f"playbook-{task_id}",
                        title=node.objective[:80],
                        description=node.objective,
                        status=node.status,
                        evidence_required=node.node_category in {"collect", "extract", "validate"},
                        checkpoint_required=node.checkpoint_required or node.node_category in {"checkpoint", "deliver"},
                        human_review_required=bool(node.approval_gate),
                        related_plan_node_id=node.node_id,
                    )
                )
        else:
            defaults = [
                ("Compile contract", "Normalize task constraints and success criteria.", "completed"),
                ("Collect evidence", "Gather source-backed material before synthesis.", "completed"),
                ("Validate delivery", "Run verifier and contradiction checks.", "completed" if task.get("status") == "delivered" else "in_progress"),
                ("Human review", "Surface approvals or review cases before publication.", "needs_review" if task.get("status") == "awaiting_approval" else "completed"),
            ]
            for index, (title, description, status) in enumerate(defaults, start=1):
                steps.append(
                    PlaybookStep(
                        version="1.0",
                        step_id=f"playbook-step-{task_id}-{index}",
                        playbook_id=f"playbook-{task_id}",
                        title=title,
                        description=description,
                        status=status,
                        evidence_required=index in {2, 3},
                        checkpoint_required=index in {1, 4},
                        human_review_required=index == 4,
                    )
                )
        playbook = PlaybookRecord(
            version="1.0",
            playbook_id=f"playbook-{task_id}",
            task_id=task_id,
            title=f"Trusted delivery playbook for {task_id}",
            status="needs_review" if task.get("status") == "awaiting_approval" else str(task.get("status", "draft")),
            rationale="Critical outputs stay tied to evidence, checkpoints, and human review requirements.",
            steps=steps,
        )
        self._save_model("trusted_playbook", playbook.playbook_id, task_id, playbook.created_at.isoformat(), playbook)
        return playbook

    def _review_cases(self, task_id: str | None = None) -> list[HumanReviewCase]:
        cases: list[HumanReviewCase] = []
        approvals = self.repository.list_approval_requests(status="pending")
        for approval in approvals:
            if task_id and approval.task_id != task_id:
                continue
            decision = HumanReviewDecision(
                version="1.0",
                decision_id=f"review-decision-placeholder-{approval.request_id}",
                case_id=f"review-case-{approval.request_id}",
                actor="pending",
                decision="pending",
                rationale="Awaiting operator decision.",
                evidence_refs=list(approval.relevant_evidence),
            )
            cases.append(
                HumanReviewCase(
                    version="1.0",
                    case_id=f"review-case-{approval.request_id}",
                    task_id=approval.task_id,
                    review_kind="runtime_approval",
                    status=approval.status,
                    summary=approval.action_summary or approval.reason,
                    assignee="approver",
                    evidence_refs=list(approval.relevant_evidence),
                    decisions=[decision],
                )
            )
        tasks = [task_id] if task_id else [str(item["task_id"]) for item in self.repository.list_tasks()]
        for current_task_id in tasks:
            report = self.repository.load_latest_validation_report(current_task_id)
            if report is None or report.status not in {"blocked", "failed"}:
                continue
            cases.append(
                HumanReviewCase(
                    version="1.0",
                    case_id=f"review-case-validation-{report.report_id}",
                    task_id=current_task_id,
                    review_kind="evidence_review",
                    status="pending",
                    summary="Validation report requires human review before trusted publication.",
                    assignee="reviewer",
                    evidence_refs=list(report.evidence_refs),
                    decisions=[],
                )
            )
        for case in cases:
            self._save_model("trusted_human_review_case", case.case_id, case.task_id, case.created_at.isoformat(), case)
        return cases

    def _benchmark_summary(self) -> BenchmarkSummaryView:
        suites: list[dict[str, Any]] = []
        latest_runs: list[dict[str, Any]] = []
        repro_runs: list[dict[str, Any]] = []
        candidates = self.repository.list_evolution_candidates()
        for candidate in candidates:
            suite = BenchmarkSuite(
                version="1.0",
                suite_id=f"benchmark-suite-{candidate.candidate_id}",
                title=candidate.target_component,
                description=candidate.hypothesis,
                benchmark_kind=candidate.candidate_type,
            )
            suites.append(suite.to_dict())
            for evaluation in self.repository.list_evaluation_runs(candidate.candidate_id):
                latest_runs.append(
                    BenchmarkRun(
                        version="1.0",
                        run_id=evaluation.run_id,
                        suite_id=suite.suite_id,
                        case_id=evaluation.suite_name,
                        task_id="",
                        status=evaluation.status,
                        score=float(evaluation.metrics.get("gain", evaluation.metrics.get("score", 0.0))),
                        summary=f"Evaluation suite {evaluation.suite_name}",
                        created_at=evaluation.completed_at,
                    ).to_dict()
                )
            for canary in self.repository.list_canary_runs(candidate.candidate_id):
                repro_runs.append(
                    ReproEvalRun(
                        version="1.0",
                        repro_run_id=f"repro-{canary.run_id}",
                        task_id="",
                        status=canary.status,
                        summary=f"Canary scope {canary.scope}",
                        created_at=canary.completed_at,
                    ).to_dict()
                )
        if not suites:
            suites.append(
                BenchmarkSuite(
                    version="1.0",
                    suite_id="benchmark-suite-runtime-health",
                    title="Runtime trust baseline",
                    description="No explicit evolution candidates yet; trusted-runtime baseline is active.",
                    benchmark_kind="baseline",
                ).to_dict()
            )
        summary = BenchmarkSummaryView(
            version="1.0",
            summary_id=f"benchmark-summary-{uuid4().hex[:10]}",
            suites=suites,
            latest_runs=sorted(latest_runs, key=lambda item: item.get("created_at", ""), reverse=True),
            repro_runs=sorted(repro_runs, key=lambda item: item.get("created_at", ""), reverse=True),
        )
        self._save_model("trusted_benchmark_summary", summary.summary_id, "global", summary.created_at.isoformat(), summary)
        return summary

    def _ensure_task_collaboration_binding(self, task_id: str) -> TaskCollaborationBinding:
        existing = self._list_models("trusted_task_collaboration", TaskCollaborationBinding, scope_key=task_id)
        if existing:
            return existing[0]
        pending = self.repository.list_approval_requests(task_id=task_id, status="pending")
        owner = self._default_actor_email()
        binding = TaskCollaborationBinding(
            version="1.0",
            binding_id=f"task-collaboration-{task_id}",
            task_id=task_id,
            owner=owner,
            reviewer="reviewer@example.com" if any(role.role_name == "reviewer" for role in self.list_user_role_bindings()) else owner,
            operators=[owner],
            watchers=[user.email for user in self.list_user_accounts() if user.email != owner][:3],
            approval_assignee="approver" if pending else "",
            blocked_by="approval" if pending else "",
            waiting_for="human review" if pending else "",
            recent_activity=[f"{task_id} currently in {self.api.task_status(task_id)['status']}"],
        )
        self._save_model("trusted_task_collaboration", binding.binding_id, task_id, binding.updated_at.isoformat(), binding)
        return binding

    def collaboration_summary(self) -> CollaborationSummaryView:
        task_bindings = [self._ensure_task_collaboration_binding(str(task["task_id"])).to_dict() for task in self.repository.list_tasks()]
        summary = CollaborationSummaryView(
            version="1.0",
            summary_id=f"collaboration-summary-{uuid4().hex[:10]}",
            users=[user.to_dict() for user in self.list_user_accounts()],
            role_bindings=[binding.to_dict() for binding in self.list_user_role_bindings()],
            sessions=[session.to_dict() for session in self.list_browser_sessions()],
            task_bindings=task_bindings,
            invitations=[item.to_dict() for item in self.list_workspace_invitations()],
        )
        self._save_model("trusted_collaboration_summary", summary.summary_id, "global", summary.created_at.isoformat(), summary)
        return summary

    def _task_timeline(self, task_id: str) -> TaskTimelineView:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        events: list[dict[str, Any]] = []
        request = dict(task.get("request", {}))
        created_at = str(request.get("created_at", ""))
        if created_at:
            events.append({"timestamp": created_at, "lane": "contract", "label": "Contract compiled", "kind": "contract"})
        plan = self.repository.load_plan(task_id)
        for node in ([] if plan is None else plan.nodes):
            events.append(
                {
                    "timestamp": created_at,
                    "lane": "plan",
                    "label": node.objective[:80],
                    "kind": node.node_category,
                    "status": node.status,
                }
            )
        for receipt in self.repository.list_execution_receipts(task_id):
            events.append(
                {
                    "timestamp": receipt.timestamp.isoformat(),
                    "lane": "execution",
                    "label": receipt.tool_used,
                    "kind": "execution_receipt",
                    "status": receipt.status,
                }
            )
        for checkpoint in self.repository.list_checkpoints(task_id):
            events.append(
                {
                    "timestamp": checkpoint.created_at.isoformat(),
                    "lane": "checkpoint",
                    "label": str(checkpoint.metadata.get("label", checkpoint.plan_node_id or checkpoint.checkpoint_id)),
                    "kind": "checkpoint",
                    "status": str(checkpoint.metadata.get("status", "recorded")),
                }
            )
        for approval in self.repository.list_approval_requests(task_id=task_id):
            events.append(
                {
                    "timestamp": approval.expiry_at.isoformat() if approval.expiry_at is not None else created_at,
                    "lane": "review",
                    "label": approval.action_summary or approval.reason,
                    "kind": "approval",
                    "status": approval.status,
                }
            )
        for usage in self.repository.list_provider_usage_records(task_id):
            events.append(
                {
                    "timestamp": usage.created_at.isoformat(),
                    "lane": "usage",
                    "label": usage.provider_name,
                    "kind": "provider_usage",
                    "status": usage.status,
                    "total_tokens": usage.total_tokens,
                }
            )
        events.sort(key=lambda item: item["timestamp"])
        timeline = TaskTimelineView(
            version="1.0",
            task_id=task_id,
            events=events,
            summary={
                "status": task["status"],
                "current_phase": task["current_phase"],
                "event_count": len(events),
                "approval_waits": sum(1 for item in events if item["kind"] == "approval" and item["status"] == "pending"),
            },
        )
        self._save_model("trusted_task_timeline", task_id, task_id, timeline.generated_at.isoformat(), timeline)
        return timeline

    def _evidence_trace(self, task_id: str) -> EvidenceTraceView:
        sources = self.repository.list_source_records(task_id)
        spans = self._synthesized_evidence_spans(task_id)
        claims = self.repository.load_claims(task_id)
        report = self.repository.load_latest_validation_report(task_id)
        trace_edges: list[dict[str, Any]] = []
        claim_dicts = [claim.to_dict() for claim in claims]
        for claim in claims:
            for ref in claim.evidence_refs:
                trace_edges.append({"from": ref, "to": claim.claim_id, "kind": "supports"})
        if report is not None:
            for ref in report.evidence_refs:
                trace_edges.append({"from": ref, "to": report.report_id, "kind": "validated_by"})
        trace = EvidenceTraceView(
            version="1.0",
            task_id=task_id,
            sources=[source.to_dict() for source in sources],
            spans=[span.to_dict() for span in spans],
            claims=claim_dicts,
            validations=[] if report is None else [report.to_dict()],
            trace_edges=trace_edges,
        )
        self._save_model("trusted_evidence_trace", task_id, task_id, trace.generated_at.isoformat(), trace)
        return trace

    def audit_overview(self) -> dict[str, Any]:
        trend = self._audit_trend()
        entries = self._audit_log_entries()
        return {
            "summary": trend.summary,
            "trend": trend.to_dict(),
            "items": [item.to_dict() for item in entries[-50:]],
            "bundles": [
                AuditEventBundle(
                    version="1.0",
                    bundle_id=f"audit-bundle-{task_id}",
                    task_id=task_id,
                    entries=[item for item in entries if item.task_id == task_id],
                ).to_dict()
                for task_id in sorted({item.task_id for item in entries})
            ],
        }

    def playbooks_overview(self) -> dict[str, Any]:
        items = [self._synthesized_playbook(str(task["task_id"])).to_dict() for task in self.repository.list_tasks()]
        return {"items": items, "review_cases": [item.to_dict() for item in self._review_cases()]}

    def benchmarks_overview(self) -> dict[str, Any]:
        summary = self._benchmark_summary()
        return {"summary": summary.to_dict()}

    def mcp_overview(self) -> dict[str, Any]:
        builtin_server = MCPServerRecord(
            version="1.0",
            server_id="mcp-server-ceos-runtime",
            display_name="CEOS Trusted Runtime",
            transport="in-process",
            endpoint="ceos://runtime",
            direction="server",
            enabled=True,
            status="ready",
        )
        self._save_model("trusted_mcp_server", builtin_server.server_id, builtin_server.direction, builtin_server.created_at.isoformat(), builtin_server)
        builtin_tools = [
            MCPToolRecord(version="1.0", tool_id="mcp-tool-task-inspection", server_id=builtin_server.server_id, tool_name="task_inspection", display_name="Task Inspection", description="Read-only task inspection.", permission_mode="read-only", schema_ref="contract-input"),
            MCPToolRecord(version="1.0", tool_id="mcp-tool-evidence-query", server_id=builtin_server.server_id, tool_name="evidence_query", display_name="Evidence Query", description="Query evidence traces and source spans.", permission_mode="read-only", schema_ref="evidence-source"),
            MCPToolRecord(version="1.0", tool_id="mcp-tool-audit-query", server_id=builtin_server.server_id, tool_name="audit_log_query", display_name="Audit Log Query", description="Query append-only audit events.", permission_mode="read-only", schema_ref="audit-log-entry"),
            MCPToolRecord(version="1.0", tool_id="mcp-tool-benchmark-query", server_id=builtin_server.server_id, tool_name="benchmark_query", display_name="Benchmark Query", description="Read benchmark and repro-eval state.", permission_mode="read-only", schema_ref="benchmark-run"),
            MCPToolRecord(version="1.0", tool_id="mcp-tool-playbook-query", server_id=builtin_server.server_id, tool_name="playbook_query", display_name="Playbook Query", description="Inspect trusted playbooks.", permission_mode="read-only", schema_ref="playbook-record"),
            MCPToolRecord(version="1.0", tool_id="mcp-tool-governed-action", server_id=builtin_server.server_id, tool_name="governed_action_submission", display_name="Governed Action Submission", description="Submit a governed action through the control plane.", permission_mode="approval-gated", schema_ref="mcp-tool-record"),
        ]
        for tool in builtin_tools:
            self._save_model("trusted_mcp_tool", tool.tool_id, tool.server_id, tool.created_at.isoformat(), tool)
        return {
            "schema_registry": self.schema_registry(),
            "server_surface": {
                "server": builtin_server.to_dict(),
                "tools": [tool.to_dict() for tool in builtin_tools],
            },
            "connected_servers": [item.to_dict() for item in self._list_models("trusted_mcp_server", MCPServerRecord) if item.server_id != builtin_server.server_id],
            "recent_invocations": [item.to_dict() for item in self._list_models("trusted_mcp_invocation", MCPInvocationRecord)][-20:],
            "permission_decisions": [item.to_dict() for item in self._list_models("trusted_mcp_permission", MCPPermissionDecision)][-20:],
        }

    def register_mcp_server(self, payload: dict[str, Any]) -> dict[str, Any]:
        record = MCPServerRecord(
            version="1.0",
            server_id=str(payload.get("server_id") or f"mcp-server-{uuid4().hex[:10]}"),
            display_name=str(payload.get("display_name", "MCP Server")),
            transport=str(payload.get("transport", "stdio")),
            endpoint=str(payload.get("endpoint", "")),
            direction=str(payload.get("direction", "client")),
            enabled=bool(payload.get("enabled", True)),
            status=str(payload.get("status", "configured")),
            updated_at=utc_now(),
        )
        self._save_model("trusted_mcp_server", record.server_id, record.direction, (record.updated_at or record.created_at).isoformat(), record)
        return {"server": record.to_dict()}

    def register_mcp_tool(self, server_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = MCPToolRecord(
            version="1.0",
            tool_id=str(payload.get("tool_id") or f"mcp-tool-{uuid4().hex[:10]}"),
            server_id=server_id,
            tool_name=str(payload.get("tool_name", "tool")),
            display_name=str(payload.get("display_name", payload.get("tool_name", "tool"))),
            description=str(payload.get("description", "")),
            permission_mode=str(payload.get("permission_mode", "read-only")),
            schema_ref=str(payload.get("schema_ref", "")),
        )
        self._save_model("trusted_mcp_tool", record.tool_id, server_id, record.created_at.isoformat(), record)
        return {"tool": record.to_dict()}

    def invoke_mcp_tool(self, server_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        tool_name = str(payload.get("tool_name", "tool"))
        actor = str(payload.get("actor", self._default_actor_email()))
        task_id = str(payload.get("task_id", ""))
        arguments = dict(payload.get("arguments", {}))
        invocation = MCPInvocationRecord(
            version="1.0",
            invocation_id=f"mcp-invocation-{uuid4().hex[:10]}",
            server_id=server_id,
            task_id=task_id,
            tool_name=tool_name,
            actor=actor,
            status="recorded",
            arguments=arguments,
            result_summary=f"Recorded invocation for {tool_name}",
            approval_required=tool_name in {"governed_action_submission"},
        )
        permission = MCPPermissionDecision(
            version="1.0",
            decision_id=f"mcp-permission-{uuid4().hex[:10]}",
            invocation_id=invocation.invocation_id,
            actor=actor,
            decision="approval_required" if invocation.approval_required else "allowed",
            rationale="Sensitive or policy-bound MCP actions remain governed." if invocation.approval_required else "Read-only MCP action allowed.",
        )
        self._save_model("trusted_mcp_invocation", invocation.invocation_id, server_id, invocation.created_at.isoformat(), invocation)
        self._save_model("trusted_mcp_permission", permission.decision_id, invocation.invocation_id, permission.created_at.isoformat(), permission)
        if task_id:
            binding = self._ensure_task_collaboration_binding(task_id)
            self._save_model("trusted_task_collaboration", binding.binding_id, task_id, utc_now().isoformat(), binding)
        return {"invocation": invocation.to_dict(), "permission": permission.to_dict()}

    def dashboard_summary(self) -> dict[str, Any]:
        system = self.api.system_report()
        usage = self.usage_summary(window="24h")
        audit = self.audit_overview()
        benchmark_summary = self.benchmarks_overview()["summary"]
        collaboration = self.collaboration_summary()
        recent_tasks = []
        for task in self.repository.list_tasks()[:8]:
            task_detail = self.repository.get_task(str(task["task_id"]))
            recent_tasks.append(
                {
                    "task_id": str(task["task_id"]),
                    "status": task["status"],
                    "current_phase": task["current_phase"],
                    "latest_checkpoint_id": task["latest_checkpoint_id"],
                    "goal": "" if task_detail is None else str(task_detail["request"].get("goal", "")),
                    "blocked_reason": "approval pending" if task["status"] == "awaiting_approval" else "",
                }
            )
        approvals = [item.to_dict() for item in self.repository.list_approval_requests(status="pending")]
        maintenance = self.api.maintenance_report()
        maintenance_report = maintenance.get("report", {})
        return {
            "system": system,
            "recent_tasks": recent_tasks,
            "approvals": approvals,
            "maintenance": maintenance,
            "usage": usage,
            "audit": audit["summary"],
            "benchmarks": benchmark_summary,
            "collaboration": {
                "user_count": len(collaboration.users),
                "session_count": len(collaboration.sessions),
                "task_binding_count": len(collaboration.task_bindings),
            },
            "health_badges": {
                "setup_required": not self.has_admin_account(),
                "provider_fallback": any(int(item.get("fallback_count", 0)) > 0 for item in usage["tasks"]),
                "maintenance_incidents": len(maintenance_report.get("incidents", [])),
            },
        }

    def task_cockpit(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        return {
            "task": task,
            "status": self.api.task_status(task_id),
            "handoff": self.api.handoff_packet_for_task(task_id),
            "checkpoints": self.api.checkpoints(task_id),
            "open_questions": self.api.open_questions(task_id),
            "next_actions": self.api.next_actions(task_id),
            "approvals": [item.to_dict() for item in self.api.approval_inbox(task_id=task_id)],
            "memory": self.api.memory_kernel_state(task_id),
            "memory_scopes": self.api.memory_scope_state(task_id),
            "timeline": self._task_timeline(task_id).to_dict(),
            "evidence_trace": self._evidence_trace(task_id).to_dict(),
            "playbook": self._synthesized_playbook(task_id).to_dict(),
            "review_cases": [item.to_dict() for item in self._review_cases(task_id)],
            "collaboration": self.api.task_collaboration(task_id),
            "strategy": self.api.strategy_state(task_id),
            "usage": self.task_usage_summary(task_id),
            "software": self.api.software_action_receipts(task_id=task_id, with_replay_diagnostics=True),
            "replay": self.api.trace_bundle(task_id),
        }

    def memory_overview(self) -> dict[str, Any]:
        tasks = self.repository.list_tasks()
        task_cards = []
        for task in tasks[:8]:
            task_id = str(task["task_id"])
            kernel = self.api.memory_kernel_state(task_id)
            task_cards.append(
                {
                    "task_id": task_id,
                    "timeline_view": kernel["timeline_view"],
                    "project_state_view": kernel["project_state_view"],
                    "maintenance_mode": self.api.memory_maintenance_mode(task_id),
                }
            )
        return {"items": task_cards}

    def software_overview(self) -> dict[str, Any]:
        harnesses = self.api.list_cli_anything_harnesses()
        return {
            "harnesses": [item.to_dict() for item in harnesses],
            "report": self.api.software_control_report(),
            "failure_clusters": self.api.software_failure_clusters()["items"],
            "recovery_hints": self.api.software_recovery_hints()["items"],
        }

    def maintenance_overview(self) -> dict[str, Any]:
        tasks = self.repository.list_tasks()
        task_payloads = []
        for task in tasks[:8]:
            task_id = str(task["task_id"])
            task_payloads.append(
                {
                    "task_id": task_id,
                    "mode": self.api.memory_maintenance_mode(task_id),
                    "incidents": self.api.memory_maintenance_incidents(task_id)["items"],
                    "recommendations": self.api.memory_maintenance_recommendation(task_id)["recommendation"],
                    "daemon": self.api.maintenance_daemon_state(task_id),
                }
            )
        return {"items": task_payloads}

    def approvals_inbox(self) -> dict[str, Any]:
        requests = [item.to_dict() for item in self.repository.list_approval_requests(status="pending")]
        return {"items": requests}

    def decide_approval(self, *, request_id: str, approver: str, status: str, rationale: str) -> dict[str, Any]:
        decision = self.api.decide_approval(
            request_id=request_id,
            approver=approver,
            status=status,
            rationale=rationale,
        )
        return decision.to_dict()

    def doctor_report(self) -> dict[str, Any]:
        startup = self.api.startup_validation()
        system = self.api.system_report()
        config = self.config_effective()
        provider_check = self.test_provider_connection()
        audit = self.audit_overview()
        benchmarks = self.benchmarks_overview()["summary"]
        frontend_dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
        frontend_index = frontend_dist / "index.html"
        frontend_assets = frontend_dist / "assets"
        frontend_status = "ready" if frontend_index.exists() else "missing-build"
        return {
            "startup": startup,
            "system": system["summary"],
            "config": config,
            "provider_check": provider_check,
            "admin_exists": self.has_admin_account(),
            "setup_required": not self.has_admin_account(),
            "audit_ledger": {
                "status": "healthy" if audit["summary"]["total_events"] > 0 else "empty",
                "event_count": audit["summary"]["total_events"],
            },
            "benchmark_reproducibility": {
                "status": "ready" if benchmarks["suites"] else "baseline-only",
                "suite_count": len(benchmarks["suites"]),
                "run_count": len(benchmarks["latest_runs"]),
                "repro_run_count": len(benchmarks["repro_runs"]),
            },
            "oidc_readiness": {
                "configured_provider_count": len(self.list_oidc_provider_configs()),
                "status": "configured" if self.list_oidc_provider_configs() else "optional-not-configured",
            },
            "frontend": {
                "status": frontend_status,
                "dist_path": str(frontend_dist),
                "index_present": frontend_index.exists(),
                "assets_present": frontend_assets.exists(),
                "recommended_action": None
                if frontend_index.exists()
                else "Run ./scripts/install.sh again or build the frontend with `cd frontend && npm install && npm run build`.",
            },
            "oidc_providers": [item.to_dict() for item in self.list_oidc_provider_configs()],
        }

    def event_stream_payloads(self) -> list[tuple[str, dict[str, Any]]]:
        return [
            ("dashboard", self.dashboard_summary()),
            ("usage", self.usage_summary(window="24h")),
            ("maintenance", self.maintenance_overview()),
            ("approvals", self.approvals_inbox()),
            ("audit", self.audit_overview()),
            ("benchmarks", self.benchmarks_overview()),
        ]
