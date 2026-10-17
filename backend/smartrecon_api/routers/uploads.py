"""Two-feed upload, mapping, EDA, and Health Gate endpoints."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.smartrecon_api.config import get_settings
from backend.smartrecon_api.db.database import get_db
from backend.smartrecon_api.db.models import UploadSession
from backend.smartrecon_api.schemas.uploads import (
    HealthResponse,
    InspectionResponse,
    MappingRequest,
    ResolutionRequest,
)
from backend.smartrecon_api.services.artifacts import upload_directory
from backend.smartrecon_api.services.uploads import (
    apply_resolution,
    confirm_mapping,
    create_demo_session,
    create_upload_session,
    health_issue_detail,
    normalized_csv,
    preview_mapping,
    save_upload,
)
from smartrecon.ingest.readers import InputFileError, read_source_bundle

router = APIRouter(prefix="/api", tags=["uploads"])


def _session_or_404(db: Session, session_id: str) -> UploadSession:
    session = db.get(UploadSession, session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "UPLOAD_NOT_FOUND", "message": "Không tìm thấy upload session."},
        )
    return session


@router.post("/demo/datasets", response_model=InspectionResponse)
def create_demo(db: Session = Depends(get_db)) -> dict:
    if not get_settings().demo_mode:
        raise HTTPException(status_code=404, detail="Demo mode không được bật")
    return create_demo_session(db)


@router.post("/uploads/inspect", response_model=InspectionResponse)
async def inspect_upload(
    orders_file: Annotated[UploadFile | None, File()] = None,
    bank_file: Annotated[UploadFile | None, File()] = None,
    workbook_file: Annotated[UploadFile | None, File()] = None,
    orders_sheet: Annotated[str | None, Form()] = None,
    bank_sheet: Annotated[str | None, Form()] = None,
    orders_header_row: Annotated[int | None, Form()] = None,
    bank_header_row: Annotated[int | None, Form()] = None,
    orders_header_depth: Annotated[int | None, Form()] = None,
    bank_header_depth: Annotated[int | None, Form()] = None,
    orders_delimiter: Annotated[str | None, Form()] = None,
    bank_delimiter: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
) -> dict:
    session_id = str(uuid4())
    directory = upload_directory(session_id)
    try:
        if workbook_file is not None:
            if orders_file is not None or bank_file is not None:
                raise ValueError("Không gửi workbook đồng thời với hai file riêng")
            path = await save_upload(workbook_file, directory, "workbook")
            raw = read_source_bundle(
                workbook_path=path,
                orders_sheet=orders_sheet,
                bank_sheet=bank_sheet,
                orders_header_row=orders_header_row,
                bank_header_row=bank_header_row,
                orders_header_depth=orders_header_depth,
                bank_header_depth=bank_header_depth,
            )
            source_paths = {
                "mode": "workbook",
                "workbook": str(path),
                "orders_sheet": orders_sheet,
                "bank_sheet": bank_sheet,
            }
        else:
            if orders_file is None or bank_file is None:
                raise ValueError("Cần đủ hai file orders và bank")
            orders_path = await save_upload(orders_file, directory, "orders")
            bank_path = await save_upload(bank_file, directory, "bank")
            raw = read_source_bundle(
                orders_path=orders_path,
                bank_path=bank_path,
                orders_header_row=orders_header_row,
                bank_header_row=bank_header_row,
                orders_header_depth=orders_header_depth,
                bank_header_depth=bank_header_depth,
                orders_delimiter=orders_delimiter,
                bank_delimiter=bank_delimiter,
            )
            source_paths = {"mode": "separate", "orders": str(orders_path), "bank": str(bank_path)}
        return create_upload_session(db, session_id, raw, source_paths)
    except (InputFileError, ValueError) as exc:
        status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if "25 MB" in str(exc) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail={"error_code": "INVALID_UPLOAD", "message": str(exc)},
        ) from exc


@router.post("/uploads/{session_id}/mapping", response_model=HealthResponse)
def map_upload(session_id: str, request: MappingRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return confirm_mapping(db, _session_or_404(db, session_id), request)
    except (InputFileError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "INVALID_MAPPING", "message": str(exc)},
        ) from exc


@router.post("/uploads/{session_id}/preview")
def preview_upload(session_id: str, request: MappingRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return preview_mapping(_session_or_404(db, session_id), request)
    except (InputFileError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "INVALID_MAPPING_PREVIEW", "message": str(exc)},
        ) from exc


@router.get("/uploads/{session_id}/normalized/{feed}.csv")
def download_normalized(session_id: str, feed: str, db: Session = Depends(get_db)) -> Response:
    try:
        content = normalized_csv(_session_or_404(db, session_id), feed)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error_code": "NORMALIZED_EXPORT_NOT_READY", "message": str(exc)},
        ) from exc
    filename = "receivables-normalized.csv" if feed == "orders" else "payments-normalized.csv"
    return Response(
        content="\ufeff" + content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/uploads/{session_id}/health", response_model=HealthResponse)
def get_health(session_id: str, db: Session = Depends(get_db)) -> dict:
    session = _session_or_404(db, session_id)
    if session.health_snapshot is None:
        raise HTTPException(
            status_code=409,
            detail={"error_code": "MAPPING_REQUIRED", "message": "Cần xác nhận mapping trước."},
        )
    return session.health_snapshot | {"session_id": session.id, "status": session.status}


@router.get("/uploads/{session_id}/health/issues/{issue_index}")
def get_health_issue_detail(session_id: str, issue_index: int, db: Session = Depends(get_db)) -> dict:
    session = _session_or_404(db, session_id)
    if session.health_snapshot is None:
        raise HTTPException(
            status_code=409,
            detail={"error_code": "MAPPING_REQUIRED", "message": "Cần chuẩn hóa dữ liệu trước."},
        )
    try:
        return health_issue_detail(session, issue_index)
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "HEALTH_ISSUE_NOT_FOUND", "message": "Không tìm thấy vấn đề dữ liệu."},
        ) from exc


@router.post("/uploads/{session_id}/resolutions", response_model=HealthResponse)
def resolve_health(session_id: str, request: ResolutionRequest, db: Session = Depends(get_db)) -> dict:
    session = _session_or_404(db, session_id)
    try:
        return apply_resolution(db, session, request)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error_code": "INVALID_RESOLUTION", "message": str(exc)},
        ) from exc
