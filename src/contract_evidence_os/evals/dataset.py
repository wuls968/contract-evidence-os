"""Golden evaluation datasets."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GoldenTaskCase:
    """One benchmarkable task case."""

    case_id: str
    goal: str
    attachments: list[str]
    preferences: dict[str, str]
    prohibitions: list[str]
    expected_facts: list[str]
    min_evidence_ref_count: int = 1


@dataclass
class GoldenTaskDataset:
    """Collection of golden task cases."""

    cases: list[GoldenTaskCase] = field(default_factory=list)


@dataclass
class LongHorizonTaskCase(GoldenTaskCase):
    """Benchmark case that spans multiple sessions and resumptions."""

    session_interrupts: list[str] = field(default_factory=list)
    require_approval: bool = False
    revision_after_interrupt: str | None = None
    revision_objective: str | None = None


@dataclass
class LongHorizonTaskDataset:
    """Collection of long-horizon benchmark cases."""

    cases: list[LongHorizonTaskCase] = field(default_factory=list)


@dataclass
class ExecutionDepthTaskCase(LongHorizonTaskCase):
    """Benchmark case that stresses multi-node execution depth."""

    force_provider_failure: bool = False
    require_replan: bool = True
    require_recovery_branch: bool = True


@dataclass
class ExecutionDepthTaskDataset:
    """Collection of execution-depth benchmark cases."""

    cases: list[ExecutionDepthTaskCase] = field(default_factory=list)


@dataclass
class OperationalTaskCase(ExecutionDepthTaskCase):
    """Benchmark case focused on production operations behavior."""

    require_concurrency: bool = False
    require_budget_mode: bool = False


@dataclass
class OperationalTaskDataset:
    """Collection of operational governance benchmark cases."""

    cases: list[OperationalTaskCase] = field(default_factory=list)


@dataclass
class SystemScaleTaskCase:
    """Benchmark case that exercises queueing, admission, and runtime pressure."""

    case_id: str
    tasks: list[dict[str, object]]
    simulate_provider_pressure: bool = False
    expect_defer_or_queue: bool = False


@dataclass
class SystemScaleTaskDataset:
    """Collection of system-scale queueing and pressure benchmark cases."""

    cases: list[SystemScaleTaskCase] = field(default_factory=list)


@dataclass
class MemoryBenchmarkCase(GoldenTaskCase):
    """Benchmark case for source-grounded memory retrieval and temporal reasoning."""

    expected_facts: list[str] = field(default_factory=list)
    query: str = ""
    expected_terms: list[str] = field(default_factory=list)


@dataclass
class MemoryBenchmarkDataset:
    """Collection of AMOS memory benchmark cases."""

    cases: list[MemoryBenchmarkCase] = field(default_factory=list)


@dataclass
class MemoryLifecycleBenchmarkCase(MemoryBenchmarkCase):
    """Benchmark case for deletion, consolidation, and rebuild behavior."""

    delete_after_run: bool = False
    require_consolidation: bool = False


@dataclass
class MemoryLifecycleBenchmarkDataset:
    """Collection of AMOS memory lifecycle benchmark cases."""

    cases: list[MemoryLifecycleBenchmarkCase] = field(default_factory=list)


@dataclass
class MemoryPolicyBenchmarkCase(MemoryLifecycleBenchmarkCase):
    """Benchmark case for poison-aware admission, purge, and timeline policy behavior."""

    risky_summary: str = ""


@dataclass
class MemoryPolicyBenchmarkDataset:
    """Collection of AMOS memory policy benchmark cases."""

    cases: list[MemoryPolicyBenchmarkCase] = field(default_factory=list)


@dataclass
class MemoryGovernanceBenchmarkCase(MemoryPolicyBenchmarkCase):
    """Benchmark case for learned admission, selective purge, and cross-scope governance."""

    second_goal: str | None = None


@dataclass
class MemoryGovernanceBenchmarkDataset:
    """Collection of AMOS memory governance benchmark cases."""

    cases: list[MemoryGovernanceBenchmarkCase] = field(default_factory=list)
