"""Upload, mapping, and health HTTP schemas."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from smartrecon.domain.statuses import Currency
from smartrecon.ingest.mapping import TRANSFORMATION_VERSION


class MappingRequest(BaseModel):
    order_columns: dict[str, str]
    bank_columns: dict[str, str]
    currency: Currency
    source_profile: str = "BANK_CREDIT"
    date_format: str = "%Y-%m-%d"
    decimal_separator: str = "."
    thousand_separator: str | None = ","
    order_defaults: dict[str, str] = Field(default_factory=lambda: {"order_status": "ELIGIBLE"})
    bank_defaults: dict[str, str] = Field(default_factory=dict)
    confirmed_structure: bool = False
    order_date_format: str | None = None
    bank_date_format: str | None = None
    order_transformations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    bank_transformations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    transformation_version: str = TRANSFORMATION_VERSION
    confirmed_ambiguities: tuple[str, ...] = ()


class ExclusionRequest(BaseModel):
    feed: Literal["orders", "bank_transactions"]
    source_row_number: int = Field(ge=2)
    reason: str = Field(min_length=3, max_length=500)


class ResolutionRequest(BaseModel):
    exclusions: list[ExclusionRequest] = Field(default_factory=list)
    acknowledged_issue_codes: list[str] = Field(default_factory=list)


class RawEdaResponse(BaseModel):
    row_count: int
    column_count: int
    columns: list[str]
    missing_by_column: dict[str, int]
    duplicate_rows: int
    sample_rows: list[dict[str, Any]]
    confidence: str


class InspectionResponse(BaseModel):
    session_id: str
    status: str
    dataset_profile: str
    raw_eda: dict[str, RawEdaResponse]
    suggested_mapping: dict[str, dict[str, str]]
    mapping_suggestions: dict[str, Any]
    detected_structure: dict[str, Any]


class HealthResponse(BaseModel):
    session_id: str
    status: str
    report: dict[str, Any]
    exclusions: list[dict[str, Any]]
    acknowledged_issue_codes: list[str]
    standardized_eda: dict[str, Any]
