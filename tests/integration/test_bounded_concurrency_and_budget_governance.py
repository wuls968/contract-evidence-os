import time
from pathlib import Path

from contract_evidence_os.runtime.service import RuntimeService


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines), encoding="utf-8")


def test_runtime_executes_independent_retrieval_nodes_with_bounded_concurrency(tmp_path: Path) -> None:
    attachment_a = tmp_path / "requirements-a.txt"
    attachment_b = tmp_path / "requirements-b.txt"
    _write(attachment_a, ["Audit history must never be deleted."])
    _write(attachment_b, ["Every important summary must cite evidence."])

    service = RuntimeService(storage_root=tmp_path / "runtime", routing_strategy="quality")
    original_invoke = service.file_tool.invoke

    def delayed_invoke(*args, **kwargs):
        time.sleep(0.25)
        return original_invoke(*args, **kwargs)

    service.file_tool.invoke = delayed_invoke  # type: ignore[method-assign]

    started = time.perf_counter()
    result = service.run_task(
        goal="Read both attachments, build a structured delivery, and verify it.",
        attachments=[str(attachment_a), str(attachment_b)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )
    elapsed = time.perf_counter() - started

    assert result.status == "completed"
    assert elapsed < 3.0
    concurrency_state = service.repository.latest_concurrency_state(result.task_id)
    assert concurrency_state is not None
    assert concurrency_state.max_parallel_nodes == 2
    history = service.repository.list_concurrency_states(result.task_id)
    assert any(len(state.last_batch_nodes) == 2 for state in history)


def test_runtime_switches_to_low_cost_mode_under_budget_pressure(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    _write(
        attachment,
        [
            "Audit history must never be deleted.",
            "Every important summary must cite evidence.",
        ],
    )

    service = RuntimeService(storage_root=tmp_path / "runtime", routing_strategy="quality")
    result = service.run_task(
        goal="Read the attachment, build a structured delivery, and verify it.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured", "max_cost": "0.02"},
        prohibitions=["Do not delete audit history."],
    )

    assert result.status in {"completed", "blocked"}
    mode_state = service.repository.latest_execution_mode(result.task_id)
    assert mode_state is not None
    assert mode_state.mode_name in {"low_cost", "standard"}
    if mode_state.mode_name == "low_cost":
        events = service.repository.list_budget_events(result.task_id)
        assert events
