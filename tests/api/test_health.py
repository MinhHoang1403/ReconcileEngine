from collections.abc import Generator
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.smartrecon_api.db.database import get_db
from backend.smartrecon_api.main import app


def _mock_db() -> Generator[Mock, None, None]:
    session = Mock(spec=Session)
    session.execute.return_value = Mock()
    yield session


def test_health_reports_database_ready() -> None:
    app.dependency_overrides[get_db] = _mock_db
    try:
        response = TestClient(app).get("/healthz")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
