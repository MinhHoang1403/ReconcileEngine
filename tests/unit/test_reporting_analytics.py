from pathlib import Path

from smartrecon.analytics.reporting import snapshot_analytics
from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.statuses import Currency
from smartrecon.engine import run_reconciliation
from smartrecon.ingest.mapping import default_demo_mapping
from smartrecon.ingest.normalization import normalize_bundle
from smartrecon.ingest.readers import read_source_bundle
from smartrecon.review import approve_group

DEMO_DIR = Path("data/demo/vn_synthetic_demo")


def _demo_result():
    raw = read_source_bundle(
        orders_path=DEMO_DIR / "internal_receivables.csv",
        bank_path=DEMO_DIR / "bank_transactions.csv",
    )
    return run_reconciliation(
        normalize_bundle(raw, default_demo_mapping()),
        ReconciliationPolicy(currency=Currency.VND),
    )


def test_snapshot_analytics_defines_denominators_and_tracks_review_changes() -> None:
    before = _demo_result()
    target = next(
        group
        for group in before.groups
        if group.order_ids == ("ORD00009", "ORD00010") and group.bank_txn_ids == ("TXN00007",)
    )
    before_metrics = snapshot_analytics(before)
    after_metrics = snapshot_analytics(approve_group(before, target.group_id))

    assert before_metrics["method_summary"]["confirmation_rate_denominator"] == "ALL_RELATION_GROUPS"
    assert before_metrics["method_summary"]["total_relation_groups"] == len(before.groups)
    assert after_metrics["method_summary"]["confirmed_groups"] == (
        before_metrics["method_summary"]["confirmed_groups"] + 1
    )
    assert after_metrics["review_status_counts"]["APPROVED"] == 1
    assert after_metrics["review_status_counts"]["OPEN"] == before_metrics["review_status_counts"]["OPEN"] - 1
    assert sum(item["count"] for item in before_metrics["confirmed_lag"]["buckets"]) == len(before.allocations)
    assert sum(item["amount_minor"] for item in before_metrics["residual_distribution"]["order_outstanding"]) == sum(
        before.order_outstanding_minor.values()
    )
    assert sum(item["amount_minor"] for item in before_metrics["residual_distribution"]["bank_unapplied"]) == sum(
        value for value in before.bank_unapplied_minor.values() if value > 0
    )
