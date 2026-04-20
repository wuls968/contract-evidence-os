"""Query and trusted-read-model behavior for AMOS memory."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from contract_evidence_os.base import utc_now
from contract_evidence_os.memory._base import MemorySubservice
from contract_evidence_os.memory.common import safe_memory_text, tokenize_memory_text, truncate_memory_text
from contract_evidence_os.memory.models import (
    DurativeMemoryRecord,
    MatrixAssociationPointer,
    MemoryDashboardItem,
    MemoryDeletionRun,
    MemoryEvidencePack,
    MemoryHardPurgeRun,
    MemoryProjectStateView,
    MemorySelectivePurgeRun,
    MemoryTimelineSegment,
    MemoryTimelineView,
    MemoryTombstoneRecord,
    ProceduralPattern,
    TemporalSemanticFact,
)


class MemoryQueryService(MemorySubservice):
    """Own browser and runtime-facing memory query surfaces."""

    def timeline_view(
        self,
        *,
        scope_key: str,
        subject: str | None = None,
        predicate: str | None = None,
    ) -> MemoryTimelineView:
        segments = self.list_memory_timeline_segments(scope_key=scope_key)
        if (subject is not None or predicate is not None) or not segments:
            if subject is not None or predicate is not None:
                segments = self.reconstruct_timeline(scope_key=scope_key, subject=subject, predicate=predicate)
            else:
                facts = self.list_temporal_semantic_facts(scope_key=scope_key)
                if facts:
                    segments = self.reconstruct_timeline(
                        scope_key=scope_key,
                        subject=facts[0].subject,
                        predicate=facts[0].predicate,
                    )
        filtered = [
            segment
            for segment in segments
            if (subject is None or segment.subject == subject) and (predicate is None or segment.predicate == predicate)
        ]
        return MemoryTimelineView(
            version="1.0",
            view_id=f"memory-timeline-view-{scope_key}-{subject or 'any'}-{predicate or 'any'}",
            scope_key=scope_key,
            subject=subject,
            predicate=predicate,
            segment_ids=[segment.segment_id for segment in filtered],
            active_segment_ids=[segment.segment_id for segment in filtered if segment.transition_kind == "terminal" or segment.end_at is None],
            contradiction_count=sum(len(segment.contradicted_fact_ids) for segment in filtered),
            generated_at=utc_now(),
        )

    def project_state_view(self, *, scope_key: str, subject: str = "user") -> MemoryProjectStateView:
        snapshot = self.reconstruct_project_state(scope_key=scope_key, subject=subject)
        return MemoryProjectStateView(
            version="1.0",
            view_id=f"memory-project-state-view-{scope_key}-{subject}",
            scope_key=scope_key,
            subject=subject,
            snapshot_id=snapshot.snapshot_id,
            summary=snapshot.summary,
            active_states=list(snapshot.active_states),
            contradiction_count=snapshot.contradiction_count,
            generated_at=utc_now(),
        )

    def list_memory_deletion_runs(self, *, scope_key: str | None = None) -> list[MemoryDeletionRun]:
        records = list(self.deletion_runs.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_deletion_runs(scope_key=scope_key)
            for record in repository_records:
                self.deletion_runs[record.run_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.completed_at, reverse=True)

    def list_hard_purge_runs(self, *, scope_key: str | None = None) -> list[MemoryHardPurgeRun]:
        records = list(self.hard_purge_runs.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_hard_purge_runs(scope_key=scope_key)
            for record in repository_records:
                self.hard_purge_runs[record.run_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.completed_at, reverse=True)

    def list_selective_purge_runs(self, *, scope_key: str | None = None) -> list[MemorySelectivePurgeRun]:
        records = list(self.selective_purge_runs.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_selective_purge_runs(scope_key=scope_key)
            for record in repository_records:
                self.selective_purge_runs[record.run_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.completed_at, reverse=True)

    def list_memory_timeline_segments(self, *, scope_key: str | None = None) -> list[MemoryTimelineSegment]:
        records = list(self.timeline_segments.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_timeline_segments(scope_key=scope_key)
            for record in repository_records:
                self.timeline_segments[record.segment_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        tombstones_by_scope = self._tombstone_index(scope_key)
        records = [
            record
            for record in records
            if ("timeline_segment", record.segment_id) not in tombstones_by_scope.get(record.scope_key, set())
        ]
        return sorted(records, key=lambda item: (item.start_at or item.created_at, item.created_at))

    def list_temporal_semantic_facts(
        self,
        *,
        scope_key: str | None = None,
        task_id: str | None = None,
    ) -> list[TemporalSemanticFact]:
        records = list(self.semantic_facts.values())
        if self.repository is not None:
            repository_records = self.repository.list_temporal_semantic_facts(scope_key=scope_key, task_id=task_id)
            for record in repository_records:
                self.semantic_facts[record.fact_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        if task_id is not None:
            records = [record for record in records if record.task_id == task_id]
        tombstones_by_scope = self._tombstone_index(scope_key)
        records = [
            record
            for record in records
            if ("semantic_fact", record.fact_id) not in tombstones_by_scope.get(record.scope_key, set())
        ]
        return sorted(records, key=lambda item: item.observed_at, reverse=True)

    def list_durative_memories(
        self,
        *,
        scope_key: str | None = None,
        task_id: str | None = None,
    ) -> list[DurativeMemoryRecord]:
        records = list(self.durative_records.values())
        if self.repository is not None:
            repository_records = self.repository.list_durative_memories(scope_key=scope_key, task_id=task_id)
            for record in repository_records:
                self.durative_records[record.durative_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        if task_id is not None:
            records = [record for record in records if record.task_id == task_id]
        tombstones_by_scope = self._tombstone_index(scope_key)
        records = [
            record
            for record in records
            if ("durative_record", record.durative_id) not in tombstones_by_scope.get(record.scope_key, set())
        ]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def retrieve_evidence_pack(
        self,
        *,
        query: str,
        scope_key: str,
        at_time: datetime | None = None,
    ) -> MemoryEvidencePack:
        query_tokens = tokenize_memory_text(query)
        raw = self.list_raw_episodes(scope_key=scope_key)
        facts = self.list_temporal_semantic_facts(scope_key=scope_key)
        pointers = self._list_matrix_pointers(scope_key=scope_key)
        patterns = self._list_procedural_patterns(scope_key=scope_key)

        candidate_facts = [fact for fact in facts if self._fact_is_relevant_at_time(fact, at_time)]
        scored_facts = self._score_semantic_facts(query_tokens, candidate_facts)
        scored_raw = self._score_raw_episodes(query_tokens, raw)
        scored_pointers = self._score_pointers(query_tokens, pointers)
        scored_patterns = self._score_patterns(query_tokens, patterns)

        selected_facts = [item.fact_id for item in scored_facts[:3]]
        selected_raw = [item.episode_id for item in scored_raw[:3]]
        selected_pointers = [item.pointer_id for item in scored_pointers[:3]]
        selected_patterns = [item.pattern_id for item in scored_patterns[:2]]

        if not selected_facts and facts:
            selected_facts = [facts[0].fact_id]
        if not selected_raw and raw:
            selected_raw = [raw[0].episode_id]
        if not selected_pointers and pointers:
            selected_pointers = [pointers[0].pointer_id]

        discarded_conflicts = [
            fact.fact_id
            for fact in facts
            if fact.status != "active" and any(active.subject == fact.subject and active.predicate == fact.predicate for active in candidate_facts)
        ]
        temporal_notes: list[str] = []
        if at_time is not None:
            temporal_notes.append(f"retrieval filtered by validity at {at_time.isoformat()}")
        if discarded_conflicts:
            temporal_notes.append("superseded conflicting memories were retained but not treated as active facts")

        pack = MemoryEvidencePack(
            version="1.0",
            pack_id=f"memory-pack-{uuid4().hex[:10]}",
            query=query,
            scope_key=scope_key,
            raw_episode_ids=selected_raw,
            semantic_fact_ids=selected_facts,
            matrix_pointer_ids=selected_pointers,
            procedural_pattern_ids=selected_patterns,
            discarded_conflict_fact_ids=discarded_conflicts[:5],
            temporal_notes=temporal_notes,
            assembled_at=utc_now(),
        )
        self.evidence_packs[pack.pack_id] = pack
        if self.repository is not None:
            self.repository.save_memory_evidence_pack(pack)
        return pack

    def dashboard(self, *, scope_key: str) -> list[MemoryDashboardItem]:
        items: list[MemoryDashboardItem] = []
        for record in self.list_raw_episodes(scope_key=scope_key)[:5]:
            text = truncate_memory_text(safe_memory_text(record.content))
            items.append(
                MemoryDashboardItem(
                    version="1.0",
                    item_id=record.episode_id,
                    scope_key=scope_key,
                    source_kind="raw_episode",
                    summary=text,
                    status="active",
                    confidence=record.trust,
                    provenance=[record.source],
                    valid_from=record.event_time_start,
                    valid_until=record.event_time_end,
                    updated_at=record.created_at,
                )
            )
        for fact in self.list_temporal_semantic_facts(scope_key=scope_key)[:10]:
            items.append(
                MemoryDashboardItem(
                    version="1.0",
                    item_id=fact.fact_id,
                    scope_key=scope_key,
                    source_kind="semantic_fact",
                    summary=f"{fact.subject} {fact.predicate} {fact.object}",
                    status=fact.status,
                    confidence=fact.confidence,
                    provenance=list(fact.provenance),
                    valid_from=fact.valid_from,
                    valid_until=fact.valid_until,
                    updated_at=fact.observed_at,
                )
            )
        for pattern in self._list_procedural_patterns(scope_key=scope_key)[:5]:
            items.append(
                MemoryDashboardItem(
                    version="1.0",
                    item_id=pattern.pattern_id,
                    scope_key=scope_key,
                    source_kind="procedural_pattern",
                    summary=pattern.summary,
                    status=pattern.status,
                    confidence=pattern.confidence,
                    provenance=list(pattern.sources),
                    valid_from=pattern.created_at,
                    valid_until=None,
                    updated_at=pattern.created_at,
                )
            )
        items = sorted(items, key=lambda item: item.updated_at, reverse=True)
        if self.repository is not None:
            for item in items:
                self.repository.save_memory_dashboard_item(item)
        return items

    def list_memory_tombstones(self, *, scope_key: str | None = None) -> list[MemoryTombstoneRecord]:
        records = list(self.tombstones.values())
        if self.repository is not None:
            repository_records = self.repository.list_memory_tombstones(scope_key=scope_key)
            for record in repository_records:
                self.tombstones[record.tombstone_id] = record
            records = repository_records
        if scope_key is not None:
            records = [record for record in records if record.scope_key == scope_key]
        return sorted(records, key=lambda item: item.deleted_at, reverse=True)
