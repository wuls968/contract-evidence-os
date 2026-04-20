import json
import threading
import urllib.parse
import urllib.request
from pathlib import Path

from contract_evidence_os.api.operator import OperatorAPI
from contract_evidence_os.api.server import RemoteOperatorService
from contract_evidence_os.runtime.service import RuntimeService


def _request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, method=method, data=data)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Request-Id", f"req-{method.lower()}-{abs(hash(url)) % 100000}")
    request.add_header("X-Request-Nonce", f"nonce-{abs(hash(url)) % 100000}")
    request.add_header("X-Idempotency-Key", f"idem-{abs(hash(url)) % 100000}")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_operator_and_remote_service_expose_selective_purge_policy_state_and_cross_scope_timeline(tmp_path: Path) -> None:
    attachment = tmp_path / "requirements.txt"
    attachment.write_text("Audit history must never be deleted.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    result_a = service.run_task(
        goal="Read the attachment and summarize the mandatory constraints.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )
    result_b = service.run_task(
        goal="Read the attachment again and summarize the same constraints with stronger policy language.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not delete audit history."],
    )

    api = OperatorAPI(storage_root=root)
    api.memory_state(result_a.task_id)
    api.memory_evidence_pack(result_a.task_id, query="什么约束要求不能删除审计历史？")
    for task_id, state_object, when in (
        (result_a.task_id, "AMOS governance", "2026-04-15T12:00:00+00:00"),
        (result_b.task_id, "timeline recovery", "2026-04-17T12:00:00+00:00"),
    ):
        candidate = api.memory.create_candidate(
            task_id=task_id,
            scope_key=task_id,
            lane="semantic",
            summary=f"user working on {state_object}",
            content={
                "subject": "user",
                "predicate": "working_on",
                "object": state_object,
                "valid_from": when,
                "head": "goal",
            },
            sources=["episode-cross-scope"],
        )
        api.memory.govern_candidate(candidate.candidate_id)
        api.memory.consolidate_candidate(candidate.candidate_id)
    policy_state = api.memory_policy_state(result_a.task_id)
    assert "admission_policy" in policy_state
    assert "learning_state" in policy_state

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        selective = _request(
            "POST",
            f"{remote.base_url}/tasks/{result_a.task_id}/memory/selective-purge",
            "secret-token",
            {
                "actor": "runtime-admin",
                "reason": "clear derived memory artifacts only",
                "target_kinds": ["evidence_pack", "dashboard_item"],
            },
        )
        assert selective["purged_record_count"] >= 1

        query = urllib.parse.urlencode(
            {
                "scope_keys": f"{result_a.task_id},{result_b.task_id}",
                "subject": "user",
                "predicate": "working_on",
            }
        )
        timeline = _request(
            "GET",
            f"{remote.base_url}/memory/cross-scope-timeline?{query}",
            "secret-token",
        )
        assert timeline["segments"]
    finally:
        remote.shutdown()

    state_after = api.memory_state(result_a.task_id)
    assert state_after["semantic_facts"]
