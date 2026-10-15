"""Run execution, dashboard, explorer, and export endpoints."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.smartrecon_api.db.database import get_db
from backend.smartrecon_api.db.models import ArtifactManifest, ReconciliationRun, UploadSession
from backend.smartrecon_api.schemas.runs import (
    DashboardResponse,
    PageResponse,
    RunCreatedResponse,
    RunDetailResponse,
    RunRequest,
)
from backend.smartrecon_api.services.artifacts import relative_artifact_path, sha256_path
from backend.smartrecon_api.services.details import entity_detail, extend_group_detail
from backend.smartrecon_api.services.exports import create_excel_export
from backend.smartrecon_api.services.runs import execute_run, load_run_result, paginate

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _run_or_404(db: Session, run_id: str) -> ReconciliationRun:
    run = db.get(ReconciliationRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "RUN_NOT_FOUND", "message": "Không tìm thấy run."},
        )
    return run


def _result_or_404(run_id: str) -> dict[str, Any]:
    try:
        return load_run_result(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "RESULT_NOT_FOUND", "message": "Run thiếu result artifact."},
        ) from exc


@router.post("", response_model=RunCreatedResponse)
def create_run(request: RunRequest, db: Session = Depends(get_db)) -> dict:
    session = db.get(UploadSession, request.upload_session_id)
    if session is None:
        raise HTTPException(status_code=404, detail={"error_code": "UPLOAD_NOT_FOUND"})
    if session.status != "HEALTH_READY":
        raise HTTPException(
            status_code=409,
            detail={"error_code": "HEALTH_BLOCKED", "message": "Health Gate chưa sẵn sàng."},
        )
    try:
        run = execute_run(db, session, request)
    except ValueError as exc:
        if str(exc) == "HEALTH_BLOCKED":
            raise HTTPException(
                status_code=409,
                detail={"error_code": "HEALTH_BLOCKED", "message": "Health Gate chưa sẵn sàng."},
            ) from exc
        raise
    return {
        "run_id": run.id,
        "status": run.status,
        "effective_revision": run.current_revision,
        "semantic_checksum": run.semantic_checksum,
    }


@router.get("/{run_id}", response_model=RunDetailResponse)
def get_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    run = _run_or_404(db, run_id)
    return {
        "run_id": run.id,
        "upload_session_id": run.upload_session_id,
        "status": run.status,
        "currency": run.currency,
        "effective_revision": run.current_revision,
        "semantic_checksum": run.semantic_checksum,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
        "policy": run.policy_snapshot,
    }


@router.get("/{run_id}/dashboard", response_model=DashboardResponse)
def get_dashboard(run_id: str, db: Session = Depends(get_db)) -> dict:
    run = _run_or_404(db, run_id)
    result = _result_or_404(run_id)
    return {
        "run_id": run.id,
        "effective_revision": run.current_revision,
        "kpis": result["kpis"],
        "layer_counts": result["layer_counts"],
        "payment_status_counts": result["kpis"]["payment_status_counts"],
        "conservation": result["conservation"],
    }


@router.get("/{run_id}/groups", response_model=PageResponse)
def get_groups(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    link_status: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    _run_or_404(db, run_id)
    groups = _result_or_404(run_id)["groups"]
    if link_status:
        groups = [item for item in groups if item["link_status"] == link_status]
    return paginate(groups, page, page_size)


@router.get("/{run_id}/groups/{group_id}")
def get_group(run_id: str, group_id: str, db: Session = Depends(get_db)) -> dict:
    run = _run_or_404(db, run_id)
    result = _result_or_404(run_id)
    session = db.get(UploadSession, run.upload_session_id)
    group = extend_group_detail(result, session, group_id) if session else None
    if group is None:
        raise HTTPException(status_code=404, detail={"error_code": "GROUP_NOT_FOUND"})
    return group


def _entity_detail_or_404(db: Session, run_id: str, entity_type: str, entity_id: str) -> dict[str, Any]:
    run = _run_or_404(db, run_id)
    session = db.get(UploadSession, run.upload_session_id)
    detail = entity_detail(_result_or_404(run_id), session, entity_type, entity_id) if session else None
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "DETAIL_NOT_FOUND", "message": "Không tìm thấy bản ghi trong phiên đối soát."},
        )
    return detail


@router.get("/{run_id}/orders/{order_id}")
def get_order_detail(run_id: str, order_id: str, db: Session = Depends(get_db)) -> dict:
    return _entity_detail_or_404(db, run_id, "order", order_id)


@router.get("/{run_id}/bank-transactions/{bank_txn_id}")
def get_bank_detail(run_id: str, bank_txn_id: str, db: Session = Depends(get_db)) -> dict:
    return _entity_detail_or_404(db, run_id, "bank", bank_txn_id)


@router.get("/{run_id}/exceptions/{exception_id}")
def get_exception_detail(run_id: str, exception_id: str, db: Session = Depends(get_db)) -> dict:
    return _entity_detail_or_404(db, run_id, "exception", exception_id)


@router.get("/{run_id}/orders", response_model=PageResponse)
def get_orders(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    _run_or_404(db, run_id)
    result = _result_or_404(run_id)
    allocated: dict[str, int] = {}
    for edge in result["allocations"]:
        allocated[edge["order_id"]] = allocated.get(edge["order_id"], 0) + edge["allocated_cash_minor"]
    rows = [
        item
        | {
            "allocated_cash_minor": allocated.get(item["order_id"], 0),
            "outstanding_minor": result["order_outstanding_minor"][item["order_id"]],
            "payment_status": result["payment_statuses"][item["order_id"]],
        }
        for item in result["orders"]
    ]
    return paginate(rows, page, page_size)


@router.get("/{run_id}/bank-transactions", response_model=PageResponse)
def get_bank_transactions(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    _run_or_404(db, run_id)
    result = _result_or_404(run_id)
    allocated: dict[str, int] = {}
    for edge in result["allocations"]:
        allocated[edge["bank_txn_id"]] = allocated.get(edge["bank_txn_id"], 0) + edge["allocated_cash_minor"]
    rows = [
        item
        | {
            "allocated_cash_minor": allocated.get(item["bank_txn_id"], 0),
            "unapplied_minor": result["bank_unapplied_minor"].get(item["bank_txn_id"]),
        }
        for item in result["bank_transactions"]
    ]
    return paginate(rows, page, page_size)


@router.get("/{run_id}/exceptions", response_model=PageResponse)
def get_exceptions(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    _run_or_404(db, run_id)
    return paginate(_result_or_404(run_id)["exceptions"], page, page_size)


@router.get("/{run_id}/exports")
def export_run(
    run_id: str,
    format: Literal["xlsx"] = "xlsx",
    db: Session = Depends(get_db),
) -> FileResponse:
    run = _run_or_404(db, run_id)
    result = _result_or_404(run_id)
    path = create_excel_export(run_id, result, run.current_revision)
    existing = db.scalar(
        select(ArtifactManifest).where(
            ArtifactManifest.run_id == run_id,
            ArtifactManifest.artifact_type == "XLSX_EXPORT",
            ArtifactManifest.relative_path == relative_artifact_path(path),
        )
    )
    if existing is None:
        db.add(
            ArtifactManifest(
                run_id=run_id,
                artifact_type="XLSX_EXPORT",
                relative_path=relative_artifact_path(path),
                sha256=sha256_path(path),
                byte_size=path.stat().st_size,
            )
        )
        db.commit()
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"smartrecon-{run_id}.xlsx",
    )
