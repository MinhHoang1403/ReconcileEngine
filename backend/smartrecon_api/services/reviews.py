"""Transactional orchestration for review decisions and immutable revisions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.smartrecon_api.db.models import (
    ArtifactManifest,
    ReconciliationRun,
    ReviewAction,
    RunRevision,
)
from backend.smartrecon_api.schemas.reviews import (
    ApproveReviewRequest,
    RejectReviewRequest,
    UndoReviewRequest,
)
from backend.smartrecon_api.services.artifacts import relative_artifact_path, sha256_path
from backend.smartrecon_api.services.runs import (
    load_run_result,
    persist_effective_records,
    result_from_payload,
    write_effective_result,
)
from backend.smartrecon_api.services.serialization import hash_json, to_jsonable
from smartrecon.engine import ReconciliationResult
from smartrecon.review import ReviewDecisionError, approve_group, reject_group

ReviewActionType = Literal["APPROVE_GROUP", "REJECT_GROUP", "UNDO_ACTION"]


class ReviewServiceError(RuntimeError):
    """Stable business error translated to an HTTP response by the router."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        **context: Any,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.context = context


def approve_review(
    db: Session,
    run_id: str,
    request: ApproveReviewRequest,
) -> dict[str, Any]:
    return _apply_group_decision(db, run_id, "APPROVE_GROUP", request)


def reject_review(
    db: Session,
    run_id: str,
    request: RejectReviewRequest,
) -> dict[str, Any]:
    return _apply_group_decision(db, run_id, "REJECT_GROUP", request)


def undo_review(
    db: Session,
    run_id: str,
    request: UndoReviewRequest,
) -> dict[str, Any]:
    command = {
        "run_id": run_id,
        "action_type": "UNDO_ACTION",
        **request.model_dump(),
    }
    return _execute_review(db, run_id, "UNDO_ACTION", command)


def _apply_group_decision(
    db: Session,
    run_id: str,
    action_type: Literal["APPROVE_GROUP", "REJECT_GROUP"],
    request: ApproveReviewRequest | RejectReviewRequest,
) -> dict[str, Any]:
    command = {
        "run_id": run_id,
        "action_type": action_type,
        **request.model_dump(),
    }
    return _execute_review(db, run_id, action_type, command)


def _execute_review(
    db: Session,
    run_id: str,
    action_type: ReviewActionType,
    command: dict[str, Any],
) -> dict[str, Any]:
    artifact_path: Path | None = None
    try:
        run = db.scalar(select(ReconciliationRun).where(ReconciliationRun.id == run_id).with_for_update())
        if run is None:
            raise ReviewServiceError("RUN_NOT_FOUND", "Không tìm thấy run.", 404)

        command_hash = hash_json(command)
        replay = db.scalar(
            select(ReviewAction).where(
                ReviewAction.run_id == run_id,
                ReviewAction.idempotency_key == command["idempotency_key"],
            )
        )
        if replay is not None:
            if replay.command_hash != command_hash:
                raise ReviewServiceError(
                    "IDEMPOTENCY_KEY_REUSED",
                    "Khóa idempotency đã được dùng cho một payload khác.",
                    409,
                    current_revision=run.current_revision,
                )
            response = dict(replay.payload["response"])
            response["idempotent_replay"] = True
            db.rollback()
            return response

        expected_revision = command["expected_revision"]
        if expected_revision != run.current_revision:
            raise ReviewServiceError(
                "STALE_REVISION",
                "Revision phía client đã cũ; hãy tải lại dữ liệu trước khi thao tác.",
                409,
                expected_revision=expected_revision,
                current_revision=run.current_revision,
            )

        before = result_from_payload(load_run_result(run_id, run.current_revision))
        target_action: ReviewAction | None = None
        if action_type == "APPROVE_GROUP":
            after = approve_group(before, command["group_id"])
            target_group_id = command["group_id"]
        elif action_type == "REJECT_GROUP":
            after = reject_group(before, command["group_id"])
            target_group_id = command["group_id"]
        else:
            target_action = db.get(ReviewAction, command["action_id"])
            if target_action is None or target_action.run_id != run_id:
                raise ReviewServiceError(
                    "REVIEW_ACTION_NOT_FOUND",
                    "Không tìm thấy review action cần hoàn tác.",
                    404,
                )
            if target_action.action_type not in {"APPROVE_GROUP", "REJECT_GROUP"}:
                raise ReviewServiceError(
                    "UNDO_NOT_SUPPORTED",
                    "Chỉ có thể hoàn tác quyết định approve hoặc reject.",
                    409,
                )
            if target_action.revision_after != run.current_revision:
                raise ReviewServiceError(
                    "UNDO_DEPENDENCY_CONFLICT",
                    "Không thể hoàn tác vì đã có revision phụ thuộc phía sau.",
                    409,
                    current_revision=run.current_revision,
                    target_revision=target_action.revision_after,
                )
            after = result_from_payload(load_run_result(run_id, target_action.revision_before))
            target_group_id = target_action.target_group_id

        new_revision = run.current_revision + 1
        artifact_path, payload = write_effective_result(run_id, new_revision, after)
        effective_checksum = hash_json(payload)
        action_id = str(uuid4())
        response = _response_payload(
            run_id,
            action_id,
            action_type,
            run.current_revision,
            new_revision,
            effective_checksum,
            target_group_id,
            before,
            after,
        )
        action = ReviewAction(
            id=action_id,
            run_id=run_id,
            action_type=action_type,
            revision_before=run.current_revision,
            revision_after=new_revision,
            idempotency_key=command["idempotency_key"],
            command_hash=command_hash,
            target_group_id=target_group_id,
            actor_label=command.get("actor_label"),
            undo_of_action_id=target_action.id if target_action else None,
            note=command.get("note"),
            payload={
                "command": command,
                "response": response,
                "evidence": _group_evidence(before, target_group_id),
            },
        )
        db.add(action)
        db.add(
            RunRevision(
                run_id=run_id,
                revision=new_revision,
                parent_revision=run.current_revision,
                action_id=action_id,
                effective_checksum=effective_checksum,
                result_artifact_path=relative_artifact_path(artifact_path),
                summary=after.kpis,
            )
        )
        persist_effective_records(db, run_id, new_revision, after)
        db.add(
            ArtifactManifest(
                run_id=run_id,
                artifact_type="RESULT_REVISION",
                relative_path=relative_artifact_path(artifact_path),
                sha256=sha256_path(artifact_path),
                byte_size=artifact_path.stat().st_size,
            )
        )
        run.current_revision = new_revision
        db.commit()
        return response
    except ReviewDecisionError as exc:
        db.rollback()
        raise ReviewServiceError(exc.code, str(exc), 409) from exc
    except ReviewServiceError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        if artifact_path is not None:
            artifact_path.unlink(missing_ok=True)
        raise


def _response_payload(
    run_id: str,
    action_id: str,
    action_type: ReviewActionType,
    revision_before: int,
    revision_after: int,
    effective_checksum: str,
    target_group_id: str | None,
    before: ReconciliationResult,
    after: ReconciliationResult,
) -> dict[str, Any]:
    cash_before = sum(edge.allocated_cash_minor for edge in before.allocations)
    cash_after = sum(edge.allocated_cash_minor for edge in after.allocations)
    conservation = to_jsonable(after.conservation)
    conservation["is_valid"] = after.conservation.is_valid
    return {
        "run_id": run_id,
        "action_id": action_id,
        "action_type": action_type,
        "revision_before": revision_before,
        "effective_revision": revision_after,
        "effective_checksum": effective_checksum,
        "changed_group_ids": [target_group_id] if target_group_id else [],
        "allocation_delta_minor": cash_after - cash_before,
        "kpis": after.kpis,
        "conservation": conservation,
        "idempotent_replay": False,
    }


def _group_evidence(result: ReconciliationResult, group_id: str | None) -> dict[str, Any]:
    group = next((item for item in result.groups if item.group_id == group_id), None)
    return to_jsonable(group) if group else {}
