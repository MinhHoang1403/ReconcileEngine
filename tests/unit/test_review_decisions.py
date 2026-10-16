from pathlib import Path

import pytest

from backend.smartrecon_api.services.runs import result_from_payload, result_to_payload
from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.statuses import Currency, LinkStatus, ReviewStatus
from smartrecon.engine import ReconciliationResult, run_reconciliation
from smartrecon.ingest.mapping import default_demo_mapping
from smartrecon.ingest.normalization import normalize_bundle
from smartrecon.ingest.readers import read_source_bundle
from smartrecon.review import ReviewDecisionError, approve_group, reject_group

DEMO_DIR = Path("data/demo/vn_synthetic_demo")


@pytest.fixture(scope="module")
def base_result() -> ReconciliationResult:
    raw = read_source_bundle(
        orders_path=DEMO_DIR / "internal_receivables.csv",
        bank_path=DEMO_DIR / "bank_transactions.csv",
    )
    normalized = normalize_bundle(raw, default_demo_mapping())
    return run_reconciliation(normalized, ReconciliationPolicy(currency=Currency.VND))


def _group_id(result: ReconciliationResult, order_ids: tuple[str, ...], bank_ids: tuple[str, ...]) -> str:
    return next(
        group.group_id for group in result.groups if group.order_ids == order_ids and group.bank_txn_ids == bank_ids
    )


def test_approve_group_creates_effective_edges_without_double_allocation(
    base_result: ReconciliationResult,
) -> None:
    group_id = _group_id(base_result, ("ORD00009", "ORD00010"), ("TXN00007",))

    reviewed = approve_group(base_result, group_id)
    group = next(item for item in reviewed.groups if item.group_id == group_id)
    new_edges = [edge for edge in reviewed.allocations if edge.group_id == group_id]

    assert group.link_status is LinkStatus.CONFIRMED
    assert group.review_status is ReviewStatus.APPROVED
    assert {(edge.order_id, edge.bank_txn_id, edge.allocated_cash_minor) for edge in new_edges} == {
        ("ORD00009", "TXN00007", 300_000),
        ("ORD00010", "TXN00007", 200_000),
    }
    assert sum(edge.allocated_cash_minor for edge in new_edges) == 500_000
    assert reviewed.conservation.is_valid
    assert reviewed.conservation.bank_allocated["TXN00007"] == 500_000
    assert group_id not in {candidate.candidate_id for candidate in reviewed.candidates}


def test_reject_group_changes_review_state_without_allocating_cash(
    base_result: ReconciliationResult,
) -> None:
    group_id = _group_id(base_result, ("ORD00004",), ("TXN00004",))

    reviewed = reject_group(base_result, group_id)
    group = next(item for item in reviewed.groups if item.group_id == group_id)

    assert group.link_status is LinkStatus.REJECTED
    assert group.review_status is ReviewStatus.REJECTED
    assert len(reviewed.allocations) == len(base_result.allocations)
    assert reviewed.kpis["confirmed_cash_allocated_minor"] == base_result.kpis["confirmed_cash_allocated_minor"]
    assert reviewed.conservation.is_valid


def test_complex_many_to_many_group_cannot_be_approved(base_result: ReconciliationResult) -> None:
    group_id = _group_id(
        base_result,
        ("ORD00029", "ORD00030"),
        ("TXN00024", "TXN00025"),
    )

    with pytest.raises(ReviewDecisionError, match="M:N") as error:
        approve_group(base_result, group_id)

    assert error.value.code == "COMPLEX_GROUP_NOT_APPROVABLE"


def test_effective_result_snapshot_round_trip_is_lossless(base_result: ReconciliationResult) -> None:
    payload = result_to_payload(base_result)

    restored = result_from_payload(payload)

    assert result_to_payload(restored) == payload
