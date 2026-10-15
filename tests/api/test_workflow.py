from collections.abc import Generator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from backend.smartrecon_api.config import get_settings
from backend.smartrecon_api.db.database import get_db
from backend.smartrecon_api.db.models import ReconciliationRun, UploadSession
from backend.smartrecon_api.main import app


class MemorySession:
    """Small Session test double; PostgreSQL behavior is covered by Docker acceptance."""

    def __init__(self) -> None:
        self.objects: dict[tuple[type, str], object] = {}

    def add(self, value: object) -> None:
        identifier = getattr(value, "id", None)
        if isinstance(identifier, str):
            self.objects[(type(value), identifier)] = value

    def get(self, model: type, identifier: str):
        return self.objects.get((model, identifier))

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        return None

    def refresh(self, value: object) -> None:
        return None

    def scalar(self, statement: object):
        return None


def _xlsx_upload(headers: list[str], values: list[object]) -> bytes:
    output = BytesIO()
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(headers)
    worksheet.append(values)
    workbook.save(output)
    workbook.close()
    return output.getvalue()


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_fractional_vnd_health_detail_preserves_source_context(
    tmp_path: Path,
    monkeypatch,
    suffix: str,
) -> None:
    session = MemorySession()

    def test_db() -> Generator[MemorySession, None, None]:
        yield session

    if suffix == ".csv":
        orders_content = b"order_id,ordered_at,expected_amount\nO1,2026-01-01,100000.5\n"
        bank_content = (
            b"bank_txn_id,txn_date,posted_amount,direction,amount_basis\nB1,2026-01-01,100000,CREDIT,POSTED_CASH\n"
        )
        content_type = "text/csv"
    else:
        orders_content = _xlsx_upload(
            ["order_id", "ordered_at", "expected_amount"],
            ["O1", "2026-01-01", "100000.5"],
        )
        bank_content = _xlsx_upload(
            ["bank_txn_id", "txn_date", "posted_amount", "direction", "amount_basis"],
            ["B1", "2026-01-01", "100000", "CREDIT", "POSTED_CASH"],
        )
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    monkeypatch.setattr(get_settings(), "artifacts_path", tmp_path / "artifacts")
    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as client:
            inspection_response = client.post(
                "/api/uploads/inspect",
                files={
                    "orders_file": (f"receivables{suffix}", orders_content, content_type),
                    "bank_file": (f"payments{suffix}", bank_content, content_type),
                },
            )
            assert inspection_response.status_code == 200
            inspection = inspection_response.json()
            mapping = {
                "order_columns": {
                    "order_id": "order_id",
                    "ordered_at": "ordered_at",
                    "expected_amount": "expected_amount",
                },
                "bank_columns": {
                    "bank_txn_id": "bank_txn_id",
                    "txn_date": "txn_date",
                    "posted_amount": "posted_amount",
                    "direction": "direction",
                    "amount_basis": "amount_basis",
                },
                "currency": "VND",
                "source_profile": "BANK_CREDIT",
                "date_format": "%Y-%m-%d",
                "decimal_separator": ".",
                "thousand_separator": ",",
                "order_defaults": {"order_status": "ELIGIBLE"},
                "bank_defaults": {},
            }
            gate_response = client.post(
                f"/api/uploads/{inspection['session_id']}/mapping",
                json=mapping,
            )
            assert gate_response.status_code == 200
            gate = gate_response.json()
            assert gate["status"] == "HEALTH_BLOCKED"
            assert gate["report"]["status"] == "BLOCKED"
            issue_index = next(
                index for index, issue in enumerate(gate["report"]["issues"]) if issue["code"] == "ORDER_PARSE_ERROR"
            )
            detail_response = client.get(f"/api/uploads/{inspection['session_id']}/health/issues/{issue_index}")
            assert detail_response.status_code == 200
            detail = detail_response.json()
            assert detail["severity"] == "BLOCKING"
            assert detail["sample_values"] == ["100000.5"]
            assert detail["rows"][0]["source_filename"] == f"orders{suffix}"
            assert detail["rows"][0]["source_row_number"] == 2
            assert detail["rows"][0]["raw_values"]["expected_amount"] == "100000.5"
            assert detail["rows"][0]["sheet_name"] == ("Sheet" if suffix == ".xlsx" else None)
    finally:
        app.dependency_overrides.clear()


def test_demo_to_export_uses_one_persisted_run(tmp_path: Path, monkeypatch) -> None:
    session = MemorySession()

    def test_db() -> Generator[MemorySession, None, None]:
        yield session

    monkeypatch.setattr(get_settings(), "artifacts_path", tmp_path / "artifacts")
    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as client:
            demo = client.post("/api/demo/datasets")
            assert demo.status_code == 200
            inspection = demo.json()
            assert "truth" not in demo.text.lower()

            mapping = {
                **inspection["suggested_mapping"],
                "currency": "VND",
                "source_profile": "BANK_CREDIT",
                "date_format": "%Y-%m-%d",
                "decimal_separator": ".",
                "thousand_separator": ",",
                "order_defaults": {"order_status": "ELIGIBLE"},
                "bank_defaults": {},
            }
            gate = client.post(f"/api/uploads/{inspection['session_id']}/mapping", json=mapping)
            assert gate.status_code == 200
            assert gate.json()["report"]["status"] == "READY"
            duplicate_index = next(
                index
                for index, issue in enumerate(gate.json()["report"]["issues"])
                if issue["code"] == "POSSIBLE_REIMPORT"
            )
            detail = client.get(f"/api/uploads/{inspection['session_id']}/health/issues/{duplicate_index}")
            assert detail.status_code == 200
            assert detail.json()["code"] == "POSSIBLE_REIMPORT"
            assert len(detail.json()["rows"]) == 2
            assert all(row["source_filename"] == "bank.csv" for row in detail.json()["rows"])
            assert client.get(f"/api/uploads/{inspection['session_id']}/health/issues/999").status_code == 404
            unchanged = client.get(f"/api/uploads/{inspection['session_id']}/health")
            assert unchanged.json()["report"] == gate.json()["report"]

            warning_codes = [
                issue["code"] for issue in gate.json()["report"]["issues"] if issue["severity"] == "WARNING"
            ]
            resolution = client.post(
                f"/api/uploads/{inspection['session_id']}/resolutions",
                json={"exclusions": [], "acknowledged_issue_codes": warning_codes},
            )
            assert resolution.status_code == 200
            assert resolution.json()["acknowledged_issue_codes"] == warning_codes

            invalid_feed = client.post(
                f"/api/uploads/{inspection['session_id']}/resolutions",
                json={"exclusions": [{"feed": "unknown", "source_row_number": 2, "reason": "Không hợp lệ"}]},
            )
            assert invalid_feed.status_code == 422
            missing_row = client.post(
                f"/api/uploads/{inspection['session_id']}/resolutions",
                json={"exclusions": [{"feed": "orders", "source_row_number": 999999, "reason": "Dòng không tồn tại"}]},
            )
            assert missing_row.status_code == 422

            created = client.post(
                "/api/runs",
                json={"upload_session_id": inspection["session_id"], "policy": {"currency": "VND"}},
            )
            assert created.status_code == 200
            run_id = created.json()["run_id"]
            repeated = client.post(
                "/api/runs",
                json={
                    "upload_session_id": inspection["session_id"],
                    "policy": {"currency": "VND", "fuzzy_candidate_threshold": 85},
                },
            )
            assert repeated.status_code == 200
            assert repeated.json()["semantic_checksum"] == created.json()["semantic_checksum"]
            dashboard = client.get(f"/api/runs/{run_id}/dashboard")
            assert dashboard.status_code == 200
            summary = dashboard.json()
            assert summary["conservation"]["is_valid"] is True
            assert summary["conservation"]["violations"] == []

            groups = client.get(f"/api/runs/{run_id}/groups?page_size=200")
            orders = client.get(f"/api/runs/{run_id}/orders?page_size=200")
            banks = client.get(f"/api/runs/{run_id}/bank-transactions?page_size=200")
            assert groups.json()["total"] > 0
            assert orders.json()["total"] == 100
            assert banks.json()["total"] == 98

            one_to_one = client.get(f"/api/runs/{run_id}/orders/ORD00001")
            assert one_to_one.status_code == 200
            one_to_one_detail = one_to_one.json()
            assert one_to_one_detail["overview"]["link_status"] == "CONFIRMED"
            assert one_to_one_detail["overview"]["relationship_types"] == ["ONE_TO_ONE"]
            assert one_to_one_detail["orders"][0]["source"]["filename"] == "orders.csv"
            assert one_to_one_detail["orders"][0]["source"]["row_number"] == 2
            assert one_to_one_detail["orders"][0]["source"]["raw_values"]["order_id"] == "ORD00001"
            assert one_to_one_detail["bank_transactions"][0]["source"]["filename"] == "bank.csv"

            many_to_one = client.get(f"/api/runs/{run_id}/orders/ORD00007").json()
            assert {item["order_id"] for item in many_to_one["orders"]} == {"ORD00007", "ORD00008"}
            assert len(many_to_one["bank_transactions"]) == 1
            assert len(many_to_one["allocations"]) == 2
            assert many_to_one["overview"]["relationship_types"] == ["MANY_ORDERS_ONE_BANK"]

            one_to_many = client.get(f"/api/runs/{run_id}/orders/ORD00011").json()
            assert len(one_to_many["orders"]) == 1
            assert {item["bank_txn_id"] for item in one_to_many["bank_transactions"]} == {
                "TXN00008",
                "TXN00009",
            }
            assert len(one_to_many["allocations"]) == 2

            partial = client.get(f"/api/runs/{run_id}/orders/ORD00012").json()
            assert partial["overview"]["outstanding_minor"] == 10_000
            assert "chưa đủ" in partial["guidance_vi"].lower()

            overpayment = client.get(f"/api/runs/{run_id}/orders/ORD00013").json()
            assert overpayment["overview"]["unapplied_minor"] == 20_000
            assert "chưa phân bổ" in overpayment["guidance_vi"].lower()

            proposal = client.get(f"/api/runs/{run_id}/orders/ORD00004").json()
            assert proposal["overview"]["link_status"] == "PROPOSED"
            assert proposal["allocations"] == []
            assert proposal["candidates"]

            orphan_order = client.get(f"/api/runs/{run_id}/orders/ORD00014").json()
            assert orphan_order["bank_transactions"] == []
            assert orphan_order["overview"]["link_status"] == "UNMATCHED"
            assert "chưa tìm thấy giao dịch thanh toán" in orphan_order["guidance_vi"].lower()

            orphan_bank = client.get(f"/api/runs/{run_id}/bank-transactions/TXN00012").json()
            assert orphan_bank["orders"] == []
            assert "chưa tìm thấy đơn hàng" in orphan_bank["guidance_vi"].lower()

            first_group = groups.json()["items"][0]
            group_detail = client.get(f"/api/runs/{run_id}/groups/{first_group['group_id']}")
            assert group_detail.status_code == 200
            assert group_detail.json()["order_records"][0]["source"]["raw_values"]

            exceptions = client.get(f"/api/runs/{run_id}/exceptions?page_size=200").json()
            exception_detail = client.get(f"/api/runs/{run_id}/exceptions/{exceptions['items'][0]['exception_id']}")
            assert exception_detail.status_code == 200
            assert (
                exception_detail.json()["selected_exception"]["exception_id"] == exceptions["items"][0]["exception_id"]
            )

            # Read-only detail remains available after reopening the persisted run.
            reopened = client.get(f"/api/runs/{run_id}/orders/ORD00001")
            assert reopened.json() == one_to_one_detail
            assert client.get(f"/api/runs/{run_id}/orders/UNKNOWN").status_code == 404

            exported = client.get(f"/api/runs/{run_id}/exports?format=xlsx")
            assert exported.status_code == 200
            export_path = tmp_path / "reconciliation.xlsx"
            export_path.write_bytes(exported.content)
    finally:
        app.dependency_overrides.clear()

    assert session.get(UploadSession, inspection["session_id"]) is not None
    assert session.get(ReconciliationRun, run_id) is not None

    workbook = load_workbook(export_path, data_only=False)
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
    edge_sheet = workbook["05_AllocationEdges"]
    headers = [cell.value for cell in next(edge_sheet.iter_rows(max_row=1))]
    cash_column = headers.index("Số tiền phân bổ") + 1
    exported_cash = sum(
        int(row[0] or 0)
        for row in edge_sheet.iter_rows(min_row=2, min_col=cash_column, max_col=cash_column, values_only=True)
    )
    assert exported_cash == summary["kpis"]["confirmed_cash_allocated_minor"]

    overview = workbook["01_TongQuan_KPI"]
    overview_values = {
        overview.cell(row=row, column=1).value: overview.cell(row=row, column=2).value
        for row in range(1, overview.max_row + 1)
    }
    assert overview_values["Tổng số tiền cần thu"] == summary["kpis"]["expected_receivable_minor"]
    assert overview_values["Điều chỉnh đã xác minh"] == 2_000
    assert "2.000 điều chỉnh đã xác minh" in overview_values["Phương trình phải thu"]

    order_sheet = workbook["02_Orders"]
    order_headers = [cell.value for cell in order_sheet[1]]
    order_rows = {row[order_headers.index("Mã đơn hàng")].value: row for row in order_sheet.iter_rows(min_row=2)}
    fee_order = order_rows["ORD00018"]
    assert fee_order[order_headers.index("Số tiền cần thu")].value == 100_000
    assert fee_order[order_headers.index("Tiền đã nhận và phân bổ")].value == 98_000
    assert fee_order[order_headers.index("Điều chỉnh đã xác minh")].value == 2_000
    assert fee_order[order_headers.index("Số tiền còn phải thu")].value == 0
    assert fee_order[order_headers.index("Tệp nguồn")].value == "orders.csv"
    assert fee_order[order_headers.index("Dòng nguồn")].value == 19
    assert order_sheet.auto_filter.ref == f"A1:U{order_sheet.max_row}"
    assert fee_order[order_headers.index("Mã giao dịch liên quan")].value == "TXN00016"
    assert order_sheet.freeze_panes == "A2"
    overpaid_order = order_rows["ORD00013"]
    assert "Đã thu đủ" in overpaid_order[order_headers.index("Trạng thái thanh toán")].value

    assert all(
        cell.data_type != "f" for worksheet in workbook.worksheets for row in worksheet.iter_rows() for cell in row
    )
    manifest_values = [cell.value for row in workbook["09_RunManifest"].iter_rows(min_row=2) for cell in row]
    assert not any(isinstance(value, str) and value.lstrip().startswith(("{", "[")) for value in manifest_values)
