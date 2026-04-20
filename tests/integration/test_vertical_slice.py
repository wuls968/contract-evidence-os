from pathlib import Path

from contract_evidence_os.runtime.service import RuntimeService


def test_runtime_executes_vertical_slice_with_evidence_and_audit(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text(
        "\n".join(
            [
                "Audit history must never be deleted.",
                "Every important summary must cite evidence.",
                "Destructive actions require explicit approval.",
            ]
        ),
        encoding="utf-8",
    )

    service = RuntimeService(storage_root=tmp_path / "runtime")
    result = service.run_task(
        goal="Read the attachment and summarize the mandatory constraints with evidence.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )

    assert result.status == "completed"
    assert result.contract.contract_id
    assert result.plan.nodes
    assert result.delivery["facts"]
    assert any("audit history" in fact["statement"].lower() for fact in result.delivery["facts"])
    assert result.validation_report.status == "passed"
    assert result.evidence_graph.nodes
    assert any(node.node_type == "source" for node in result.evidence_graph.nodes)
    assert result.audit_events
    assert result.receipts
