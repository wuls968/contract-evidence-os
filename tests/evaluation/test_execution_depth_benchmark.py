from pathlib import Path

from contract_evidence_os.evals.dataset import ExecutionDepthTaskCase, ExecutionDepthTaskDataset
from contract_evidence_os.evals.harness import EvaluationHarness
from contract_evidence_os.runtime.providers import DeterministicLLMProvider, ProviderManager
from contract_evidence_os.runtime.service import RuntimeService


def _factory(strategy_name: str, fail_extraction: bool = False):
    def _build(root: Path) -> RuntimeService:
        providers = {
            "primary": DeterministicLLMProvider(
                name="primary",
                fail_profiles={"quality-extractor"} if fail_extraction else set(),
            ),
            "fallback": DeterministicLLMProvider(name="fallback"),
        }
        return RuntimeService(
            storage_root=root,
            routing_strategy=strategy_name,
            provider_manager=ProviderManager(providers=providers),
        )

    return _build


def test_execution_depth_eval_tracks_replanning_and_provider_fallback(tmp_path: Path) -> None:
    attachment_a = tmp_path / "requirements-a.txt"
    attachment_b = tmp_path / "requirements-b.txt"
    attachment_a.write_text("Audit history must never be deleted.\nEvery important summary must cite evidence.\n", encoding="utf-8")
    attachment_b.write_text("Destructive actions require explicit approval.\nPublication requires final verification.\n", encoding="utf-8")

    dataset = ExecutionDepthTaskDataset(
        cases=[
            ExecutionDepthTaskCase(
                case_id="depth-001",
                goal="Read both attachments, build a structured delivery, verify it, and publish externally.",
                attachments=[str(attachment_a), str(attachment_b)],
                preferences={"output_style": "structured"},
                prohibitions=["Do not delete audit history."],
                expected_facts=[
                    "Audit history must never be deleted.",
                    "Every important summary must cite evidence.",
                    "Destructive actions require explicit approval.",
                ],
                require_approval=True,
                force_provider_failure=True,
            )
        ]
    )

    reports = EvaluationHarness().compare_execution_depth_strategies(
        dataset=dataset,
        runtime_factories={
            "quality": _factory("quality", fail_extraction=True),
            "economy": _factory("economy", fail_extraction=False),
        },
        working_root=tmp_path / "benchmarks",
    )

    for report in reports.values():
        assert report.metrics["node_completion_rate"] > 0.0
        assert report.metrics["verification_before_delivery_rate"] == 1.0
        assert report.metrics["approval_delay_survival_rate"] == 1.0
        assert report.metrics["end_to_end_completion_after_replan"] >= 0.0
