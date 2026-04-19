import json
import threading
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


def test_operator_and_remote_service_expose_maintenance_workers_rollouts_and_resolution(tmp_path: Path) -> None:
    attachment = tmp_path / "notes.txt"
    attachment.write_text("AMOS should expose maintenance workers, rollouts, and incident resolution.\n", encoding="utf-8")
    root = tmp_path / "runtime"
    service = RuntimeService(storage_root=root, routing_strategy="quality")
    service.memory.shared_artifact_root = root / "shared-artifacts"
    result = service.run_task(
        goal="Read the attachment and summarize maintenance worker and rollout requirements.",
        attachments=[str(attachment)],
        preferences={"output_style": "structured"},
        prohibitions=["Do not erase audit lineage."],
    )
    service.memory.schedule_background_maintenance(
        scope_key=result.task_id,
        cadence_hours=24,
        actor="runtime-admin",
    )
    service.memory.register_maintenance_worker(worker_id="maint-a", host_id="host-a", actor="runtime-admin")
    service.memory.run_maintenance_worker_cycle(worker_id="maint-a")
    service.memory.train_maintenance_controller(scope_key=result.task_id)
    service.memory.run_maintenance_recommendation_canary(scope_key=result.task_id)
    promotion = service.memory.recommend_maintenance_policy_promotion(scope_key=result.task_id)

    api = OperatorAPI(storage_root=root)
    workers = api.memory_maintenance_workers(result.task_id)
    assert "items" in workers

    remote = RemoteOperatorService(storage_root=root, token="secret-token", host="127.0.0.1", port=0)
    thread = threading.Thread(target=remote.serve_forever, daemon=True)
    thread.start()
    try:
        applied = _request(
            "POST",
            f"{remote.base_url}/tasks/{result.task_id}/memory/maintenance-promotions/{promotion.recommendation_id}/apply",
            "secret-token",
            {"actor": "remote-operator", "reason": "apply maintenance controller rollout"},
        )
        assert "rollout_id" in applied

        rollouts = _request(
            "GET",
            f"{remote.base_url}/tasks/{result.task_id}/memory/maintenance-rollouts",
            "secret-token",
        )
        assert "items" in rollouts

        rolled_back = _request(
            "POST",
            f"{remote.base_url}/tasks/{result.task_id}/memory/maintenance-rollouts/{applied['rollout_id']}/rollback",
            "secret-token",
            {"actor": "remote-operator", "reason": "rollback maintenance controller rollout"},
        )
        assert rolled_back["action"] == "rollback"
    finally:
        remote.shutdown()
