"""Revision-scoped dashboard and audit projections."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.smartrecon_api.db.models import ReviewAction
from backend.smartrecon_api.services.runs import result_from_payload
from smartrecon.analytics.reporting import snapshot_analytics


def review_actions_as_of(db: Session, run_id: str, revision: int) -> list[ReviewAction]:
    """Return committed audit actions that contributed to the requested revision."""
    return list(
        db.scalars(
            select(ReviewAction)
            .where(ReviewAction.run_id == run_id, ReviewAction.revision_after <= revision)
            .order_by(ReviewAction.revision_after, ReviewAction.id)
        ).all()
    )


def dashboard_analytics(
    result_payload: dict[str, Any],
    actions: list[ReviewAction],
) -> dict[str, Any]:
    """Combine pure snapshot metrics with immutable review-event counts."""
    analytics = snapshot_analytics(result_from_payload(result_payload))
    action_counts = Counter(action.action_type for action in actions)
    analytics["review_decision_counts"] = {
        "APPROVE_GROUP": action_counts.get("APPROVE_GROUP", 0),
        "REJECT_GROUP": action_counts.get("REJECT_GROUP", 0),
        "UNDO_ACTION": action_counts.get("UNDO_ACTION", 0),
    }
    return analytics


def review_audit_rows(actions: list[ReviewAction]) -> list[dict[str, Any]]:
    """Serialize review audit fields for a report without exposing command hashes."""
    return [
        {
            "action_id": action.id,
            "created_at": action.created_at,
            "action_type": action.action_type,
            "revision_before": action.revision_before,
            "revision_after": action.revision_after,
            "target_group_id": action.target_group_id,
            "actor_label": action.actor_label,
            "actor_is_authenticated": False,
            "note": action.note,
            "undo_of_action_id": action.undo_of_action_id,
            "allocation_delta_minor": action.payload.get("response", {}).get("allocation_delta_minor", 0),
        }
        for action in actions
    ]
