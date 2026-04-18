from pathlib import Path

from contract_evidence_os.runtime.service import RuntimeService


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines), encoding="utf-8")


def test_runtime_executes_persisted_multi_node_plan_and_scheduler_state(tmp_path: Path) -> None:
    attachment_a = tmp_path / "requirements-a.txt"
    attachment_b = tmp_path / "requirements-b.txt"
    _write(attachment_a, ["Audit history must never be deleted.", "Every important summary must cite evidence."])
    _write(attachment_b, ["Destructive actions require explicit approval.", "Publication requires final verification."])

    service = RuntimeService(storage_root=tmp_path / "runtime", routing_strategy="quality")
    result = service.run_task(
        goal="Read both attachments, build a structured delivery, verify it, and record learning.",
        attachments=[str(attachment_a), str(attachment_b)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )

    assert result.status == "completed"
    assert len(result.plan.nodes) >= 5
    assert {node.node_category for node in result.plan.nodes} >= {"research", "build", "verification", "memory_evolution"}

    receipts = service.repository.list_execution_receipts(result.task_id)
    assert {receipt.plan_node_id for receipt in receipts} >= {
        "node-retrieve-source-0",
        "node-extract-source-0",
        "node-build-delivery",
        "node-verify-delivery",
        "node-capture-learning",
    }

    scheduler_state = service.repository.latest_scheduler_state(result.task_id)
    assert scheduler_state is not None
    assert scheduler_state.status == "completed"


def test_runtime_replans_and_selects_recovery_branch_after_provider_failure(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    _write(
        attachment,
        [
            "Audit history must never be deleted.",
            "Every important summary must cite evidence.",
        ],
    )

    from contract_evidence_os.runtime.providers import DeterministicLLMProvider, ProviderManager

    service = RuntimeService(
        storage_root=tmp_path / "runtime",
        routing_strategy="quality",
        provider_manager=ProviderManager(
            providers={
                "primary": DeterministicLLMProvider(name="primary", fail_profiles={"quality-extractor"}),
            }
        ),
    )

    result = service.run_task(
        goal="Read the attachment, build a structured delivery, and verify it.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )

    assert result.status == "completed"

    revisions = service.repository.list_plan_revisions(result.task_id)
    branches = service.repository.list_execution_branches(result.task_id)
    assert revisions
    assert any(branch.status == "selected" for branch in branches)
    assert any("recovery" in node.node_category for node in result.plan.nodes)

    replay = service.replay_task(result.task_id)
    assert replay["plan_revisions"]
    assert replay["execution_branches"]
