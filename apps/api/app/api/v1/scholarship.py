"""مسارات المصادر والاستشهادات والادعاءات (المرحلة E).

القراءة العامة محصورة بما اجتاز الاعتماد: الادعاء المسودة أو قيد المراجعة
لا يُعرض للعموم بوصفه نتيجة، والمعتمد يُعرض بأدلته المؤيدة والمعارضة معًا.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.api.response import ok
from app.db.session import get_session
from app.models.enums import RecordStatus, UserRole
from app.models.user import User
from app.schemas.scholarship import (
    AttachEvidenceRequest,
    CitationRequest,
    ClaimRequest,
    DisputeRequest,
    RejectSourceRequest,
    SourceWorkRequest,
)
from app.services.scholarship import (
    CLAIM_REVIEWER_ROLES,
    SOURCE_VERIFIER_ROLES,
    ScholarshipError,
    ScholarshipService,
)

router = APIRouter(tags=["Scholarship"])

_contribute = require_roles(*[role.value for role in UserRole])
_verify_source = require_roles(*SOURCE_VERIFIER_ROLES)
_review_claim = require_roles(*CLAIM_REVIEWER_ROLES)

_STATUS_BY_CODE = {
    "SOURCE_NOT_FOUND": 404,
    "CITATION_NOT_FOUND": 404,
    "CLAIM_NOT_FOUND": 404,
    "ROOT_NOT_FOUND": 404,
    "AYAH_NOT_FOUND": 404,
    "SOURCE_CONFLICT": 409,
    "EVIDENCE_EXISTS": 409,
    "ALREADY_VERIFIED": 409,
    "CLAIM_LOCKED": 409,
    "CLAIM_NOT_DRAFT": 409,
    "CLAIM_NOT_UNDER_REVIEW": 409,
    "EVIDENCE_REQUIRED": 409,
    "SELF_REVIEW_FORBIDDEN": 409,
    "SELF_VERIFICATION_FORBIDDEN": 409,
    "SECOND_REVIEW_REQUIRED": 409,
    "NOT_CLAIM_AUTHOR": 403,
    "SOURCE_INCOMPLETE": 422,
    "LOCATOR_REQUIRED": 422,
    "CITATION_EMPTY": 422,
    "STATEMENT_TOO_SHORT": 422,
    "SUBJECT_INVALID": 422,
    "REASON_REQUIRED": 422,
}


def _err(exc: ScholarshipError) -> HTTPException:
    return HTTPException(
        status_code=_STATUS_BY_CODE.get(exc.code, 400),
        detail={"code": exc.code, "message": exc.message},
    )


# ---- المصادر ------------------------------------------------------------
@router.get("/sources")
async def list_sources(
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    return ok(request, await ScholarshipService(session).list_sources(offset, limit))


@router.post("/sources")
async def add_source(
    request: Request,
    body: SourceWorkRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_contribute),
):
    try:
        result = await ScholarshipService(session).add_source(
            body.model_dump(), actor.id
        )
    except ScholarshipError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/sources/{source_id}/verify")
async def verify_source(
    request: Request,
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_verify_source),
):
    try:
        result = await ScholarshipService(session).verify_source(source_id, actor.id)
    except ScholarshipError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/sources/{source_id}/reject")
async def reject_source(
    request: Request,
    source_id: uuid.UUID,
    body: RejectSourceRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_verify_source),
):
    try:
        result = await ScholarshipService(session).reject_source(
            source_id, actor.id, body.reason
        )
    except ScholarshipError as exc:
        raise _err(exc) from None
    return ok(request, result)


# ---- الاستشهادات --------------------------------------------------------
@router.post("/citations")
async def add_citation(
    request: Request,
    body: CitationRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_contribute),
):
    try:
        result = await ScholarshipService(session).add_citation(
            body.model_dump(), actor.id
        )
    except (ScholarshipError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise HTTPException(
                status_code=422,
                detail={"code": "VALIDATION_ERROR", "message": "معرف مصدر غير صالح."},
            ) from None
        raise _err(exc) from None
    return ok(request, result)


@router.get("/citations/{citation_id}")
async def get_citation(
    request: Request,
    citation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_current_user),
):
    try:
        result = await ScholarshipService(session).get_citation(citation_id)
    except ScholarshipError as exc:
        raise _err(exc) from None
    return ok(request, result)


# ---- الادعاءات ----------------------------------------------------------
@router.get("/claims")
async def list_claims(
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """قراءة عامة: المعتمد والمختلف فيه فقط — المسودات ليست نتائج."""
    service = ScholarshipService(session)
    approved = await service.list_claims(offset, limit, RecordStatus.APPROVED.value)
    disputed = await service.list_claims(0, limit, RecordStatus.DISPUTED.value)
    return ok(
        request,
        {
            "approved": approved,
            "disputed": disputed,
            "notice": (
                "تُعرض هنا الادعاءات المعتمدة والمختلف فيها فقط. المسودات "
                "وما هو قيد المراجعة ليست نتائج ولا تُنشر."
            ),
        },
    )


@router.post("/claims")
async def create_claim(
    request: Request,
    body: ClaimRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_contribute),
):
    try:
        result = await ScholarshipService(session).create_claim(
            body.model_dump(), actor.id
        )
    except ScholarshipError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.get("/claims/{claim_id}")
async def get_claim(
    request: Request,
    claim_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ScholarshipService(session).get_claim(claim_id)
    except ScholarshipError as exc:
        raise _err(exc) from None
    # ما لم يُعتمد أو يُختلف فيه ليس نتيجة: يبقى بين صاحبه والمراجعين
    private_states = {
        RecordStatus.DRAFT.value,
        RecordStatus.UNDER_REVIEW.value,
        RecordStatus.REJECTED.value,
    }
    if result["status"] in private_states:
        is_author = result["author"]["id"] == str(user.id)
        if not is_author and not (user.role_values & CLAIM_REVIEWER_ROLES):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FORBIDDEN",
                    "message": "هذا الادعاء لم يُعتمد بعد، وهو بين صاحبه والمراجعين.",
                },
            )
    return ok(request, result)


@router.post("/claims/{claim_id}/evidence")
async def attach_evidence(
    request: Request,
    claim_id: uuid.UUID,
    body: AttachEvidenceRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_contribute),
):
    try:
        result = await ScholarshipService(session).attach_citation(
            claim_id,
            uuid.UUID(body.citation_id),
            body.stance.value,
            body.note,
            actor.id,
        )
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "معرف استشهاد غير صالح."},
        ) from None
    except ScholarshipError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/claims/{claim_id}/submit")
async def submit_claim(
    request: Request,
    claim_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_contribute),
):
    try:
        result = await ScholarshipService(session).submit_claim(claim_id, actor.id)
    except ScholarshipError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/claims/{claim_id}/approve")
async def approve_claim(
    request: Request,
    claim_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    reviewer: User = Depends(_review_claim),
):
    try:
        result = await ScholarshipService(session).approve_claim(claim_id, reviewer.id)
    except ScholarshipError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/claims/{claim_id}/dispute")
async def dispute_claim(
    request: Request,
    claim_id: uuid.UUID,
    body: DisputeRequest,
    session: AsyncSession = Depends(get_session),
    reviewer: User = Depends(_review_claim),
):
    try:
        result = await ScholarshipService(session).dispute_claim(
            claim_id, reviewer.id, body.reason
        )
    except ScholarshipError as exc:
        raise _err(exc) from None
    return ok(request, result)
