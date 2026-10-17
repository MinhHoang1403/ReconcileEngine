"""Reusable import-profile HTTP schemas."""

from pydantic import BaseModel, Field


class ImportProfileCreate(BaseModel):
    session_id: str
    name: str = Field(min_length=1, max_length=160)


class ImportProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    session_id: str | None = None


class ImportProfileResponse(BaseModel):
    id: str
    name: str
    schema_fingerprint: str
    schema_version: str
    schema_snapshot: dict
    mapping_snapshot: dict
    created_at: str | None
    updated_at: str | None
