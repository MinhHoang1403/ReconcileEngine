from pathlib import Path

from smartrecon.analytics.duckdb_queries import allocation_totals
from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.statuses import Currency
from smartrecon.engine import run_reconciliation
from smartrecon.ingest.mapping import default_demo_mapping
from smartrecon.ingest.normalization import normalize_bundle
from smartrecon.ingest.readers import read_source_bundle

DEMO_DIR = Path("data/demo/vn_synthetic_demo")


def _run_csv_demo():
    raw = read_source_bundle(
        orders_path=DEMO_DIR / "internal_receivables.csv",
        bank_path=DEMO_DIR / "bank_transactions.csv",
    )
    normalized = normalize_bundle(raw, default_demo_mapping())
    return run_reconciliation(normalized, ReconciliationPolicy(currency=Currency.VND))


def test_demo_runs_all_layers_and_preserves_money() -> None:
    result = _run_csv_demo()

    assert result.conservation.is_valid
    assert result.layer_counts["L1"]["confirmed_groups"] > 0
    assert result.layer_counts["L2"]["confirmed_groups"] > 0
    assert result.layer_counts["L3"]["proposed_groups"] > 0
    assert result.layer_counts["L4"]["proposed_groups"] > 0
    assert sum(result.kpis["payment_status_counts"].values()) == 100
    assert result.kpis["expected_receivable_minor"] == (
        result.kpis["confirmed_cash_allocated_minor"]
        + result.kpis["verified_adjustments_minor"]
        + result.kpis["outstanding_receivable_minor"]
    )
    eligible_bank_total = sum(
        bank.eligible_credit_minor for bank in result.bank_transactions if bank.bank_txn_id != "TXN00013-B"
    )
    assert eligible_bank_total == (
        result.kpis["confirmed_cash_allocated_minor"] + result.kpis["unapplied_bank_credit_minor"]
    )


def test_csv_and_xlsx_have_identical_engine_semantics() -> None:
    csv_result = _run_csv_demo()
    workbook = read_source_bundle(
        workbook_path=DEMO_DIR / "sample_reconciliation.xlsx",
        orders_sheet="Internal",
        bank_sheet="Bank",
    )
    xlsx_result = run_reconciliation(
        normalize_bundle(workbook, default_demo_mapping()),
        ReconciliationPolicy(currency=Currency.VND),
    )
    assert csv_result.semantic_checksum == xlsx_result.semantic_checksum
    assert csv_result.kpis == xlsx_result.kpis


def test_duckdb_analytics_cross_checks_effective_edge_totals() -> None:
    result = _run_csv_demo()
    totals = allocation_totals(list(result.allocations))

    assert totals["allocated_cash_minor"] == result.kpis["confirmed_cash_allocated_minor"]
    assert totals["orders_count"] == result.kpis["confirmed_link_orders_count"]
    assert totals["bank_rows_count"] == result.kpis["confirmed_bank_rows_count"]


def test_semantic_checksum_normalizes_equivalent_numeric_policy_values() -> None:
    raw = read_source_bundle(
        orders_path=DEMO_DIR / "internal_receivables.csv",
        bank_path=DEMO_DIR / "bank_transactions.csv",
    )
    normalized = normalize_bundle(raw, default_demo_mapping())

    integer_threshold = run_reconciliation(
        normalized,
        ReconciliationPolicy(currency=Currency.VND, fuzzy_candidate_threshold=85),
    )
    float_threshold = run_reconciliation(
        normalized,
        ReconciliationPolicy(currency=Currency.VND, fuzzy_candidate_threshold=85.0),
    )

    assert integer_threshold.semantic_checksum == float_threshold.semantic_checksum
