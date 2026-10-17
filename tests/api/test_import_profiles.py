from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.smartrecon_api.config import get_settings
from backend.smartrecon_api.db.database import Base, get_db
from backend.smartrecon_api.main import app

ORDERS = b"order_id,ordered_at,expected_amount\nO-1,2026-10-17,1000\n"
BANK = b"bank_txn_id,txn_date,posted_amount,direction,amount_basis\nB-1,2026-10-18,1000,CREDIT,POSTED_CASH\n"


def _inspect(client: TestClient, orders: bytes = ORDERS) -> dict:
    response = client.post(
        "/api/uploads/inspect",
        files={
            "orders_file": ("orders.csv", orders, "text/csv"),
            "bank_file": ("bank.csv", BANK, "text/csv"),
        },
    )
    assert response.status_code == 200
    return response.json()


def test_import_profile_crud_reuse_and_schema_drift_protection(tmp_path: Path, monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)

    def test_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    monkeypatch.setattr(get_settings(), "artifacts_path", tmp_path / "artifacts")
    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as client:
            inspection = _inspect(client)
            assert inspection["import_profile"]["applied"] is False
            mapping = {
                **inspection["suggested_mapping"],
                "currency": "VND",
                "date_format": "%Y-%m-%d",
                "decimal_separator": ".",
                "thousand_separator": ",",
                "order_defaults": {"order_status": "ELIGIBLE"},
                "bank_defaults": {},
            }
            preview = client.post(
                f"/api/uploads/{inspection['session_id']}/preview",
                json=mapping,
            )
            assert preview.status_code == 200
            assert preview.json()["status"] == "READY"
            assert preview.json()["orders"][0]["order_id"] == "O-1"
            assert preview.json()["bank_transactions"][0]["posted_amount_minor"] == 1000
            confirmed = client.post(
                f"/api/uploads/{inspection['session_id']}/mapping",
                json=mapping,
            )
            assert confirmed.status_code == 200
            orders_csv = client.get(f"/api/uploads/{inspection['session_id']}/normalized/orders.csv")
            bank_csv = client.get(f"/api/uploads/{inspection['session_id']}/normalized/bank_transactions.csv")
            assert orders_csv.status_code == 200
            assert "source_row_number" in orders_csv.text
            assert "O-1" in orders_csv.text
            assert bank_csv.status_code == 200
            assert "B-1" in bank_csv.text

            created = client.post(
                "/api/import-profiles",
                json={"session_id": inspection["session_id"], "name": "Sao kê chuẩn"},
            )
            assert created.status_code == 201
            profile = created.json()
            assert profile["mapping_snapshot"]["bank_columns"]["posted_amount"] == "posted_amount"

            listed = client.get("/api/import-profiles")
            assert listed.status_code == 200
            assert [item["id"] for item in listed.json()] == [profile["id"]]

            reused = _inspect(client)
            assert reused["import_profile"]["applied"] is True
            saved = reused["import_profile"]["saved_profile"]
            assert saved["id"] == profile["id"]
            assert saved["mapping_snapshot"]["import_profile_id"] == profile["id"]
            assert reused["suggested_mapping"] == inspection["suggested_mapping"]

            renamed = client.patch(
                f"/api/import-profiles/{profile['id']}",
                json={"name": "Sao kê ngân hàng A"},
            )
            assert renamed.status_code == 200
            assert renamed.json()["name"] == "Sao kê ngân hàng A"

            drifted = _inspect(
                client,
                b"order_id,ordered_at,amount_due\nO-1,2026-10-17,1000\n",
            )
            assert drifted["import_profile"]["applied"] is False
            assert drifted["import_profile"]["saved_profile"] is None

            deleted = client.delete(f"/api/import-profiles/{profile['id']}")
            assert deleted.status_code == 204
            assert client.get("/api/import-profiles").json() == []
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()
