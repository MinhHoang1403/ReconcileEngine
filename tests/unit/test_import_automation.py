from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from smartrecon.domain.statuses import Currency
from smartrecon.ingest.automation import plan_automatic_import
from smartrecon.ingest.health import build_health_report
from smartrecon.ingest.mapping import BANK_FIELDS, BANK_REQUIRED, ORDER_FIELDS, ORDER_REQUIRED, analyze_mapping
from smartrecon.ingest.normalization import normalize_bundle
from smartrecon.ingest.readers import read_source_bundle


def source(tmp_path: Path, *, amount: str = "1000", currency: bool = True, rows: int = 1):
    orders = pd.DataFrame(
        {
            "order_id": [f"O{i:05}" for i in range(rows)],
            "ordered_at": ["2026-10-20"] * rows,
            "expected_amount": ["1000"] * rows,
            "currency": ["VND"] * rows,
        }
    )
    orders.loc[rows // 2, "expected_amount"] = amount
    banks = pd.DataFrame(
        {
            "bank_txn_id": ["B00001"],
            "txn_date": ["2026-10-21"],
            "posted_amount": ["1000"],
            "direction": ["CREDIT"],
            "amount_basis": ["POSTED_CASH"],
            "currency": ["VND"],
        }
    )
    if not currency:
        orders = orders.drop(columns="currency")
    paths = [tmp_path / "orders.csv", tmp_path / "bank.csv"]
    orders.to_csv(paths[0], index=False)
    banks.to_csv(paths[1], index=False)
    return read_source_bundle(orders_path=paths[0], bank_path=paths[1])


def analyses(raw):
    return (
        analyze_mapping(raw.orders.frame, ORDER_FIELDS, feed="orders", required_fields=ORDER_REQUIRED),
        analyze_mapping(
            raw.bank_transactions.frame, BANK_FIELDS, feed="bank_transactions", required_fields=BANK_REQUIRED
        ),
    )


def test_clear_source_can_normalize_without_guessing_locale_or_mutating_raw(tmp_path: Path) -> None:
    raw = source(tmp_path)
    before = raw.orders.frame.copy(deep=True)
    plan = plan_automatic_import(raw, *analyses(raw))
    assert not plan.reasons
    assert plan.mapping.currency is Currency.VND
    assert plan.mapping.thousand_separator is None
    normalized = normalize_bundle(raw, plan.mapping)
    assert build_health_report(normalized).status == "READY"
    assert normalized.orders[0].order_id == "O00000"
    assert normalized.orders[0].expected_amount_minor == 1000
    assert raw.orders.frame.equals(before)


@pytest.mark.parametrize("amount", ["1.000", "1000.0", "1 000", "-1000"])
def test_unconfirmed_money_format_is_not_automated(tmp_path: Path, amount: str) -> None:
    raw = source(tmp_path, amount=amount, rows=231)
    plan = plan_automatic_import(raw, *analyses(raw))
    assert plan.mapping is None
    assert plan.reasons


def test_absent_currency_is_a_question_not_an_implicit_vnd_assumption(tmp_path: Path) -> None:
    raw = source(tmp_path, currency=False)
    plan = plan_automatic_import(raw, *analyses(raw))
    assert plan.mapping is None
    assert "CURRENCY_REQUIRES_CONFIRMATION" in plan.reasons


def test_currency_outside_mapping_sample_still_prevents_automation(tmp_path: Path) -> None:
    raw = source(tmp_path, rows=231)
    frame = raw.orders.frame.copy()
    frame.loc[115, "currency"] = "BRL"
    raw = replace(raw, orders=replace(raw.orders, frame=frame))
    plan = plan_automatic_import(raw, *analyses(raw))
    assert plan.mapping is None
    assert "CURRENCY_REQUIRES_CONFIRMATION" in plan.reasons


def test_explicit_profile_can_supply_confirmed_money_format(tmp_path: Path) -> None:
    raw = source(tmp_path)
    plan = plan_automatic_import(raw, *analyses(raw))
    explicit = replace(plan.mapping, decimal_separator=",", thousand_separator=".")
    raw = source(tmp_path, amount="1.000")
    assert build_health_report(normalize_bundle(raw, explicit)).status == "READY"
    accepted = plan_automatic_import(raw, *analyses(raw), confirmed_mapping=explicit)
    assert accepted.mapping == explicit
    assert normalize_bundle(raw, accepted.mapping).orders[0].expected_amount_minor == 1000


def test_explicit_gross_basis_still_hits_blocking_health_gate(tmp_path: Path) -> None:
    raw = source(tmp_path)
    frame = raw.bank_transactions.frame.copy()
    frame.loc[0, "amount_basis"] = "GROSS_SETTLEMENT"
    raw = replace(raw, bank_transactions=replace(raw.bank_transactions, frame=frame))
    plan = plan_automatic_import(raw, *analyses(raw))
    assert plan.mapping is not None
    assert build_health_report(normalize_bundle(raw, plan.mapping)).status == "BLOCKED"


def test_profile_does_not_override_ambiguous_structure(tmp_path: Path) -> None:
    raw = source(tmp_path)
    explicit = plan_automatic_import(raw, *analyses(raw)).mapping
    raw = replace(raw, orders=replace(raw.orders, structure=replace(raw.orders.structure, status="NEEDS_REVIEW")))
    plan = plan_automatic_import(raw, *analyses(raw), confirmed_mapping=explicit)
    assert plan.mapping is None
    assert "STRUCTURE_REQUIRES_CONFIRMATION" in plan.reasons
