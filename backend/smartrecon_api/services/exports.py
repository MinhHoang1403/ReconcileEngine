"""Vietnamese Excel reporting from one immutable reconciliation snapshot."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from backend.smartrecon_api.services.artifacts import run_directory

SHEET_NAMES = [
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

PAYMENT_STATUS = {
    "FULL": "Đã thu đủ",
    "PARTIAL": "Thu một phần",
    "NO_CONFIRMED_RECEIPT": "Chưa có tiền xác nhận",
    "UNKNOWN": "Chưa xác định",
    "NOT_ELIGIBLE": "Không đủ điều kiện",
}
ORDER_STATUS = {"ELIGIBLE": "Đủ điều kiện", "EXCLUDED": "Không tham gia đối soát"}
AMOUNT_BASIS = {
    "POSTED_CASH": "Tiền thực nhận",
    "NET_SETTLEMENT": "Tiền quyết toán ròng",
    "GROSS_REPORT": "Báo cáo giá trị gộp",
}
LINK_STATUS = {"CONFIRMED": "Đã xác nhận", "PROPOSED": "Đề xuất, chưa xác nhận"}
GROUP_TYPE = {
    "ONE_TO_ONE": "Một đơn – một giao dịch",
    "MANY_ORDERS_ONE_BANK": "Nhiều đơn – một giao dịch",
    "ONE_ORDER_MANY_BANKS": "Một đơn – nhiều giao dịch",
    "MANY_TO_MANY": "Nhiều đơn – nhiều giao dịch",
}
REASON_CODE = {
    "AMBIGUOUS_CANDIDATES": "Có nhiều phương án đối chiếu",
    "COMPLEX_MANY_TO_MANY_REVIEW": "Quan hệ nhiều–nhiều cần kiểm tra",
    "CURRENCY_MISMATCH": "Khác loại tiền",
    "DEBIT_EXCLUDED": "Giao dịch tiền ra không tham gia đối chiếu thu tiền",
    "NO_CONFIRMED_RECEIPT": "Chưa tìm thấy giao dịch thanh toán đủ bằng chứng",
    "ORPHAN_BANK": "Chưa tìm thấy đơn hàng tương ứng",
    "OVERPAY_RESIDUAL": "Còn tiền nhận chưa phân bổ sau khi đơn hàng đã đủ",
    "PARTIAL_PAYMENT": "Thanh toán chưa đủ",
    "PARTIAL_SEARCH_EXHAUSTED": "Giới hạn tìm kiếm đã đạt, cần kiểm tra",
    "POSSIBLE_REIMPORT": "Có khả năng nhập lặp",
    "PROPOSED_BANK": "Có đề xuất đối chiếu nhưng chưa xác nhận",
    "REFERENCE_COLLISION": "Mã tham chiếu trùng nhiều bản ghi",
}


def safe_excel_value(value: Any) -> Any:
    """Force user-origin formula prefixes to remain text in spreadsheet clients."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _safe_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: safe_excel_value(value) for key, value in row.items()}


def _as_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _joined(values: Any) -> str:
    if not values:
        return ""
    return ", ".join(str(value) for value in values)


def _format_integer_vi(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _display_datetime(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return str(value)
    return parsed.strftime("%d/%m/%Y %H:%M")


def _reason_text(values: list[str]) -> str:
    return " · ".join(REASON_CODE.get(value, value) for value in values)


def _source_columns(
    row: dict[str, Any],
    file_meta: dict[str, Any],
) -> dict[str, Any]:
    lineage = row.get("lineage") or {}
    return {
        "Tệp nguồn": file_meta.get("name", ""),
        "Trang tính nguồn": file_meta.get("sheet", ""),
        "Dòng nguồn": lineage.get("source_row_number"),
        "Mã kiểm tra dòng": lineage.get("source_row_hash", ""),
        "Mã tệp nguồn": lineage.get("source_file_id", ""),
    }


def _order_rows(
    result: dict[str, Any],
    source_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    allocated: dict[str, int] = {}
    adjustments: dict[str, int] = {}
    for edge in result.get("allocations", []):
        allocated[edge["order_id"]] = allocated.get(edge["order_id"], 0) + edge["allocated_cash_minor"]
    for adjustment in result.get("adjustments", []):
        adjustments[adjustment["order_id"]] = adjustments.get(adjustment["order_id"], 0) + adjustment["amount_minor"]
    file_meta = source_manifest.get("files", {}).get("orders", {})
    rows = []
    for item in result.get("orders", []):
        order_id = item["order_id"]
        rows.append(
            _safe_row(
                {
                    "Mã đơn hàng": order_id,
                    "Ngày phát sinh": _as_date(item.get("ordered_at")),
                    "Số tiền cần thu": item.get("expected_amount_minor", 0),
                    "Tiền đã nhận và phân bổ": allocated.get(order_id, 0),
                    "Điều chỉnh đã xác minh": adjustments.get(order_id, 0),
                    "Số tiền còn phải thu": result.get("order_outstanding_minor", {}).get(order_id, 0),
                    "Trạng thái thanh toán": PAYMENT_STATUS.get(
                        result.get("payment_statuses", {}).get(order_id, ""),
                        result.get("payment_statuses", {}).get(order_id, ""),
                    ),
                    "Trạng thái đơn hàng": ORDER_STATUS.get(item.get("order_status", ""), item.get("order_status", "")),
                    "Loại tiền": item.get("currency", ""),
                    "Mã tham chiếu": item.get("external_ref", ""),
                    "Mã khách hàng": item.get("customer_id", ""),
                    "Tên khách hàng": item.get("customer_name", ""),
                    "Kênh thanh toán": item.get("payment_channel", ""),
                    "Mã lô": item.get("batch_ref", ""),
                    "Mô tả": item.get("description", ""),
                }
                | _source_columns(item, file_meta)
            )
        )
    return rows


def _bank_rows(
    result: dict[str, Any],
    source_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    allocated: dict[str, int] = {}
    for edge in result.get("allocations", []):
        allocated[edge["bank_txn_id"]] = allocated.get(edge["bank_txn_id"], 0) + edge["allocated_cash_minor"]
    file_meta = source_manifest.get("files", {}).get("bank", {})
    rows = []
    for item in result.get("bank_transactions", []):
        bank_id = item["bank_txn_id"]
        rows.append(
            _safe_row(
                {
                    "Mã giao dịch": bank_id,
                    "Mã tham chiếu": item.get("txn_ref", ""),
                    "Ngày giao dịch": _as_date(item.get("txn_date")),
                    "Ngày giá trị": _as_date(item.get("value_date")),
                    "Chiều giao dịch": {"CREDIT": "Tiền vào", "DEBIT": "Tiền ra"}.get(
                        item.get("direction", ""), item.get("direction", "")
                    ),
                    "Số tiền ghi nhận": item.get("posted_amount_minor", 0),
                    "Tiền đã phân bổ": allocated.get(bank_id, 0),
                    "Tiền chưa phân bổ": result.get("bank_unapplied_minor", {}).get(bank_id, 0),
                    "Cơ sở số tiền": AMOUNT_BASIS.get(item.get("amount_basis", ""), item.get("amount_basis", "")),
                    "Loại tiền": item.get("currency", ""),
                    "Nội dung": item.get("description", ""),
                    "Người chuyển": item.get("sender_name", ""),
                    "Kênh": item.get("channel", ""),
                    "Mã lô": item.get("batch_ref", ""),
                    "Phí khai báo": item.get("declared_fee_minor"),
                }
                | _source_columns(item, file_meta)
            )
        )
    return rows


def _group_row(item: dict[str, Any]) -> dict[str, Any]:
    evidence = item.get("evidence") or {}
    reason_codes = evidence.get("reason_codes") or []
    statuses = item.get("payment_statuses") or {}
    return _safe_row(
        {
            "Mã nhóm": item.get("group_id", ""),
            "Kiểu quan hệ": GROUP_TYPE.get(item.get("group_type", ""), item.get("group_type", "")),
            "Mã đơn hàng": _joined(item.get("order_ids")),
            "Mã giao dịch": _joined(item.get("bank_txn_ids")),
            "Trạng thái liên kết": LINK_STATUS.get(item.get("link_status", ""), item.get("link_status", "")),
            "Trạng thái thanh toán": " · ".join(
                f"{key}: {PAYMENT_STATUS.get(value, value)}" for key, value in statuses.items()
            ),
            "Phương pháp đối chiếu": evidence.get("rule_id", ""),
            "Phiên bản quy tắc": evidence.get("rule_version", ""),
            "Giải thích": evidence.get("explanation_vi", ""),
            "Lý do": _reason_text(reason_codes),
            "Mã lý do kỹ thuật": _joined(reason_codes),
            "Tham chiếu tìm thấy": _joined(evidence.get("reference_hits")),
            "Chênh lệch số tiền": evidence.get("amount_delta_minor"),
            "Chênh lệch ngày": evidence.get("date_delta_days"),
            "Điểm tương đồng": evidence.get("score"),
        }
    )


def _allocation_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _safe_row(
            {
                "Mã phân bổ": item.get("edge_id", ""),
                "Mã nhóm": item.get("group_id", ""),
                "Mã đơn hàng": item.get("order_id", ""),
                "Mã giao dịch": item.get("bank_txn_id", ""),
                "Số tiền phân bổ": item.get("allocated_cash_minor", 0),
                "Loại tiền": item.get("currency", ""),
            }
        )
        for item in result.get("allocations", [])
    ]


def _exception_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _safe_row(
            {
                "Mã trường hợp": item.get("exception_id", ""),
                "Lý do cần kiểm tra": _reason_text(item.get("reason_codes") or []),
                "Mã đơn hàng": _joined(item.get("order_ids")),
                "Mã giao dịch": _joined(item.get("bank_txn_ids")),
                "Giá trị cần kiểm tra": item.get("risk_amount_minor", 0),
                "Mã lý do kỹ thuật": _joined(item.get("reason_codes")),
            }
        )
        for item in result.get("exceptions", [])
    ]


def _flatten_manifest(value: Any, prefix: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_flatten_manifest(child, path))
    elif isinstance(value, list):
        rows.append({"Thông tin": prefix, "Giá trị": _joined(value)})
    else:
        rows.append({"Thông tin": prefix, "Giá trị": safe_excel_value(value)})
    return rows


def _write_overview(
    writer: pd.ExcelWriter,
    run_id: str,
    result: dict[str, Any],
    revision: int,
    run_metadata: dict[str, Any],
) -> None:
    workbook = writer.book
    worksheet = workbook.add_worksheet(SHEET_NAMES[0])
    writer.sheets[SHEET_NAMES[0]] = worksheet
    title = workbook.add_format(
        {"font_name": "Segoe UI", "font_size": 16, "bold": True, "font_color": "#FFFFFF", "bg_color": "#103C2E"}
    )
    section = workbook.add_format(
        {"font_name": "Segoe UI", "font_size": 11, "bold": True, "font_color": "#FFFFFF", "bg_color": "#176B4D"}
    )
    label = workbook.add_format({"font_name": "Segoe UI", "bold": True, "font_color": "#44534C"})
    text = workbook.add_format({"font_name": "Segoe UI", "font_color": "#17231E"})
    money = workbook.add_format({"font_name": "Segoe UI", "num_format": "#,##0;[Red](#,##0);-"})
    integer = workbook.add_format({"font_name": "Segoe UI", "num_format": "#,##0"})
    good = workbook.add_format({"font_name": "Segoe UI", "bold": True, "font_color": "#176B4D", "bg_color": "#E7F3ED"})
    bad = workbook.add_format({"font_name": "Segoe UI", "bold": True, "font_color": "#A83F38", "bg_color": "#FCEDEB"})
    wrap = workbook.add_format({"font_name": "Segoe UI", "text_wrap": True, "valign": "top"})

    worksheet.merge_range("A1:F1", "BÁO CÁO ĐỐI SOÁT TÀI CHÍNH", title)
    metadata = [
        ("Mã phiên đối soát", run_id),
        ("Lần sửa dữ liệu", revision),
        (
            "Thời điểm hoàn thành",
            _display_datetime(run_metadata.get("completed_at") or run_metadata.get("created_at") or datetime.now(UTC)),
        ),
        ("Loại tiền", result.get("kpis", {}).get("currency", run_metadata.get("currency", ""))),
        ("Số đơn hàng", len(result.get("orders", []))),
        ("Số giao dịch thanh toán", len(result.get("bank_transactions", []))),
    ]
    for row_index, (name, value) in enumerate(metadata, start=2):
        worksheet.write(row_index, 0, name, label)
        worksheet.write(row_index, 1, safe_excel_value(value), text)

    worksheet.merge_range("A10:F10", "CÁC CHỈ SỐ CHÍNH", section)
    kpis = result.get("kpis", {})
    metrics = [
        ("Tổng số tiền cần thu", kpis.get("expected_receivable_minor", 0), "Tổng giá trị đơn hàng đủ điều kiện."),
        (
            "Tiền đã nhận và đối chiếu thành công",
            kpis.get("confirmed_cash_allocated_minor", 0),
            "Chỉ gồm phân bổ đã xác nhận.",
        ),
        (
            "Điều chỉnh đã xác minh",
            kpis.get("verified_adjustments_minor", 0),
            "Khoản phi tiền mặt có bằng chứng, ví dụ phí PSP khai báo.",
        ),
        (
            "Số tiền chưa được xác nhận đã thu",
            kpis.get("outstanding_receivable_minor", 0),
            "Tổng phải thu trừ tiền đã phân bổ và điều chỉnh.",
        ),
        (
            "Tiền đã nhận nhưng chưa xác định được đơn hàng",
            kpis.get("unapplied_bank_credit_minor", 0),
            "Tiền vào đủ điều kiện nhưng chưa phân bổ.",
        ),
        (
            "Đơn hàng đã xác nhận thanh toán đủ",
            kpis.get("fully_settled_orders_count", 0),
            "Số đơn có số còn phải thu bằng 0.",
        ),
        (
            "Trường hợp cần kiểm tra",
            kpis.get("unresolved_exceptions_count", 0),
            "Các trường hợp chưa đủ bằng chứng hoặc còn chênh lệch.",
        ),
    ]
    worksheet.write_row(10, 0, ["Chỉ số", "Giá trị", "Cách hiểu"], section)
    for row_index, (name, value, explanation) in enumerate(metrics, start=11):
        worksheet.write(row_index, 0, name, text)
        worksheet.write_number(row_index, 1, value, money if "tiền" in name.lower() else integer)
        worksheet.write(row_index, 2, explanation, wrap)

    expected = int(kpis.get("expected_receivable_minor", 0))
    allocated = int(kpis.get("confirmed_cash_allocated_minor", 0))
    adjustments = int(kpis.get("verified_adjustments_minor", 0))
    outstanding = int(kpis.get("outstanding_receivable_minor", 0))
    worksheet.merge_range("A20:F20", "KIỂM TRA BẢO TOÀN TIỀN", section)
    worksheet.write(20, 0, "Phương trình phải thu", label)
    worksheet.write(
        20,
        1,
        (
            f"{_format_integer_vi(expected)} = {_format_integer_vi(allocated)} tiền đã nhận + "
            f"{_format_integer_vi(adjustments)} điều chỉnh đã xác minh + "
            f"{_format_integer_vi(outstanding)} còn phải thu"
        ),
        text,
    )
    bridge_valid = expected == allocated + adjustments + outstanding
    worksheet.write(21, 0, "Kết quả phương trình", label)
    worksheet.write(21, 1, "Khớp chính xác" if bridge_valid else "Chưa khớp", good if bridge_valid else bad)
    conservation = result.get("conservation", {})
    worksheet.write(22, 0, "Bất biến phân bổ", label)
    worksheet.write(
        22,
        1,
        "Đạt — không phân bổ trùng hoặc mất chênh lệch"
        if conservation.get("is_valid", True)
        else f"Không đạt — {_joined(conservation.get('violations'))}",
        good if conservation.get("is_valid", True) else bad,
    )
    worksheet.set_column("A:A", 40)
    worksheet.set_column("B:B", 32)
    worksheet.set_column("C:F", 24)
    worksheet.set_row(0, 25)
    worksheet.freeze_panes(10, 0)
    worksheet.hide_gridlines(2)


def _write_table_sheet(
    writer: pd.ExcelWriter,
    sheet_name: str,
    rows: list[dict[str, Any]],
    columns: list[str],
) -> None:
    frame = pd.DataFrame(rows, columns=columns)
    frame.to_excel(writer, sheet_name=sheet_name, index=False)
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]
    header = workbook.add_format(
        {
            "font_name": "Segoe UI",
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#176B4D",
            "text_wrap": True,
            "valign": "vcenter",
            "border": 0,
        }
    )
    money = workbook.add_format({"font_name": "Segoe UI", "num_format": "#,##0;[Red](#,##0);-"})
    date_format = workbook.add_format({"font_name": "Segoe UI", "num_format": "dd/mm/yyyy"})
    text = workbook.add_format({"font_name": "Segoe UI"})
    for column_index, column in enumerate(columns):
        worksheet.write(0, column_index, column, header)
        values = frame[column].head(200) if column in frame else []
        width = min(52, max(len(column) + 2, max((len(str(value)) for value in values), default=0) + 2))
        cell_format = text
        if any(word in column for word in ("Số tiền", "Tiền ", "Giá trị", "Phí", "Chênh lệch số tiền")):
            cell_format = money
        elif column.startswith("Ngày"):
            cell_format = date_format
        worksheet.set_column(column_index, column_index, width, cell_format)
    worksheet.set_row(0, 30)
    worksheet.freeze_panes(1, 0)
    worksheet.autofilter(0, 0, max(len(frame), 1), max(len(columns) - 1, 0))
    worksheet.hide_gridlines(2)
    if "Trạng thái liên kết" in columns and len(frame) > 0:
        status_column = columns.index("Trạng thái liên kết")
        worksheet.conditional_format(
            1,
            status_column,
            len(frame),
            status_column,
            {
                "type": "text",
                "criteria": "containing",
                "value": "Đã xác nhận",
                "format": workbook.add_format({"bg_color": "#E7F3ED", "font_color": "#176B4D"}),
            },
        )
        worksheet.conditional_format(
            1,
            status_column,
            len(frame),
            status_column,
            {
                "type": "text",
                "criteria": "containing",
                "value": "Đề xuất",
                "format": workbook.add_format({"bg_color": "#FFF5DF", "font_color": "#8A5008"}),
            },
        )


def create_excel_export(
    run_id: str,
    result: dict[str, Any],
    revision: int = 0,
    *,
    run_metadata: dict[str, Any] | None = None,
    source_manifest: dict[str, Any] | None = None,
) -> Path:
    """Generate a readable run-scoped workbook without formula-based business logic."""
    output = run_directory(run_id) / "exports" / f"reconciliation-r{revision}.xlsx"
    output.parent.mkdir(parents=True, exist_ok=True)
    run_metadata = run_metadata or {}
    source_manifest = source_manifest or {}
    manifest_path = run_directory(run_id) / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest_payload = {
        "Thông tin phiên": {
            "run_id": run_id,
            "effective_revision": revision,
            "status": run_metadata.get("status"),
            "currency": run_metadata.get("currency"),
            "created_at": run_metadata.get("created_at"),
            "completed_at": run_metadata.get("completed_at"),
        },
        "Định danh kết quả": manifest,
        "Nguồn dữ liệu": source_manifest,
        "Chính sách": run_metadata.get("policy_snapshot", {}),
        "Ánh xạ": run_metadata.get("mapping_snapshot", {}),
    }

    confirmed_groups = [_group_row(item) for item in result.get("groups", []) if item.get("link_status") == "CONFIRMED"]
    proposed_groups = [_group_row(item) for item in result.get("groups", []) if item.get("link_status") == "PROPOSED"]
    tables: list[tuple[str, list[dict[str, Any]], list[str]]] = [
        (
            "02_Orders",
            _order_rows(result, source_manifest),
            [
                "Mã đơn hàng",
                "Ngày phát sinh",
                "Số tiền cần thu",
                "Tiền đã nhận và phân bổ",
                "Điều chỉnh đã xác minh",
                "Số tiền còn phải thu",
                "Trạng thái thanh toán",
                "Trạng thái đơn hàng",
                "Loại tiền",
                "Mã tham chiếu",
                "Mã khách hàng",
                "Tên khách hàng",
                "Kênh thanh toán",
                "Mã lô",
                "Mô tả",
                "Tệp nguồn",
                "Trang tính nguồn",
                "Dòng nguồn",
                "Mã kiểm tra dòng",
                "Mã tệp nguồn",
            ],
        ),
        (
            "03_BankTransactions",
            _bank_rows(result, source_manifest),
            [
                "Mã giao dịch",
                "Mã tham chiếu",
                "Ngày giao dịch",
                "Ngày giá trị",
                "Chiều giao dịch",
                "Số tiền ghi nhận",
                "Tiền đã phân bổ",
                "Tiền chưa phân bổ",
                "Cơ sở số tiền",
                "Loại tiền",
                "Nội dung",
                "Người chuyển",
                "Kênh",
                "Mã lô",
                "Phí khai báo",
                "Tệp nguồn",
                "Trang tính nguồn",
                "Dòng nguồn",
                "Mã kiểm tra dòng",
                "Mã tệp nguồn",
            ],
        ),
        ("04_ConfirmedGroups", confirmed_groups, list(_group_row({}).keys())),
        (
            "05_AllocationEdges",
            _allocation_rows(result),
            ["Mã phân bổ", "Mã nhóm", "Mã đơn hàng", "Mã giao dịch", "Số tiền phân bổ", "Loại tiền"],
        ),
        ("06_ReviewQueue", proposed_groups, list(_group_row({}).keys())),
        (
            "07_Exceptions_Orphans",
            _exception_rows(result),
            [
                "Mã trường hợp",
                "Lý do cần kiểm tra",
                "Mã đơn hàng",
                "Mã giao dịch",
                "Giá trị cần kiểm tra",
                "Mã lý do kỹ thuật",
            ],
        ),
        (
            "08_ReviewAudit",
            [
                {
                    "Thời điểm": "",
                    "Hành động": "Chưa có thao tác đánh giá trong phạm vi hiện tại",
                    "Mã đối tượng": "",
                    "Ghi chú": "",
                }
            ],
            ["Thời điểm", "Hành động", "Mã đối tượng", "Ghi chú"],
        ),
        ("09_RunManifest", _flatten_manifest(manifest_payload), ["Thông tin", "Giá trị"]),
    ]

    with pd.ExcelWriter(
        output,
        engine="xlsxwriter",
        date_format="dd/mm/yyyy",
        datetime_format="dd/mm/yyyy hh:mm",
        engine_kwargs={"options": {"strings_to_formulas": False, "strings_to_urls": False}},
    ) as writer:
        _write_overview(writer, run_id, result, revision, run_metadata)
        for sheet_name, rows, columns in tables:
            _write_table_sheet(writer, sheet_name, rows, columns)
    return output
