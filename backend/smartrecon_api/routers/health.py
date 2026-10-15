"""Container and dependency health endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.smartrecon_api.db.database import get_db

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthcheck(db: Session = Depends(get_db)) -> dict[str, str]:
    """Report readiness only when PostgreSQL is reachable."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_code": "DATABASE_UNAVAILABLE", "message": "PostgreSQL chưa sẵn sàng."},
        ) from exc
    return {"status": "ok", "database": "ok"}
