import csv
from collections import defaultdict
from pathlib import Path

from research.financial_cases import write_holdout
from smartrecon.config import ReconciliationPolicy
from smartrecon.domain.statuses import Currency
from smartrecon.engine import run_reconciliation
from smartrecon.ingest.mapping import default_demo_mapping
from smartrecon.ingest.normalization import normalize_bundle
from smartrecon.ingest.readers import read_source_bundle


def read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_independent_holdout_is_reproducible_and_labels_conserve_cash(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    manifest = write_holdout(first, cases_per_relation=3)
    assert write_holdout(second, cases_per_relation=3) == manifest
    for file in first.iterdir():
        assert file.read_bytes() == (second / file.name).read_bytes()
    orders = read(first / "internal_receivables.csv")
    banks = read(first / "bank_transactions.csv")
    edges = read(first / "truth_edges.csv")
    assert {edge["truth_relation"] for edge in edges} == {"1:1", "N:1", "1:N", "M:N"}
    assert all(not ({"case_id", "truth_group_id", "scenario"} & row.keys()) for row in orders + banks)
    order_cash, bank_cash = defaultdict(int), defaultdict(int)
    for edge in edges:
        amount = int(edge["allocated_cash_minor"])
        assert amount > 0
        order_cash[edge["order_id"]] += amount
        bank_cash[edge["bank_txn_id"]] += amount
    assert all(order_cash[row["order_id"]] <= int(row["expected_amount"]) for row in orders)
    assert all(bank_cash[row["bank_txn_id"]] <= int(row["posted_amount"]) for row in banks)
    # No labels enter normalization or execution; evaluate only after the result exists.
    raw = read_source_bundle(orders_path=first / "internal_receivables.csv", bank_path=first / "bank_transactions.csv")
    result = run_reconciliation(normalize_bundle(raw, default_demo_mapping()), ReconciliationPolicy(Currency.VND))
    assert result.conservation.is_valid
    truth_keys = {(edge["order_id"], edge["bank_txn_id"]) for edge in edges}
    assert {(edge.order_id, edge.bank_txn_id) for edge in result.allocations} <= truth_keys
