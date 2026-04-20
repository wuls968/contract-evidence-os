from __future__ import annotations

from pathlib import Path

from contract_evidence_os.base import utc_now
from contract_evidence_os.memory.matrix import MemoryMatrix
from contract_evidence_os.memory.maintenance_service import MemoryMaintenanceService
from contract_evidence_os.memory.models import RawEpisodeRecord
from contract_evidence_os.memory.query_service import MemoryQueryService
from contract_evidence_os.storage.memory_store import SQLiteMemoryStore
from contract_evidence_os.storage.repository import SQLiteRepository


def _build_repository(tmp_path: Path) -> SQLiteRepository:
    root = tmp_path / "runtime"
    root.mkdir(parents=True, exist_ok=True)
    return SQLiteRepository(root / "state.db")


def test_repository_exposes_memory_store_and_delegates_memory_persistence(tmp_path: Path) -> None:
    repository = _build_repository(tmp_path)

    assert isinstance(repository.memory_store, SQLiteMemoryStore)

    episode = RawEpisodeRecord(
        version="1.0",
        episode_id="episode-phase2-raw",
        task_id="task-phase2",
        episode_type="interaction",
        actor="operator@example.com",
        scope_key="scope-phase2",
        project_id=None,
        source="phase2-test",
        consent="granted",
        content={"summary": "Trusted runtime raw episode"},
        trust=0.7,
        dialogue_time=utc_now(),
        event_time_start=utc_now(),
        event_time_end=None,
        created_at=utc_now(),
    )
    repository.save_raw_episode(episode)

    records = repository.list_raw_episodes(scope_key="scope-phase2")
    assert [item.episode_id for item in records] == ["episode-phase2-raw"]


def test_memory_matrix_exposes_query_and_maintenance_services(tmp_path: Path) -> None:
    repository = _build_repository(tmp_path)
    matrix = MemoryMatrix(repository=repository, artifact_root=tmp_path / "artifacts")

    assert isinstance(matrix.query_service, MemoryQueryService)
    assert isinstance(matrix.maintenance_service, MemoryMaintenanceService)

    timeline = matrix.timeline_view(scope_key="scope-phase2")
    assert timeline.scope_key == "scope-phase2"

    mode = matrix.maintenance_mode(scope_key="scope-phase2")
    assert mode["scope_key"] == "scope-phase2"
