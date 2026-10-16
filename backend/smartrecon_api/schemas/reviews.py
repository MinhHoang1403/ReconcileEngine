"""Request and response contracts for auditable review decisions."""

from typing import Any

from pydantic import BaseModel, Field


class ReviewCommandBase(BaseModel):
    """Concurrency and audit fields shared by every mutating review request."""

    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=120)
    actor_label: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2_000)


class ApproveReviewRequest(ReviewCommandBase):
    group_id: str = Field(min_length=1, max_length=64)
    note: str = Field(min_length=1, max_length=2_000)


class RejectReviewRequest(ReviewCommandBase):
    group_id: str = Field(min_length=1, max_length=64)
    note: str = Field(min_length=1, max_length=2_000)


class UndoReviewRequest(ReviewCommandBase):
    action_id: str = Field(min_length=1, max_length=36)


class ReviewActionResponse(BaseModel):
    run_id: str
    action_id: str
    action_type: str
    revision_before: int
    effective_revision: int
    effective_checksum: str
    changed_group_ids: list[str]
    allocation_delta_minor: int
    kpis: dict[str, Any]
    conservation: dict[str, Any]
    idempotent_replay: bool = False


class ReviewPageResponse(BaseModel):
    run_id: str
    effective_revision: int
    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int
