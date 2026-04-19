from datetime import UTC, datetime, timedelta
from pathlib import Path

from contract_evidence_os.runtime.auth import AuthManager
from contract_evidence_os.runtime.provider_health import ProviderAvailabilityPolicy
from contract_evidence_os.runtime.provider_pool import ProviderPoolManager
from contract_evidence_os.storage.repository import SQLiteRepository


def _now() -> datetime:
    return datetime(2026, 4, 17, 0, 0, tzinfo=UTC)


def test_provider_pool_manager_balances_for_reservations_and_fairness(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    repository.save_provider_availability_policy(
        ProviderAvailabilityPolicy(
            version="1.0",
            policy_id="provider-policy-openai",
            provider_name="openai_live",
            failure_threshold=3,
            cooldown_seconds=30,
            rate_limit_window_seconds=60,
            max_requests_per_window=20,
            created_at=_now(),
        )
    )
    repository.save_provider_availability_policy(
        ProviderAvailabilityPolicy(
            version="1.0",
            policy_id="provider-policy-anthropic",
            provider_name="anthropic_live",
            failure_threshold=3,
            cooldown_seconds=30,
            rate_limit_window_seconds=60,
            max_requests_per_window=20,
            created_at=_now(),
        )
    )
    pool = ProviderPoolManager(repository=repository)
    pool.register_capacity("openai_live", max_parallel=2, reservation_slots={"verification": 1, "recovery": 1})
    pool.register_capacity("anthropic_live", max_parallel=2, reservation_slots={"verification": 0, "recovery": 0})

    pool.reserve(
        provider_name="openai_live",
        reservation_type="verification",
        task_id="task-verify",
        worker_id="worker-1",
        expires_at=_now() + timedelta(minutes=5),
    )

    build_decision = pool.balance(
        candidate_providers=["openai_live", "anthropic_live"],
        task_id="task-build",
        worker_id="worker-2",
        workload="build",
        risk_level="low",
        now=_now(),
    )
    assert build_decision.chosen_provider == "anthropic_live"

    verify_decision = pool.balance(
        candidate_providers=["openai_live", "anthropic_live"],
        task_id="task-verify",
        worker_id="worker-1",
        workload="verification",
        risk_level="high",
        now=_now(),
    )
    assert verify_decision.chosen_provider == "openai_live"
    assert verify_decision.reservation_applied is True
    assert pool.fairness_snapshot(now=_now())


def test_auth_manager_enforces_scopes_revocation_and_replay_protection(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    auth = AuthManager(repository=repository)

    viewer_credential, viewer_token = auth.issue_credential(
        principal_name="viewer",
        principal_type="operator",
        scopes=["viewer"],
        expires_at=_now() + timedelta(hours=1),
    )
    admin_credential, admin_token = auth.issue_credential(
        principal_name="admin",
        principal_type="operator",
        scopes=["viewer", "runtime-admin", "policy-admin", "approver"],
        expires_at=_now() + timedelta(hours=1),
    )

    viewer_session = auth.authenticate(viewer_token, request_id="req-view-001", now=_now())
    assert auth.authorize(viewer_session, required_scopes=["viewer"], action="view_queue").allowed is True
    assert auth.authorize(viewer_session, required_scopes=["runtime-admin"], action="set_drain_mode").allowed is False

    admin_session = auth.authenticate(admin_token, request_id="req-admin-001", now=_now())
    first = auth.record_request(
        session=admin_session,
        request_id="req-admin-001",
        nonce="nonce-001",
        idempotency_key="idem-001",
        action="set_drain_mode",
        sensitive=True,
        now=_now(),
    )
    assert first.accepted is True

    replay = auth.record_request(
        session=admin_session,
        request_id="req-admin-001",
        nonce="nonce-001",
        idempotency_key="idem-001",
        action="set_drain_mode",
        sensitive=True,
        now=_now() + timedelta(seconds=1),
    )
    assert replay.accepted is False

    auth.revoke_credential(admin_credential.credential_id, reason="rotation", revoked_at=_now() + timedelta(seconds=2))
    revoked = auth.authenticate(admin_token, request_id="req-admin-002", now=_now() + timedelta(seconds=3))
    assert revoked is None


def test_auth_manager_issues_service_credentials_and_records_rotation(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "ceos.sqlite3")
    auth = AuthManager(repository=repository)

    credential, token = auth.issue_service_credential(
        service_name="dispatcher-1",
        service_role="dispatcher",
        scopes=["worker-service", "runtime-admin"],
        allowed_hosts=["host-a"],
        expires_at=_now() + timedelta(hours=1),
    )
    session = auth.authenticate(token, request_id="req-service-001", now=_now())
    assert session is not None
    assert repository.list_service_principals()
    assert repository.list_service_credentials()

    rotated, rotated_token = auth.rotate_credential(
        credential.credential_id,
        reason="service rotation",
        expires_at=_now() + timedelta(hours=2),
    )
    assert rotated is not None
    assert rotated.credential_id != credential.credential_id
    assert rotated_token
    assert repository.list_credential_rotation_records(credential.credential_id)
