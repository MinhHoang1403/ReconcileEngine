from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.smartrecon_api.config import get_settings
from backend.smartrecon_api.db.database import get_db
from backend.smartrecon_api.db.models import ReconciliationRun, ReviewAction
from backend.smartrecon_api.main import app
from backend.smartrecon_api.schemas.reviews import ApproveReviewRequest
from backend.smartrecon_api.services.reviews import approve_review
from backend.smartrecon_api.services.runs import effective_result_path, result_to_payload
from backend.smartrecon_api.services.serialization import write_json
from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.statuses import Currency
from smartrecon.engine import ReconciliationResult, run_reconciliation
from smartrecon.ingest.mapping import default_demo_mapping
from smartrecon.ingest.normalization import normalize_bundle
from smartrecon.ingest.readers import read_source_bundle

DEMO_DIR = Path("data/demo/vn_synthetic_demo")


class ReviewSession:
    """Transaction-aware test double; PostgreSQL locking is verified in Docker acceptance."""

    def __init__(self, run: ReconciliationRun, *, fail_commit: bool = False) -> None:
        self.run = run
        self.fail_commit = fail_commit
        self.committed_revision = run.current_revision
        self.committed_actions: dict[str, ReviewAction] = {}
        self.staged: list[object] = []
        self.rollback_count = 0

    def scalar(self, statement: object):
        entity = statement.column_descriptions[0].get("entity")
        if entity is ReconciliationRun:
            return self.run
        if entity is ReviewAction:
            params = statement.compile().params
            key = next(
                (value for name, value in params.items() if "idempotency_key" in name),
                None,
            )
            return next(
                (action for action in self.committed_actions.values() if action.idempotency_key == key),
                None,
            )
        return None

    def get(self, model: type, identifier: str):
        if model is ReviewAction:
            return self.committed_actions.get(identifier)
        if model is ReconciliationRun and identifier == self.run.id:
            return self.run
        return None

    def add(self, value: object) -> None:
        self.staged.append(value)

    def commit(self) -> None:
        if self.fail_commit:
            raise RuntimeError("forced commit failure")
        for value in self.staged:
            if isinstance(value, ReviewAction):
                self.committed_actions[value.id] = value
        self.staged.clear()
        self.committed_revision = self.run.current_revision

    def rollback(self) -> None:
        self.rollback_count += 1
        self.staged.clear()
        self.run.current_revision = self.committed_revision


@pytest.fixture(scope="module")
def base_result() -> ReconciliationResult:
    raw = read_source_bundle(
        orders_path=DEMO_DIR / "internal_receivables.csv",
        bank_path=DEMO_DIR / "bank_transactions.csv",
    )
    normalized = normalize_bundle(raw, default_demo_mapping())
    return run_reconciliation(normalized, ReconciliationPolicy(currency=Currency.VND))


def _group_id(result: ReconciliationResult) -> str:
    return next(
        group.group_id
        for group in result.groups
        if group.order_ids == ("ORD00009", "ORD00010") and group.bank_txn_ids == ("TXN00007",)
    )


def _session(tmp_path: Path, monkeypatch, result: ReconciliationResult, *, fail_commit: bool = False):
    monkeypatch.setattr(get_settings(), "artifacts_path", tmp_path / "artifacts")
    run = ReconciliationRun(
        id="run-review-test",
        upload_session_id="upload-review-test",
        status="COMPLETED",
        currency="VND",
        policy_snapshot={},
        mapping_snapshot={},
        semantic_checksum=result.semantic_checksum,
        current_revision=0,
    )
    session = ReviewSession(run, fail_commit=fail_commit)
    write_json(effective_result_path(run.id, 0), result_to_payload(result))
    return session


def test_review_api_is_idempotent_and_stale_revision_returns_409(
    tmp_path: Path,
    monkeypatch,
    base_result: ReconciliationResult,
) -> None:
    session = _session(tmp_path, monkeypatch, base_result)

    def test_db() -> Generator[ReviewSession, None, None]:
        yield session

    group_id = _group_id(base_result)
    command = {
        "group_id": group_id,
        "expected_revision": 0,
        "idempotency_key": "approve-review-0001",
        "actor_label": "local_demo_label",
    }
    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as client:
            accepted = client.post(
                f"/api/runs/{session.run.id}/reviews/approve",
                json=command,
            )
            assert accepted.status_code == 200
            assert accepted.json()["effective_revision"] == 1
            assert accepted.json()["allocation_delta_minor"] == 500_000
            assert accepted.json()["conservation"]["is_valid"] is True

            replay = client.post(
                f"/api/runs/{session.run.id}/reviews/approve",
                json=command,
            )
            assert replay.status_code == 200
            assert replay.json()["action_id"] == accepted.json()["action_id"]
            assert replay.json()["idempotent_replay"] is True

            key_reuse = client.post(
                f"/api/runs/{session.run.id}/reviews/approve",
                json=command | {"group_id": "different-group"},
            )
            assert key_reuse.status_code == 409
            assert key_reuse.json()["detail"]["error_code"] == "IDEMPOTENCY_KEY_REUSED"

            stale = client.post(
                f"/api/runs/{session.run.id}/reviews/approve",
                json=command | {"idempotency_key": "approve-review-0002"},
            )
            assert stale.status_code == 409
            assert stale.json()["detail"]["error_code"] == "STALE_REVISION"
            assert stale.json()["detail"]["current_revision"] == 1
    finally:
        app.dependency_overrides.clear()

    assert len(session.committed_actions) == 1
    assert session.run.current_revision == 1


def test_review_commit_failure_rolls_back_and_removes_unpublished_artifact(
    tmp_path: Path,
    monkeypatch,
    base_result: ReconciliationResult,
) -> None:
    session = _session(tmp_path, monkeypatch, base_result, fail_commit=True)
    request = ApproveReviewRequest(
        group_id=_group_id(base_result),
        expected_revision=0,
        idempotency_key="approve-review-failure",
    )

    with pytest.raises(RuntimeError, match="forced commit failure"):
        approve_review(session, session.run.id, request)

    assert session.rollback_count == 1
    assert session.run.current_revision == 0
    assert session.committed_actions == {}
    assert not effective_result_path(session.run.id, 1).exists()
