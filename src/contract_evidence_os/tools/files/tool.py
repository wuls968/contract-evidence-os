"""Local file retrieval tool."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.evidence.models import SourceRecord
from contract_evidence_os.tools.models import ToolInvocation, ToolResult, ToolSpec


@dataclass
class FileRetrievalTool:
    """Read a local file and emit typed source metadata."""

    spec: ToolSpec = field(
        default_factory=lambda: ToolSpec(
            version="1.0",
            tool_id="file-retrieval",
            name="file_retrieval",
            description="Read a local file with provenance capture.",
            input_schema={"type": "object", "required": ["path"]},
            output_schema={"type": "object", "required": ["content"]},
            risk_level="low",
            permission_requirements=["read"],
            retry_policy={"max_attempts": 1},
            timeout_policy={"seconds": 5},
            audit_hooks=["record_tool_invocation"],
            evidence_hooks=["emit_source_record"],
            validation_hooks=["check_file_exists"],
            mock_provider="in_memory_file_provider",
            simulator_provider="simulated_file_provider",
        )
    )

    def invoke(
        self,
        path: str,
        actor: str,
        task_id: str = "",
        plan_node_id: str = "",
        correlation_id: str = "",
    ) -> tuple[ToolInvocation, ToolResult, SourceRecord | None]:
        idempotency_key = f"file_retrieval:{actor}:{path}"
        correlation = correlation_id or f"{task_id}:{plan_node_id}:file_retrieval"
        invocation = ToolInvocation(
            version="1.0",
            invocation_id=f"invoke-{uuid4().hex[:10]}",
            tool_id=self.spec.tool_id,
            actor=actor,
            input_payload={"path": path},
            requested_at=utc_now(),
            task_id=task_id,
            plan_node_id=plan_node_id,
            correlation_id=correlation,
            idempotency_key=idempotency_key,
        )
        started_at = utc_now()
        target = Path(path)
        if not target.exists() or not target.is_file():
            result = ToolResult(
                version="1.0",
                invocation_id=invocation.invocation_id,
                tool_id=self.spec.tool_id,
                status="failed",
                output_payload={},
                error=f"missing file: {path}",
                started_at=started_at,
                completed_at=utc_now(),
                correlation_id=correlation,
                provenance={"locator": path, "actor": actor},
                confidence=1.0,
                provider_mode="live",
                deterministic=True,
                failure_classification="missing_input",
                suggested_follow_up_action="verify attachment path and retry",
            )
            return invocation, result, None

        content = target.read_text(encoding="utf-8")
        digest = sha256(content.encode("utf-8")).hexdigest()
        result = ToolResult(
            version="1.0",
            invocation_id=invocation.invocation_id,
            tool_id=self.spec.tool_id,
            status="success",
            output_payload={"content": content, "path": str(target)},
            error=None,
            started_at=started_at,
            completed_at=utc_now(),
            correlation_id=correlation,
            provenance={"locator": str(target), "content_hash": digest},
            confidence=0.95,
            provider_mode="live",
            deterministic=True,
            suggested_follow_up_action="extract grounded claims from the retrieved content",
            artifact_refs=[str(target)],
        )
        source = SourceRecord(
            version="1.0",
            source_id=f"source-{uuid4().hex[:10]}",
            source_type="file",
            locator=str(target),
            retrieved_at=utc_now(),
            credibility=0.95,
            time_relevance=1.0,
            content_hash=digest,
            snippet=content[:200],
        )
        return invocation, result, source

    def chunk_document(self, content: str, chunk_size: int = 200) -> list[str]:
        """Split a document into small replayable chunks."""

        return [content[index : index + chunk_size] for index in range(0, len(content), chunk_size)]

    def keyword_search(self, content: str, keywords: list[str]) -> list[str]:
        """Return lines that match any provided keyword."""

        normalized = [keyword.lower() for keyword in keywords]
        return [
            line
            for line in content.splitlines()
            if any(keyword in line.lower() for keyword in normalized)
        ]
