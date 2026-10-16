"""Run request and response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from smartrecon.domain.statuses import Currency


class PolicyRequest(BaseModel):
    currency: Currency
    max_days_diff: int = Field(default=3, ge=0, le=30)
    fuzzy_candidate_threshold: float = Field(default=85.0, ge=0, le=100)
    max_candidates_per_item: int = Field(default=5, ge=1, le=20)
    max_group_orders: int = Field(default=3, ge=2, le=4)
    max_split_bank_rows: int = Field(default=3, ge=2, le=4)
    max_group_block_size: int = Field(default=20, ge=2, le=100)
    max_combinations_per_case: int = Field(default=2_000, ge=10, le=100_000)
    allow_verified_psp_fees: bool = True


class RunRequest(BaseModel):
    upload_session_id: str
    policy: PolicyRequest


class RunCreatedResponse(BaseModel):
    run_id: str
    status: str
    effective_revision: int
    semantic_checksum: str | None


class RunDetailResponse(RunCreatedResponse):
    upload_session_id: str
    currency: str
    created_at: datetime
    completed_at: datetime | None
    policy: dict[str, Any]


class DashboardResponse(BaseModel):
    run_id: str
    effective_revision: int
    kpis: dict[str, Any]
    layer_counts: dict[str, Any]
    payment_status_counts: dict[str, int]
    analytics: dict[str, Any]
    conservation: dict[str, Any]


class PageResponse(BaseModel):
    run_id: str
    effective_revision: int
    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int
