"""Review queue mutations for an existing reconciliation run."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.smartrecon_api.db.database import get_db
from backend.smartrecon_api.schemas.reviews import (
    ApproveReviewRequest,
    RejectReviewRequest,
    ReviewActionResponse,
    ReviewPageResponse,
    UndoReviewRequest,
)
from backend.smartrecon_api.services.reviews import (
    ReviewServiceError,
    approve_review,
    reject_review,
    review_history,
    review_queue,
    undo_review,
)

router = APIRouter(prefix="/api/runs/{run_id}/reviews", tags=["reviews"])


def _translate_error(error: ReviewServiceError) -> HTTPException:
    detail: dict[str, Any] = {
        "error_code": error.code,
        "message": error.message,
        **error.context,
    }
    return HTTPException(status_code=error.status_code, detail=detail)


@router.get("", response_model=ReviewPageResponse)
def get_queue(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    query: str | None = Query(default=None, max_length=200),
    group_type: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return review_queue(db, run_id, page, page_size, query, group_type)
    except ReviewServiceError as error:
        raise _translate_error(error) from error


@router.get("/history", response_model=ReviewPageResponse)
def get_history(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return review_history(db, run_id, page, page_size)
    except ReviewServiceError as error:
        raise _translate_error(error) from error


@router.post("/approve", response_model=ReviewActionResponse)
def approve(
    run_id: str,
    request: ApproveReviewRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return approve_review(db, run_id, request)
    except ReviewServiceError as error:
        raise _translate_error(error) from error


@router.post("/reject", response_model=ReviewActionResponse)
def reject(
    run_id: str,
    request: RejectReviewRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return reject_review(db, run_id, request)
    except ReviewServiceError as error:
        raise _translate_error(error) from error


@router.post("/undo", response_model=ReviewActionResponse)
def undo(
    run_id: str,
    request: UndoReviewRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return undo_review(db, run_id, request)
    except ReviewServiceError as error:
        raise _translate_error(error) from error
