from collections.abc import Generator
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.smartrecon_api.config import get_settings
from backend.smartrecon_api.db.database import get_db
from backend.smartrecon_api.main import app

ORDERS = b"order_id,ordered_at,expected_amount\nO1,2026-01-01,100000\n"
BANK = b"bank_txn_id,txn_date,posted_amount,direction,amount_basis\nB1,2026-01-01,100000,CREDIT,POSTED_CASH\n"


def _mock_db() -> Generator[Mock, None, None]:
    yield Mock(spec=Session)


def test_upload_uses_server_names_even_when_client_filename_contains_traversal(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setattr(get_settings(), "artifacts_path", artifact_root)
    app.dependency_overrides[get_db] = _mock_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/uploads/inspect",
                files={
                    "orders_file": ("../../escaped.csv", ORDERS, "text/csv"),
                    "bank_file": ("..\\escaped.csv", BANK, "text/csv"),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    session_id = response.json()["session_id"]
    session_directory = artifact_root / "uploads" / session_id
    assert {path.name for path in session_directory.iterdir()} == {"orders.csv", "bank.csv"}
    assert not (tmp_path / "escaped.csv").exists()


def test_upload_rejects_unsupported_extension_and_content_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "artifacts_path", tmp_path / "artifacts")
    app.dependency_overrides[get_db] = _mock_db
    try:
        with TestClient(app) as client:
            extension = client.post(
                "/api/uploads/inspect",
                files={
                    "orders_file": ("orders.exe", ORDERS, "application/octet-stream"),
                    "bank_file": ("bank.csv", BANK, "text/csv"),
                },
            )
            content_type = client.post(
                "/api/uploads/inspect",
                files={
                    "orders_file": ("orders.csv", ORDERS, "text/html"),
                    "bank_file": ("bank.csv", BANK, "text/csv"),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert extension.status_code == 400
    assert extension.json()["detail"]["error_code"] == "INVALID_UPLOAD"
    assert content_type.status_code == 400
    assert content_type.json()["detail"]["error_code"] == "INVALID_UPLOAD"
