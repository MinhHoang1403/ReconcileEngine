"""Persistence operations for user-confirmed, schema-bound import profiles."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.smartrecon_api.db.models import ImportProfile, UploadSession
from backend.smartrecon_api.schemas.profiles import ImportProfileCreate, ImportProfileUpdate
from backend.smartrecon_api.services.serialization import to_jsonable
from backend.smartrecon_api.services.uploads import load_raw_bundle
from smartrecon.ingest.profiles import SCHEMA_VERSION, schema_fingerprint, source_schema


def serialize_profile(profile: ImportProfile, *, include_mapping: bool = True) -> dict[str, Any]:
    payload = {
        "id": profile.id,
        "name": profile.name,
        "schema_fingerprint": profile.schema_fingerprint,
        "schema_version": profile.schema_version,
        "schema_snapshot": profile.schema_snapshot,
        "created_at": to_jsonable(profile.created_at),
        "updated_at": to_jsonable(profile.updated_at),
    }
    if include_mapping:
        payload["mapping_snapshot"] = profile.mapping_snapshot
    return payload


def find_matching_profile(db: Session, fingerprint: str) -> ImportProfile | None:
    """Return a profile only for the current fingerprint algorithm and exact schema hash."""
    return db.scalar(
        select(ImportProfile).where(
            ImportProfile.schema_fingerprint == fingerprint,
            ImportProfile.schema_version == SCHEMA_VERSION,
        )
    )


def list_profiles(db: Session) -> list[dict[str, Any]]:
    profiles = db.scalars(select(ImportProfile).order_by(ImportProfile.name, ImportProfile.id)).all()
    return [serialize_profile(profile) for profile in profiles]


def create_profile(db: Session, request: ImportProfileCreate) -> ImportProfile:
    session = db.get(UploadSession, request.session_id)
    if session is None:
        raise LookupError("Không tìm thấy upload session")
    if not session.mapping_snapshot:
        raise ValueError("Cần xác nhận mapping trước khi lưu profile")
    raw = load_raw_bundle(session)
    fingerprint = schema_fingerprint(raw)
    if find_matching_profile(db, fingerprint) is not None:
        raise ValueError("Schema này đã có import profile; hãy sửa profile hiện có")
    profile = ImportProfile(
        id=str(uuid4()),
        name=request.name.strip(),
        schema_fingerprint=fingerprint,
        schema_version=SCHEMA_VERSION,
        schema_snapshot=source_schema(raw),
        mapping_snapshot=session.mapping_snapshot,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(db: Session, profile: ImportProfile, request: ImportProfileUpdate) -> ImportProfile:
    if request.name is not None:
        profile.name = request.name.strip()
    if request.session_id is not None:
        session = db.get(UploadSession, request.session_id)
        if session is None:
            raise LookupError("Không tìm thấy upload session")
        if not session.mapping_snapshot:
            raise ValueError("Cần xác nhận mapping trước khi cập nhật profile")
        raw = load_raw_bundle(session)
        if schema_fingerprint(raw) != profile.schema_fingerprint or source_schema(raw) != profile.schema_snapshot:
            raise ValueError("Cấu trúc nguồn đã thay đổi; không thể ghi đè profile hiện có")
        profile.mapping_snapshot = session.mapping_snapshot
    db.commit()
    db.refresh(profile)
    return profile


def delete_profile(db: Session, profile: ImportProfile) -> None:
    db.delete(profile)
    db.commit()
