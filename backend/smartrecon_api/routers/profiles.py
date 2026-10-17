"""CRUD endpoints for reusable, user-confirmed import profiles."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.smartrecon_api.db.database import get_db
from backend.smartrecon_api.db.models import ImportProfile
from backend.smartrecon_api.schemas.profiles import (
    ImportProfileCreate,
    ImportProfileResponse,
    ImportProfileUpdate,
)
from backend.smartrecon_api.services.profiles import (
    create_profile,
    delete_profile,
    list_profiles,
    serialize_profile,
    update_profile,
)

router = APIRouter(prefix="/api/import-profiles", tags=["import-profiles"])


def _profile_or_404(db: Session, profile_id: str) -> ImportProfile:
    profile = db.get(ImportProfile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "IMPORT_PROFILE_NOT_FOUND", "message": "Không tìm thấy import profile."},
        )
    return profile


@router.get("", response_model=list[ImportProfileResponse])
def get_profiles(db: Session = Depends(get_db)) -> list[dict]:
    return list_profiles(db)


@router.post("", response_model=ImportProfileResponse, status_code=status.HTTP_201_CREATED)
def post_profile(request: ImportProfileCreate, db: Session = Depends(get_db)) -> dict:
    try:
        return serialize_profile(create_profile(db, request))
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "UPLOAD_NOT_FOUND", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error_code": "IMPORT_PROFILE_CONFLICT", "message": str(exc)},
        ) from exc


@router.patch("/{profile_id}", response_model=ImportProfileResponse)
def patch_profile(profile_id: str, request: ImportProfileUpdate, db: Session = Depends(get_db)) -> dict:
    try:
        return serialize_profile(update_profile(db, _profile_or_404(db, profile_id), request))
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "UPLOAD_NOT_FOUND", "message": str(exc)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"error_code": "IMPORT_PROFILE_SCHEMA_CHANGED", "message": str(exc)},
        ) from exc


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_profile(profile_id: str, db: Session = Depends(get_db)) -> Response:
    delete_profile(db, _profile_or_404(db, profile_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
