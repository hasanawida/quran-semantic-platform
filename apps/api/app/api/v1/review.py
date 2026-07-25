"""مسارات صندوق المراجعة والخلافات والتصحيحات (المرحلة G)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.api.response import ok
from app.db.session import get_session
from app.models.enums import UserRole
from app.models.review import ReviewTarget
from app.models.user import User
from app.services.review import (
    ARBITER_ROLES,
    ASSIGNER_ROLES,
    ReviewError,
    ReviewService,
)

router = APIRouter(tags=["Review"], prefix="/review")

_assign = require_roles(*ASSIGNER_ROLES)
_arbitrate = require_roles(*ARBITER_ROLES)
_reviewer = require_roles(
    UserRole.LINGUISTIC_REVIEWER.value,
    UserRole.SHARIA_REVIEWER.value,
    UserRole.QUALITY_MANAGER.value,
    UserRole.TEXT_OFFICER.value,
    UserRole.ARBITRATION_COMMITTEE.value,
    UserRole.TECH_ADMIN.value,
)

_STATUS_BY_CODE = {
    "TARGET_NOT_FOUND": 404,
    "ASSIGNMENT_NOT_FOUND": 404,
    "DISPUTE_NOT_FOUND": 404,
    "CORRECTION_NOT_FOUND": 404,
    "REVIEWER_NOT_FOUND": 404,
    "NOT_ASSIGNEE": 403,
    "SELF_REVIEW_FORBIDDEN": 409,
    "SELF_DISPUTE_FORBIDDEN": 409,
    "SELF_ARBITRATION_FORBIDDEN": 409,
    "CONFLICT_OF_INTEREST": 409,
    "ASSIGNMENT_EXISTS": 409,
    "ASSIGNMENT_CLOSED": 409,
    "ALREADY_RESOLVED": 409,
    "CLAIM_IS_DRAFT": 409,
    "TARGET_NOT_APPLICABLE": 409,
    "CORRECTION_CLOSED": 409,
    "NOT_ACCEPTED": 409,
    "NOT_APPROVED": 409,
    "REASON_REQUIRED": 422,
    "RESOLUTION_REQUIRED": 422,
    "DESCRIPTION_REQUIRED": 422,
    "NEW_STATEMENT_REQUIRED": 422,
    "DETAILS_REQUIRED": 422,
    "BODY_REQUIRED": 422,
}


def _err(exc: ReviewError) -> HTTPException:
    return HTTPException(
        status_code=_STATUS_BY_CODE.get(exc.code, 400),
        detail={"code": exc.code, "message": exc.message},
    )


class TargetRef(BaseModel):
    target_type: ReviewTarget
    target_id: str


class AssignRequest(TargetRef):
    reviewer_id: str


class RespondRequest(BaseModel):
    accept: bool
    reason: str | None = Field(default=None, max_length=500)


class CommentRequest(TargetRef):
    body: str = Field(min_length=1, max_length=8000)


class DisputeRequest(TargetRef):
    reason: str = Field(min_length=10, max_length=4000)


class ResolveRequest(BaseModel):
    resolution: str = Field(min_length=10, max_length=4000)


class ConflictRequest(TargetRef):
    details: str = Field(min_length=5, max_length=1000)


class CorrectionRequest(TargetRef):
    description: str = Field(min_length=10, max_length=4000)
    new_statement: str | None = Field(default=None, max_length=8000)
    dispute_id: str | None = None


def _uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": f"{label} غير صالح."},
        ) from None


# ---- التكليفات ----------------------------------------------------------
@router.post("/assignments")
async def assign(
    request: Request,
    body: AssignRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_assign),
):
    try:
        result = await ReviewService(session).assign(
            body.target_type,
            _uuid(body.target_id, "معرف الكيان"),
            _uuid(body.reviewer_id, "معرف المراجع"),
            actor,
        )
    except ReviewError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.get("/assignments/mine")
async def my_queue(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return ok(request, await ReviewService(session).my_queue(user))


@router.post("/assignments/{assignment_id}/respond")
async def respond(
    request: Request,
    assignment_id: uuid.UUID,
    body: RespondRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ReviewService(session).respond(
            assignment_id, user, body.accept, body.reason
        )
    except ReviewError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/assignments/{assignment_id}/complete")
async def complete(
    request: Request,
    assignment_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ReviewService(session).complete(assignment_id, user)
    except ReviewError as exc:
        raise _err(exc) from None
    return ok(request, result)


# ---- تضارب المصالح ------------------------------------------------------
@router.post("/conflicts")
async def declare_conflict(
    request: Request,
    body: ConflictRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ReviewService(session).declare_conflict(
            user.id,
            body.target_type,
            _uuid(body.target_id, "معرف الكيان"),
            body.details,
        )
    except ReviewError as exc:
        raise _err(exc) from None
    return ok(request, result)


# ---- التعليقات والخيط ---------------------------------------------------
@router.post("/comments")
async def add_comment(
    request: Request,
    body: CommentRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ReviewService(session).add_comment(
            body.target_type, _uuid(body.target_id, "معرف الكيان"), body.body, user
        )
    except ReviewError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.get("/threads/{target_type}/{target_id}")
async def thread(
    request: Request,
    target_type: ReviewTarget,
    target_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_reviewer),
):
    """خيط المراجعة يكشف نقاش المراجعين ونصوص المسودات، فهو للمراجعين."""
    return ok(request, await ReviewService(session).list_thread(target_type, target_id))


# ---- الخلافات -----------------------------------------------------------
@router.get("/disputes")
async def open_disputes(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    """الخلافات المفتوحة معروضة لكل مستخدم مسجَّل — لا تُخفى."""
    return ok(request, await ReviewService(session).open_disputes())


@router.post("/disputes")
async def raise_dispute(
    request: Request,
    body: DisputeRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_reviewer),
):
    try:
        result = await ReviewService(session).raise_dispute(
            body.target_type, _uuid(body.target_id, "معرف الكيان"), body.reason, actor
        )
    except ReviewError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/disputes/{dispute_id}/resolve")
async def resolve_dispute(
    request: Request,
    dispute_id: uuid.UUID,
    body: ResolveRequest,
    session: AsyncSession = Depends(get_session),
    arbiter: User = Depends(_arbitrate),
):
    try:
        result = await ReviewService(session).resolve_dispute(
            dispute_id, body.resolution, arbiter
        )
    except ReviewError as exc:
        raise _err(exc) from None
    return ok(request, result)


# ---- التصحيحات ----------------------------------------------------------
@router.get("/corrections/{target_type}/{target_id}")
async def list_corrections(
    request: Request,
    target_type: ReviewTarget,
    target_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_reviewer),
):
    """لقطة «قبل» تحوي النص السابق للادعاء، فلا تُفتح لكل مسجَّل."""
    return ok(
        request, await ReviewService(session).list_corrections(target_type, target_id)
    )


@router.post("/corrections")
async def propose_correction(
    request: Request,
    body: CorrectionRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ReviewService(session).propose_correction(
            body.target_type,
            _uuid(body.target_id, "معرف الكيان"),
            body.description,
            body.new_statement,
            user,
            _uuid(body.dispute_id, "معرف الخلاف") if body.dispute_id else None,
        )
    except ReviewError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/corrections/{correction_id}/approve")
async def approve_correction(
    request: Request,
    correction_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    approver: User = Depends(_reviewer),
):
    try:
        result = await ReviewService(session).approve_correction(correction_id, approver)
    except ReviewError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/corrections/{correction_id}/apply")
async def apply_correction(
    request: Request,
    correction_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_reviewer),
):
    try:
        result = await ReviewService(session).apply_correction(correction_id, actor)
    except ReviewError as exc:
        raise _err(exc) from None
    return ok(request, result)
