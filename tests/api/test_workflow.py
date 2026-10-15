from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import load_workbook

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

    workbook = load_workbook(export_path, data_only=False, read_only=True)
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
    cash_column = headers.index("allocated_cash_minor") + 1
    exported_cash = sum(
        int(row[0] or 0)
        for row in edge_sheet.iter_rows(min_row=2, min_col=cash_column, max_col=cash_column, values_only=True)
    )
    assert exported_cash == summary["kpis"]["confirmed_cash_allocated_minor"]
