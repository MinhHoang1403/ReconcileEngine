from dataclasses import replace
from pathlib import Path

import pytest
from openpyxl import Workbook

from smartrecon.domain.statuses import Currency, Severity
from smartrecon.ingest.health import Exclusion, apply_exclusions, build_health_report
from smartrecon.ingest.mapping import (
    BANK_FIELDS,
    BANK_REQUIRED,
    ORDER_FIELDS,
    ORDER_REQUIRED,
    MappingConfig,
    analyze_mapping,
)
from smartrecon.ingest.normalization import normalize_bundle
from smartrecon.ingest.readers import read_source_bundle


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize("style", ["english", "vietnamese", "unaccented"])
def test_source_variants_map_and_normalize_without_changing_money(tmp_path: Path, suffix: str, style: str) -> None:
    headers = {
        "english": (
            ["Order No", "Created Date", "Amount Due"],
            ["TX ID", "Posting Date", "Net Amount", "Credit Debit", "Basis"],
        ),
        "vietnamese": (
            ["Mã ĐH", "Ngày tạo", "Số tiền cần thu"],
            ["Mã GD", "Ngày hạch toán", "Số tiền thực nhận", "Chiều giao dịch", "Cơ sở số tiền"],
        ),
        "unaccented": (
            ["ma don hang", "ngay phat sinh", "so tien phai thu"],
            ["ma giao dich", "ngay giao dich", "so tien thuc nhan", "chieu giao dich", "loai so tien"],
        ),
    }
    order_headers, bank_headers = headers[style]
    paths = [tmp_path / f"orders.{suffix}", tmp_path / f"bank.{suffix}"]
    data = [
        (order_headers, ["00001", "2026-10-20", "120000"]),
        (bank_headers, ["00009", "2026-10-21", "120000", "CREDIT", "POSTED_CASH"]),
    ]
    for path, (columns, values) in zip(paths, data, strict=True):
        if suffix == "csv":
            path.write_text(";".join(columns) + "\n" + ";".join(values) + "\n", encoding="utf-8-sig")
        else:
            workbook = Workbook()
            workbook.active.append(columns)
            workbook.active.append(values)
            workbook.save(path)
            workbook.close()
    raw = read_source_bundle(orders_path=paths[0], bank_path=paths[1])
    orders = analyze_mapping(raw.orders.frame, ORDER_FIELDS, feed="orders", required_fields=ORDER_REQUIRED)
    bank = analyze_mapping(
        raw.bank_transactions.frame, BANK_FIELDS, feed="bank_transactions", required_fields=BANK_REQUIRED
    )
    assert orders.selected_mapping == dict(
        zip(("order_id", "ordered_at", "expected_amount"), order_headers, strict=True)
    )
    assert bank.selected_mapping == dict(
        zip(("bank_txn_id", "txn_date", "posted_amount", "direction", "amount_basis"), bank_headers, strict=True)
    )
    mapping = MappingConfig(
        order_columns=orders.selected_mapping,
        bank_columns=bank.selected_mapping,
        currency=Currency.VND,
        date_format="AUTO",
    )
    normalized = normalize_bundle(raw, mapping)
    assert not normalized.rejected_rows
    assert normalized.orders[0].order_id == "00001"
    assert normalized.bank_transactions[0].bank_txn_id == "00009"
    assert normalized.orders[0].expected_amount_minor == normalized.bank_transactions[0].posted_amount_minor == 120000
    assert (
        normalized.orders[0].lineage.source_row_number == normalized.bank_transactions[0].lineage.source_row_number == 2
    )
    assert normalize_bundle(raw, replace(mapping)) == normalized


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
def test_parseable_report_total_cannot_become_a_transaction(tmp_path: Path, suffix: str) -> None:
    """A date on a total row must not bypass the structure warning during normalization."""
    paths = [tmp_path / f"orders.{suffix}", tmp_path / f"bank.{suffix}"]
    rows = [
        [
            ["order_id", "ordered_at", "expected_amount"],
            ["O1", "2026-10-20", "120000"],
            ["Total", "2026-10-20", "120000"],
        ],
        [
            ["bank_txn_id", "txn_date", "posted_amount", "direction", "amount_basis"],
            ["B1", "2026-10-21", "120000", "CREDIT", "POSTED_CASH"],
            ["Total", "2026-10-21", "120000", "CREDIT", "POSTED_CASH"],
        ],
    ]
    for path, table in zip(paths, rows, strict=True):
        if suffix == "csv":
            path.write_text("\n".join(";".join(row) for row in table) + "\n", encoding="utf-8")
        else:
            workbook = Workbook()
            for row in table:
                workbook.active.append(row)
            workbook.save(path)
            workbook.close()
    raw = read_source_bundle(orders_path=paths[0], bank_path=paths[1])
    mapping = MappingConfig(
        order_columns={field: field for field in ORDER_REQUIRED},
        bank_columns={field: field for field in BANK_REQUIRED},
        currency=Currency.VND,
        confirmed_structure=True,
    )
    normalized = normalize_bundle(raw, mapping)
    assert build_health_report(normalized).status == "BLOCKED"
    assert [row.order_id for row in normalized.orders] == ["O1"]
    assert [row.bank_txn_id for row in normalized.bank_transactions] == ["B1"]
    assert {(row.feed, row.source_row_number) for row in normalized.rejected_rows} == {
        ("orders", 3),
        ("bank_transactions", 3),
    }
    assert all(issue.source_rows == (3,) for issue in normalized.issues if issue.severity is Severity.BLOCKING)
    resolved, report = apply_exclusions(
        normalized,
        [
            Exclusion("orders", 3, "Dòng tổng báo cáo"),
            Exclusion("bank_transactions", 3, "Dòng tổng báo cáo"),
        ],
    )
    assert report.status == "READY"
    assert sum(row.expected_amount_minor for row in resolved.orders) == 120000
    assert sum(row.posted_amount_minor for row in resolved.bank_transactions) == 120000
    assert raw.orders.frame.iloc[1]["order_id"] == raw.bank_transactions.frame.iloc[1]["bank_txn_id"] == "Total"


@pytest.mark.parametrize("suffix", ["csv", "xlsx"])
@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("order_id", "", "ORDER_PARSE_ERROR"),
        ("ordered_at", "2026-02-30", "ORDER_PARSE_ERROR"),
        ("expected_amount", "1000.5", "ORDER_PARSE_ERROR"),
        ("bank_txn_id", "", "BANK_PARSE_ERROR"),
        ("txn_date", "not a date", "BANK_PARSE_ERROR"),
        ("direction", "MAYBE", "BANK_PARSE_ERROR"),
        ("amount_basis", "TOTAL", "BANK_PARSE_ERROR"),
        ("posted_amount", "Infinity", "BANK_PARSE_ERROR"),
        ("order_id", "O0", "ORDER_ID_COLLISION"),
        ("bank_txn_id", "B0", "BANK_ID_COLLISION"),
    ],
)
def test_validation_covers_every_source_row_and_retains_lineage(
    tmp_path: Path,
    suffix: str,
    field: str,
    value: str,
    code: str,
) -> None:
    """An invalid middle row cannot disappear behind display/evidence sampling limits."""
    import pandas as pd

    orders = pd.DataFrame(
        [{"order_id": f"O{index}", "ordered_at": "2026-10-20", "expected_amount": "1000"} for index in range(131)]
    )
    bank = pd.DataFrame(
        [
            {
                "bank_txn_id": f"B{index}",
                "txn_date": "2026-10-21",
                "posted_amount": "1000",
                "direction": "CREDIT",
                "amount_basis": "POSTED_CASH",
            }
            for index in range(131)
        ]
    )
    target = orders if field in orders.columns else bank
    target.loc[73, field] = value
    paths = [tmp_path / f"orders.{suffix}", tmp_path / f"bank.{suffix}"]
    for path, frame in zip(paths, (orders, bank), strict=True):
        if suffix == "csv":
            frame.to_csv(path, index=False)
        else:
            frame.to_excel(path, index=False)
    raw = read_source_bundle(orders_path=paths[0], bank_path=paths[1])
    normalized = normalize_bundle(
        raw,
        MappingConfig(
            order_columns={name: name for name in ORDER_REQUIRED},
            bank_columns={name: name for name in BANK_REQUIRED},
            currency=Currency.VND,
        ),
    )
    issue = next(issue for issue in normalized.issues if issue.code == code)
    assert issue.severity is Severity.BLOCKING
    assert 75 in issue.source_rows
    assert build_health_report(normalized).status == "BLOCKED"
    if code.endswith("PARSE_ERROR"):
        rejected = normalized.rejected_rows
        assert len(rejected) == 1
        assert rejected[0].source_row_number == 75
        assert len(rejected[0].source_row_hash) == 64
    else:
        assert not normalized.rejected_rows  # collision remains visible for an explicit resolution
    for records, table in ((normalized.orders, raw.orders), (normalized.bank_transactions, raw.bank_transactions)):
        assert all(record.lineage.source_file_id == table.source_file_id for record in records)
        assert all(len(record.lineage.source_row_hash) == 64 for record in records)
