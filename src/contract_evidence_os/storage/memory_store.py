"""Memory-focused repository facade."""

from __future__ import annotations

from typing import Any

from contract_evidence_os.memory.models import (
    MemoryPromotionDecision,
    MemoryPromotionRecord,
    MemoryRecord,
    MemoryScopeRecord,
    RawEpisodeRecord,
    SummaryRecord,
    WorkingMemorySnapshot,
)
from contract_evidence_os.storage._base import SQLiteSubstore


class SQLiteMemoryStore(SQLiteSubstore):
    """Own decomposed memory persistence and expose the broader memory store boundary."""

    _OWNER_MEMORY_PREFIXES = (
        "save_memory_",
        "list_memory_",
        "load_memory_",
        "latest_memory_",
        "save_temporal_semantic_fact",
        "list_temporal_semantic_facts",
        "save_durative_memory",
        "list_durative_memories",
        "save_matrix_association_pointer",
        "list_matrix_association_pointers",
        "save_procedural_pattern",
        "list_procedural_patterns",
        "save_explicit_memory_record",
        "list_explicit_memory_records",
        "save_skill_capsule",
        "save_memory_lifecycle_trace",
        "list_memory_lifecycle_traces",
    )

    def __getattr__(self, name: str) -> Any:
        if name.startswith(self._OWNER_MEMORY_PREFIXES):
            return object.__getattribute__(self.owner, name)
        return super().__getattr__(name)

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
        rows = self.owner._fetchall(query, tuple(params))  # noqa: SLF001
        return [self.owner._model_from_row("memory_records", row, MemoryRecord) for row in rows]  # noqa: SLF001

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

    def save_memory_scope_record(self, record: MemoryScopeRecord) -> None:
        self._save_runtime_state_record(
            "memory_scope_record",
            record.record_id,
            record.scope_key,
            record.updated_at.isoformat(),
            record,
        )

    def list_memory_scope_records(self, *, scope_key: str | None = None) -> list[MemoryScopeRecord]:
        return self._list_runtime_state_records("memory_scope_record", MemoryScopeRecord, scope_key=scope_key)

    def load_memory_scope_record(self, record_id: str) -> MemoryScopeRecord | None:
        return self._load_runtime_state_record("memory_scope_record", record_id, MemoryScopeRecord)

    def save_memory_promotion_decision(self, record: MemoryPromotionDecision) -> None:
        self._save_runtime_state_record(
            "memory_promotion_decision",
            record.decision_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_memory_promotion_decisions(self, *, scope_key: str | None = None) -> list[MemoryPromotionDecision]:
        return self._list_runtime_state_records("memory_promotion_decision", MemoryPromotionDecision, scope_key=scope_key)

    def save_summary_record(self, record: SummaryRecord) -> None:
        self._save_runtime_state_record(
            "memory_summary_record",
            record.summary_id,
            record.scope_key,
            record.created_at.isoformat(),
            record,
        )

    def list_summary_records(self, *, scope_key: str | None = None) -> list[SummaryRecord]:
        return self._list_runtime_state_records("memory_summary_record", SummaryRecord, scope_key=scope_key)
