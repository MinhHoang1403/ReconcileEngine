import csv
import json
from pathlib import Path

from openpyxl import load_workbook

from smartrecon.generation.synthetic import (
    BANK_COLUMNS,
    BUSINESS_TRUTH_DENYLIST,
    ORDER_COLUMNS,
    generate_vnd_demo,
    write_demo_bundle,
)


def test_generator_is_semantically_deterministic_and_covers_required_cases() -> None:
    first = generate_vnd_demo(seed=42, order_count=100)
    second = generate_vnd_demo(seed=42, order_count=100)

    assert first == second
    assert len(first.orders) == 100
    case_ids = {case["case_id"] for case in first.truth_cases}
    assert {f"F{number:02d}" for number in range(1, 19)} - {"F19", "F20"} <= case_ids
    assert {"F22", "F23", "F24"} <= case_ids
    assert first.manifest["counts"]["orders"] == 100


def test_business_feeds_do_not_leak_truth_fields() -> None:
    bundle = generate_vnd_demo()
    assert not (set(bundle.orders[0]) & BUSINESS_TRUTH_DENYLIST)
    assert not (set(bundle.bank_transactions[0]) & BUSINESS_TRUTH_DENYLIST)


def test_csv_and_workbook_have_equivalent_business_values(tmp_path: Path) -> None:
    bundle = generate_vnd_demo()
    paths = write_demo_bundle(bundle, tmp_path)
    workbook = load_workbook(paths["workbook"], read_only=True, data_only=True)

    with Path(paths["orders"]).open(encoding="utf-8", newline="") as handle:
        csv_orders = list(csv.DictReader(handle))
    sheet_orders = list(workbook["Internal"].values)
    assert list(sheet_orders[0]) == ORDER_COLUMNS
    assert str(sheet_orders[1][0]) == csv_orders[0]["order_id"]
    assert int(sheet_orders[1][2]) == int(csv_orders[0]["expected_amount"])

    with Path(paths["bank"]).open(encoding="utf-8", newline="") as handle:
        csv_bank = list(csv.DictReader(handle))
    sheet_bank = list(workbook["Bank"].values)
    assert list(sheet_bank[0]) == BANK_COLUMNS
    assert str(sheet_bank[1][0]) == csv_bank[0]["bank_txn_id"]
    assert int(sheet_bank[1][5]) == int(csv_bank[0]["posted_amount"])

    manifest = json.loads(Path(paths["manifest"]).read_text(encoding="utf-8"))
    assert manifest == bundle.manifest
