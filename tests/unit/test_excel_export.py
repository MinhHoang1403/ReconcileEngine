from pathlib import Path

from openpyxl import load_workbook

from backend.smartrecon_api.config import get_settings
from backend.smartrecon_api.services.exports import create_excel_export, safe_excel_value


def test_formula_injection_is_exported_as_text(tmp_path: Path, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "artifacts_path", tmp_path)
    result = {
        "kpis": {
            "currency": "VND",
            "expected_receivable_minor": 28_000,
            "confirmed_cash_allocated_minor": 0,
            "verified_adjustments_minor": 0,
            "outstanding_receivable_minor": 28_000,
            "unapplied_bank_credit_minor": 0,
            "fully_settled_orders_count": 0,
            "unresolved_exceptions_count": 1,
        },
        "orders": [
            {
                "order_id": "O28",
                "description": '=HYPERLINK("https://invalid")',
                "expected_amount_minor": 28_000,
                "ordered_at": "2026-01-02",
                "lineage": {
                    "source_file_id": "orders-file",
                    "source_row_number": 2,
                    "source_row_hash": "row-hash",
                },
            }
        ],
        "bank_transactions": [],
        "groups": [],
        "allocations": [],
        "exceptions": [],
        "order_outstanding_minor": {"O28": 28_000},
        "payment_statuses": {"O28": "UNPAID"},
        "bank_unapplied_minor": {},
        "semantic_checksum": "fixture",
        "conservation": {"is_valid": True, "violations": []},
    }

    path = create_excel_export(
        "formula-test",
        result,
        source_manifest={"files": {"orders": {"name": "orders.csv", "sheet": None}}},
    )
    workbook = load_workbook(path, data_only=False)
    assert workbook.sheetnames == [
        "01_TongQuan_KPI",
        "02_Orders",
        "03_BankTransactions",
        "04_ConfirmedGroups",
        "05_AllocationEdges",
        "06_ReviewQueue",
        "07_Exceptions_Orphans",
        "08_ReviewAudit",
        "09_RunManifest",
    ]
    sheet = workbook["02_Orders"]
    headers = [cell.value for cell in sheet[1]]
    description_cell = sheet.cell(row=2, column=headers.index("Mô tả") + 1)
    amount_cell = sheet.cell(row=2, column=headers.index("Số tiền cần thu") + 1)
    date_cell = sheet.cell(row=2, column=headers.index("Ngày phát sinh") + 1)

    assert description_cell.data_type == "s"
    assert description_cell.value.startswith("'")
    assert amount_cell.data_type == "n"
    assert amount_cell.number_format == "#,##0;[Red](#,##0);-"
    assert date_cell.number_format == "dd/mm/yyyy"
    assert sheet.auto_filter.ref == "A1:U2"
    assert sheet.freeze_panes == "A2"
    assert sheet.cell(row=2, column=headers.index("Tệp nguồn") + 1).value == "orders.csv"
    assert all(cell.data_type != "f" for worksheet in workbook.worksheets for row in worksheet for cell in row)
    assert safe_excel_value("-123") == "'-123"
    assert safe_excel_value(-123) == -123
