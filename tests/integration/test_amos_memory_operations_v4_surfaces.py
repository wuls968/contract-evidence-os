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


def test_operator_and_remote_service_expose_memory_rebuild_loop_and_repair_apply_rollback(tmp_path: Path) -> None:
    attachment = tmp_path / "notes.txt"
    attachment.write_text("AMOS should support partial repair, canary repair, and rollback.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    result_a = service.run_task(
        goal="Read the attachment and summarize the memory recovery requirements.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not erase audit lineage."],
    )
    result_b = service.run_task(
        goal="Read the attachment and summarize the same recovery requirements with stronger contradiction handling.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not erase audit lineage."],
    )
    service.export_artifacts(result_a.task_id)

    api = OperatorAPI(storage_root=root)
    selective = api.selective_rebuild_memory(
        result_a.task_id,
        reason="repair only artifacts and project state",
        target_kinds=["artifact_file", "project_state_snapshot"],
    )
    assert selective["rebuilt_counts"]["artifact_file"] >= 1

    for task_id, state_object, when in (
        (result_a.task_id, "AMOS design", "2026-04-10T12:00:00+00:00"),
        (result_b.task_id, "policy tuning", "2026-04-15T12:00:00+00:00"),
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
            sources=["episode-cross-scope-v4"],
        )
        api.memory.govern_candidate(candidate.candidate_id)
        api.memory.consolidate_candidate(candidate.candidate_id)

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        loop = _request(
            "POST",
            f"{remote.base_url}/tasks/{result_a.task_id}/memory/operations-loop",
            "secret-token",
            {"reason": "nightly loop"},
        )
        assert loop["status"] == "completed"

        query = urllib.parse.urlencode(
            {
                "scope_keys": f"{result_a.task_id},{result_b.task_id}",
                "subject": "user",
                "predicate": "working_on",
            }
        )
        canary = _request(
            "POST",
            f"{remote.base_url}/memory/cross-scope-repairs/canary",
            "secret-token",
            {
                "scope_keys": [result_a.task_id, result_b.task_id],
                "subject": "user",
                "predicate": "working_on",
            },
        )
        assert canary["recommendation"] == "apply"

        apply_result = _request(
            "POST",
            f"{remote.base_url}/memory/cross-scope-repairs/{canary['repair_ids'][0]}/apply",
            "secret-token",
            {"actor": "remote-operator", "reason": "accept latest state"},
        )
        assert apply_result["action"] == "apply"

        rollback_result = _request(
            "POST",
            f"{remote.base_url}/memory/cross-scope-repairs/{canary['repair_ids'][0]}/rollback",
            "secret-token",
            {"actor": "remote-operator", "reason": "restore prior state"},
        )
        assert rollback_result["action"] == "rollback"
    finally:
        remote.shutdown()
