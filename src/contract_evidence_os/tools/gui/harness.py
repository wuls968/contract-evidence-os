"""Simulator-backed computer use harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from contract_evidence_os.audit.models import ExecutionReceipt
from contract_evidence_os.base import utc_now


@dataclass
class UIState:
    """Structured UI snapshot for simulator-backed computer use."""

    state_id: str
    elements: dict[str, dict[str, object]]


@dataclass
class ComputerUseHarness:
    """Capture structured UI state and require approval for risky actions."""

    states: dict[str, UIState] = field(default_factory=dict)

    def capture_state(self, elements: dict[str, dict[str, object]]) -> UIState:
        state = UIState(state_id=f"ui-{uuid4().hex[:10]}", elements=elements)
        self.states[state.state_id] = state
        return state

    def click(self, state_id: str, element_id: str, approved: bool = False) -> ExecutionReceipt:
        state = self.states[state_id]
        element = state.elements[element_id]
        risk = str(element.get("risk", "low"))
        if risk in {"high", "destructive"} and not approved:
            status = "blocked"
            output_summary = f"Click on {element_id} blocked pending approval"
        else:
            status = "success"
            output_summary = f"Clicked {element_id}"
        return ExecutionReceipt(
            version="1.0",
            receipt_id=f"receipt-{uuid4().hex[:10]}",
            contract_id="gui-contract",
            plan_node_id="gui-action",
            actor="ComputerUseHarness",
            tool_used="computer_use_harness",
            input_summary=f"click:{element_id}",
            output_summary=output_summary,
            artifacts=[state_id],
            evidence_refs=[],
            validation_refs=[],
            approval_refs=["explicit"] if approved else [],
            status=status,
            timestamp=utc_now(),
        )

    def compare_states(self, before: UIState, after: UIState) -> dict[str, list[str]]:
        before_keys = set(before.elements)
        after_keys = set(after.elements)
        return {
            "added": sorted(after_keys - before_keys),
            "removed": sorted(before_keys - after_keys),
            "unchanged": sorted(before_keys & after_keys),
        }
