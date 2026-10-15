from dataclasses import asdict
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from smartrecon.domain.statuses import Currency, Severity
from smartrecon.ingest.eda import summarize_raw, summarize_standardized
from smartrecon.ingest.health import Exclusion, apply_exclusions, build_health_report
from smartrecon.ingest.mapping import MappingConfig, default_demo_mapping, suggest_mapping
from smartrecon.ingest.normalization import normalize_bundle
from smartrecon.ingest.readers import InputFileError, read_source_bundle, read_table

DEMO_DIR = Path("data/demo/vn_synthetic_demo")


def _read_demo_csv():
    return read_source_bundle(
        orders_path=DEMO_DIR / "internal_receivables.csv",
        bank_path=DEMO_DIR / "bank_transactions.csv",
    )


def _minimal_mapping() -> MappingConfig:
    return MappingConfig(
        order_columns={
            "order_id": "order_id",
            "ordered_at": "ordered_at",
            "expected_amount": "expected_amount",
        },
        bank_columns={
            "bank_txn_id": "bank_txn_id",
            "txn_date": "txn_date",
            "posted_amount": "posted_amount",
            "direction": "direction",
            "amount_basis": "amount_basis",
        },
        currency=Currency.VND,
    )


def test_csv_and_xlsx_normalize_to_the_same_semantics() -> None:
    csv_bundle = _read_demo_csv()
    xlsx_bundle = read_source_bundle(
        workbook_path=DEMO_DIR / "sample_reconciliation.xlsx",
        orders_sheet="Internal",
        bank_sheet="Bank",
    )
    mapping = default_demo_mapping()

    csv_normalized = normalize_bundle(csv_bundle, mapping)
    xlsx_normalized = normalize_bundle(xlsx_bundle, mapping)

    def order_semantics(rows):
        return [(row.order_id, row.ordered_at, row.expected_amount_minor, row.currency) for row in rows]

    def bank_semantics(rows):
        return [
            (
                row.bank_txn_id,
                row.txn_date,
                row.posted_amount_minor,
                row.currency,
                row.direction,
            )
            for row in rows
        ]

    assert order_semantics(csv_normalized.orders) == order_semantics(xlsx_normalized.orders)
    assert bank_semantics(csv_normalized.bank_transactions) == bank_semantics(xlsx_normalized.bank_transactions)
    assert csv_normalized.duplicate_bank_ids == ("TXN00013-B",)
    assert not [issue for issue in csv_normalized.issues if issue.severity is Severity.BLOCKING]


def test_raw_and_standardized_eda_use_distinct_denominators() -> None:
    raw = _read_demo_csv()
    normalized = normalize_bundle(raw, default_demo_mapping())

    raw_orders = summarize_raw(raw.orders)
    standardized = summarize_standardized(
        list(normalized.orders), list(normalized.bank_transactions), Currency.VND.value
    )

    assert raw_orders.row_count == 100
    assert raw_orders.confidence == "PRELIMINARY_BEFORE_MAPPING"
    assert standardized.orders_count == 100
    assert standardized.bank_rows_count == 98
    assert standardized.eligible_credit_count == 97  # one debit is outside the credit pool
    assert standardized.currency == "VND"


def test_mapping_suggestions_are_alias_based_and_require_confirmation() -> None:
    suggestions = suggest_mapping(
        ["order_ref", "tx_date", "amount", "unknown"],
        {"order_id", "ordered_at", "expected_amount", "customer_name"},
    )
    assert suggestions == {
        "expected_amount": "amount",
        "order_id": "order_ref",
        "ordered_at": "tx_date",
    }


def test_mapping_suggestions_accept_exact_vietnamese_aliases_without_fuzzy_guessing() -> None:
    suggestions = suggest_mapping(
        ["MÃ ĐƠN HÀNG", "Ngày phát sinh", "Số tiền cần thu", "ma don hang gan giong"],
        {"order_id", "ordered_at", "expected_amount"},
    )
    assert suggestions == {
        "expected_amount": "Số tiền cần thu",
        "order_id": "MÃ ĐƠN HÀNG",
        "ordered_at": "Ngày phát sinh",
    }


def test_ambiguous_normalized_header_is_not_suggested() -> None:
    suggestions = suggest_mapping(["Mã đơn hàng", "ma-don-hang"], {"order_id"})
    assert suggestions == {}


def test_reusing_one_source_column_for_multiple_fields_blocks_health() -> None:
    raw = _read_demo_csv()
    mapping = default_demo_mapping()
    conflicted = MappingConfig(
        order_columns=mapping.order_columns | {"ordered_at": mapping.order_columns["order_id"]},
        bank_columns=mapping.bank_columns,
        currency=mapping.currency,
    )
    normalized = normalize_bundle(raw, conflicted)
    issue = next(item for item in normalized.issues if item.code == "SOURCE_COLUMN_REUSED")
    assert issue.severity is Severity.BLOCKING
    assert "order_id" in issue.message_vi


def test_leading_zero_identifier_survives_csv_and_xlsx() -> None:
    mapping = default_demo_mapping()
    for raw in (
        _read_demo_csv(),
        read_source_bundle(
            workbook_path=DEMO_DIR / "sample_reconciliation.xlsx",
            orders_sheet="Internal",
            bank_sheet="Bank",
        ),
    ):
        normalized = normalize_bundle(raw, mapping)
        assert any(order.order_id == "00017" for order in normalized.orders)


def test_health_reports_duplicate_as_warning_not_silent_drop() -> None:
    normalized = normalize_bundle(_read_demo_csv(), default_demo_mapping())
    report = build_health_report(normalized)

    duplicate_issue = next(issue for issue in report.issues if issue.code == "POSSIBLE_REIMPORT")
    assert report.status == "READY"
    assert report.info_count == 1
    assert duplicate_issue.severity is Severity.WARNING
    assert len(normalized.bank_transactions) == 98

    duplicate_bank = next(bank for bank in normalized.bank_transactions if bank.bank_txn_id == "TXN00013-B")
    resolved, resolved_report = apply_exclusions(
        normalized,
        [
            Exclusion(
                "bank_transactions",
                duplicate_bank.lineage.source_row_number,
                "Đã xác minh là dòng import lặp",
            )
        ],
    )
    assert len(resolved.bank_transactions) == 97
    assert resolved_report.status == "READY"
    assert resolved_report.excluded_rows[0].reason


def test_bad_amount_and_currency_mismatch_block_health(tmp_path: Path) -> None:
    orders = pd.DataFrame(
        [
            {
                "order_id": "O1",
                "ordered_at": "2026-01-01",
                "expected_amount": "not-money",
                "currency": "VND",
                "order_status": "ELIGIBLE",
            },
            {
                "order_id": "O2",
                "ordered_at": "2026-01-01",
                "expected_amount": "10.00",
                "currency": "BRL",
                "order_status": "ELIGIBLE",
            },
        ]
    )
    bank = pd.DataFrame(
        [
            {
                "bank_txn_id": "B1",
                "txn_date": "2026-01-01",
                "posted_amount": "100",
                "direction": "CREDIT",
                "amount_basis": "POSTED_CASH",
                "currency": "VND",
            }
        ]
    )
    orders_path = tmp_path / "orders.csv"
    bank_path = tmp_path / "bank.csv"
    orders.to_csv(orders_path, index=False)
    bank.to_csv(bank_path, index=False)

    mapping = MappingConfig(
        order_columns={
            "order_id": "order_id",
            "ordered_at": "ordered_at",
            "expected_amount": "expected_amount",
            "currency": "currency",
            "order_status": "order_status",
        },
        bank_columns={
            "bank_txn_id": "bank_txn_id",
            "txn_date": "txn_date",
            "posted_amount": "posted_amount",
            "direction": "direction",
            "amount_basis": "amount_basis",
            "currency": "currency",
        },
        currency=Currency.VND,
    )
    normalized = normalize_bundle(read_source_bundle(orders_path=orders_path, bank_path=bank_path), mapping)
    report = build_health_report(normalized)

    assert report.status == "BLOCKED"
    assert {issue.code for issue in report.issues} >= {"ORDER_PARSE_ERROR", "CURRENCY_MISMATCH"}
    assert len(normalized.rejected_rows) == 1


def _write_money_sources(tmp_path: Path, suffix: str, amount: str) -> tuple[Path, Path]:
    orders = pd.DataFrame([{"order_id": "O1", "ordered_at": "2026-01-01", "expected_amount": amount}])
    bank = pd.DataFrame(
        [
            {
                "bank_txn_id": "B1",
                "txn_date": "2026-01-01",
                "posted_amount": amount,
                "direction": "CREDIT",
                "amount_basis": "POSTED_CASH",
            }
        ]
    )
    orders_path = tmp_path / f"orders{suffix}"
    bank_path = tmp_path / f"bank{suffix}"
    if suffix == ".csv":
        orders.to_csv(orders_path, index=False)
        bank.to_csv(bank_path, index=False)
    else:
        orders.to_excel(orders_path, index=False)
        bank.to_excel(bank_path, index=False)
    return orders_path, bank_path


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_integral_vnd_decimal_is_valid_for_csv_and_xlsx(tmp_path: Path, suffix: str) -> None:
    orders_path, bank_path = _write_money_sources(tmp_path, suffix, "100000.0")

    normalized = normalize_bundle(
        read_source_bundle(orders_path=orders_path, bank_path=bank_path),
        _minimal_mapping(),
    )
    report = build_health_report(normalized)

    assert report.status == "READY"
    assert normalized.orders[0].expected_amount_minor == 100_000
    assert normalized.bank_transactions[0].posted_amount_minor == 100_000
    assert normalized.rejected_rows == ()


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_fractional_vnd_blocks_csv_and_xlsx_without_silent_drop(tmp_path: Path, suffix: str) -> None:
    orders_path, bank_path = _write_money_sources(tmp_path, suffix, "100000.5")

    normalized = normalize_bundle(
        read_source_bundle(orders_path=orders_path, bank_path=bank_path),
        _minimal_mapping(),
    )
    report = build_health_report(normalized)
    parse_issues = [issue for issue in report.issues if issue.code in {"ORDER_PARSE_ERROR", "BANK_PARSE_ERROR"}]

    assert report.status == "BLOCKED"
    assert {issue.feed for issue in parse_issues} == {"orders", "bank_transactions"}
    assert all(issue.severity is Severity.BLOCKING for issue in parse_issues)
    assert all(issue.source_rows == (2,) for issue in parse_issues)
    assert all("100000.5" in issue.message_vi for issue in parse_issues)
    assert all(issue.sample_values == ("100000.5",) for issue in parse_issues)
    assert normalized.orders == ()
    assert normalized.bank_transactions == ()
    assert {(row.feed, row.source_row_number) for row in normalized.rejected_rows} == {
        ("orders", 2),
        ("bank_transactions", 2),
    }


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_fractional_vnd_declared_fee_is_not_ignored(tmp_path: Path, suffix: str) -> None:
    orders_path, bank_path = _write_money_sources(tmp_path, suffix, "100000")
    if suffix == ".csv":
        bank = pd.read_csv(bank_path, dtype=str)
        bank["declared_fee"] = "0.5"
        bank.to_csv(bank_path, index=False)
    else:
        bank = pd.read_excel(bank_path, dtype=str)
        bank["declared_fee"] = "0.5"
        bank.to_excel(bank_path, index=False)
    base_mapping = _minimal_mapping()
    mapping = MappingConfig(
        order_columns=base_mapping.order_columns,
        bank_columns=base_mapping.bank_columns | {"declared_fee": "declared_fee"},
        currency=Currency.VND,
    )

    normalized = normalize_bundle(
        read_source_bundle(orders_path=orders_path, bank_path=bank_path),
        mapping,
    )
    report = build_health_report(normalized)
    issue = next(item for item in report.issues if item.code == "BANK_PARSE_ERROR")

    assert report.status == "BLOCKED"
    assert issue.severity is Severity.BLOCKING
    assert issue.source_rows == (2,)
    assert issue.sample_values == ("100000", "0.5")
    assert "0.5" in issue.message_vi
    assert normalized.bank_transactions == ()
    assert normalized.rejected_rows[0].reason_code == "BANK_PARSE_ERROR"


def test_invalid_file_content_and_ambiguous_workbook_are_rejected(tmp_path: Path) -> None:
    fake_xlsx = tmp_path / "fake.xlsx"
    fake_xlsx.write_text("not a zip", encoding="utf-8")
    with pytest.raises(InputFileError, match="XLSX"):
        read_table(fake_xlsx)

    with pytest.raises(InputFileError, match="hai sheet khác nhau"):
        read_source_bundle(
            workbook_path=DEMO_DIR / "sample_reconciliation.xlsx",
            orders_sheet="Internal",
            bank_sheet="Internal",
        )


def test_duplicate_headers_are_rejected_before_pandas_can_rename_them(tmp_path: Path) -> None:
    duplicate_csv = tmp_path / "duplicate.csv"
    duplicate_csv.write_text("id,id\n1,2\n", encoding="utf-8")
    with pytest.raises(InputFileError, match="Header"):
        read_table(duplicate_csv)

    duplicate_xlsx = tmp_path / "duplicate.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["id", "id"])
    worksheet.append(["1", "2"])
    workbook.save(duplicate_xlsx)
    workbook.close()
    with pytest.raises(InputFileError, match="Header"):
        read_table(duplicate_xlsx)


def test_same_amount_and_date_without_reference_are_distinct_cash_rows(tmp_path: Path) -> None:
    orders_path = tmp_path / "orders.csv"
    bank_path = tmp_path / "bank.csv"
    pd.DataFrame([{"order_id": "O1", "ordered_at": "2026-01-01", "expected_amount": "200000"}]).to_csv(
        orders_path, index=False
    )
    pd.DataFrame(
        [
            {
                "bank_txn_id": "B1",
                "txn_date": "2026-01-02",
                "posted_amount": "100000",
                "direction": "CREDIT",
                "amount_basis": "POSTED_CASH",
            },
            {
                "bank_txn_id": "B2",
                "txn_date": "2026-01-02",
                "posted_amount": "100000",
                "direction": "CREDIT",
                "amount_basis": "POSTED_CASH",
            },
        ]
    ).to_csv(bank_path, index=False)

    normalized = normalize_bundle(
        read_source_bundle(orders_path=orders_path, bank_path=bank_path),
        _minimal_mapping(),
    )

    assert normalized.duplicate_bank_ids == ()
    assert not [issue for issue in normalized.issues if issue.code == "POSSIBLE_REIMPORT"]


def test_excluding_one_colliding_row_resolves_collision_when_one_row_remains(tmp_path: Path) -> None:
    orders_path = tmp_path / "orders.csv"
    bank_path = tmp_path / "bank.csv"
    pd.DataFrame(
        [
            {"order_id": "O1", "ordered_at": "2026-01-01", "expected_amount": "100000"},
            {"order_id": "O1", "ordered_at": "2026-01-02", "expected_amount": "100000"},
        ]
    ).to_csv(orders_path, index=False)
    pd.DataFrame(
        [
            {
                "bank_txn_id": "B1",
                "txn_date": "2026-01-02",
                "posted_amount": "100000",
                "direction": "CREDIT",
                "amount_basis": "POSTED_CASH",
            }
        ]
    ).to_csv(bank_path, index=False)
    normalized = normalize_bundle(
        read_source_bundle(orders_path=orders_path, bank_path=bank_path),
        _minimal_mapping(),
    )
    assert build_health_report(normalized).status == "BLOCKED"

    filtered, report = apply_exclusions(
        normalized,
        [Exclusion("orders", 3, "Dòng trùng đã được xác minh")],
    )

    assert [order.order_id for order in filtered.orders] == ["O1"]
    assert report.status == "READY"
    assert not [issue for issue in report.issues if issue.code == "ORDER_ID_COLLISION"]


def test_lineage_hashes_are_present_and_json_ready() -> None:
    normalized = normalize_bundle(_read_demo_csv(), default_demo_mapping())
    first = normalized.orders[0]
    lineage = asdict(first.lineage)
    assert lineage["source_row_number"] == 2
    assert len(lineage["source_row_hash"]) == 64
    assert len(normalized.source_hashes["orders"]) == 64
