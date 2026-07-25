"""إدارة خط الصرف: الترميز والاستيراد والتعارضات والقرارات والاشتقاق.

الصلاحيات (قسم 18): كل تحقق في طبقة الخدمة، والاستيراد وإعادة الاشتقاق
عمليتان تقنيتان محفوظتان لمسؤول النص والمدير التقني، بينما اقتراح قرار
الجذر واعتماده للمراجعين اللغويين وإدارة الجودة ولجنة الحسم.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.api.response import ok
from app.db.session import get_session
from app.models.enums import UserRole
from app.models.morphology import MorphologySource
from app.models.user import User
from app.schemas.morphology import (
    ApproveDecisionRequest,
    ImportMorphologyRequest,
    ProposeDecisionRequest,
    RebuildRequest,
    SourceToggleRequest,
    TokenizeRequest,
)
from app.services.morphology import (
    MorphologyError,
    MorphologyService,
    load_morphology_bundle,
)

router = APIRouter(tags=["Admin: Morphology"], prefix="/admin/morphology")

_operate = require_roles(UserRole.TEXT_OFFICER.value, UserRole.TECH_ADMIN.value)
_propose = require_roles(
    UserRole.LINGUISTIC_REVIEWER.value,
    UserRole.QUALITY_MANAGER.value,
    UserRole.TECH_ADMIN.value,
)
_approve = require_roles(
    UserRole.LINGUISTIC_REVIEWER.value,
    UserRole.QUALITY_MANAGER.value,
    UserRole.ARBITRATION_COMMITTEE.value,
)
_read = require_roles(
    UserRole.TEXT_OFFICER.value,
    UserRole.TECH_ADMIN.value,
    UserRole.LINGUISTIC_REVIEWER.value,
    UserRole.QUALITY_MANAGER.value,
    UserRole.SHARIA_REVIEWER.value,
    UserRole.ARBITRATION_COMMITTEE.value,
)

_STATUS_BY_CODE = {
    "AYAH_NOT_FOUND": 404,
    "WORD_NOT_FOUND": 404,
    "DECISION_NOT_FOUND": 404,
    "ROOT_NOT_FOUND": 404,
    "SOURCE_NOT_FOUND": 404,
    "BUNDLE_MISSING": 404,
    "GOLDEN_FILE_MISSING": 404,
    "NO_ACTIVE_VERSION": 409,
    "NOT_TOKENIZED": 409,
    "NO_ANALYSES": 409,
    "NO_AYAHS": 409,
    "DECISION_EXISTS": 409,
    "ALREADY_APPROVED": 409,
    "SELF_REVIEW_FORBIDDEN": 409,
    "RATIONALE_REQUIRED": 422,
    "INVALID_ROOT": 422,
}


def _err(exc: MorphologyError) -> HTTPException:
    return HTTPException(
        status_code=_STATUS_BY_CODE.get(exc.code, 400),
        detail={"code": exc.code, "message": exc.message},
    )


def _scope(surahs: list[int] | None) -> set[int] | None:
    return set(surahs) if surahs else None


# ---- المصادر ------------------------------------------------------------
@router.get("/sources")
async def list_sources(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_read),
):
    return ok(request, await MorphologyService(session).list_sources())


@router.patch("/sources/{source_id}")
async def toggle_source(
    request: Request,
    source_id: uuid.UUID,
    body: SourceToggleRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_operate),
):
    """تعطيل مصدر يستبعده من الاشتقاق دون حذف بياناته."""
    from app.db.audit import record_audit

    source = await session.get(MorphologySource, source_id)
    if source is None:
        raise _err(MorphologyError("SOURCE_NOT_FOUND", "المصدر غير موجود."))
    source.is_enabled = body.is_enabled
    record_audit(
        session,
        action="morphology_source_toggle",
        entity_type="morphology_source",
        entity_id=source.id,
        actor_id=actor.id,
        new_data={"is_enabled": body.is_enabled},
    )
    await session.commit()
    return ok(request, {"id": str(source.id), "is_enabled": source.is_enabled})


# ---- خط المعالجة --------------------------------------------------------
@router.post("/tokenize")
async def tokenize(
    request: Request,
    body: TokenizeRequest | None = None,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_operate),
):
    try:
        result = await MorphologyService(session).tokenize_version(
            actor_id=actor.id, surahs=_scope(body.surahs if body else None)
        )
    except MorphologyError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/import")
async def import_morphology(
    request: Request,
    body: ImportMorphologyRequest | None = None,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_operate),
):
    """يستورد حزمة الصرف المبنية محليًا (ببصمة ملفها المصدري)."""
    try:
        bundle = load_morphology_bundle()
        result = await MorphologyService(session).import_bundle(
            bundle, actor_id=actor.id, surahs=_scope(body.surahs if body else None)
        )
    except MorphologyError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/rebuild-occurrences")
async def rebuild_occurrences(
    request: Request,
    body: RebuildRequest | None = None,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_operate),
):
    try:
        result = await MorphologyService(session).rebuild_occurrences(
            actor_id=actor.id, surahs=_scope(body.surahs if body else None)
        )
    except MorphologyError as exc:
        raise _err(exc) from None
    return ok(request, result)


# ---- التعارضات والقرارات ------------------------------------------------
@router.get("/conflicts")
async def list_conflicts(
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_read),
):
    try:
        result = await MorphologyService(session).list_conflicts(offset, limit)
    except MorphologyError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.get("/decisions")
async def list_decisions(
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_read),
):
    return ok(request, await MorphologyService(session).list_decisions(offset, limit))


@router.post("/decisions")
async def propose_decision(
    request: Request,
    body: ProposeDecisionRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_propose),
):
    try:
        result = await MorphologyService(session).propose_decision(
            body.surah,
            body.ayah,
            body.word_number,
            body.roots,
            body.rationale,
            actor.id,
        )
    except MorphologyError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/decisions/{decision_id}/approve")
async def approve_decision(
    request: Request,
    decision_id: uuid.UUID,
    body: ApproveDecisionRequest | None = None,
    session: AsyncSession = Depends(get_session),
    reviewer: User = Depends(_approve),
):
    try:
        result = await MorphologyService(session).approve_decision(
            decision_id, reviewer.id, body.note if body else None
        )
    except MorphologyError as exc:
        raise _err(exc) from None
    return ok(request, result)


# ---- المواضع المرجعية ---------------------------------------------------
@router.post("/golden/seed")
async def seed_golden(
    request: Request,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_operate),
):
    try:
        result = await MorphologyService(session).seed_golden_cases(actor_id=actor.id)
    except MorphologyError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.get("/golden/check")
async def golden_check(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_read),
):
    try:
        result = await MorphologyService(session).golden_check()
    except MorphologyError as exc:
        raise _err(exc) from None
    return ok(request, result)


# ---- ملخص الحالة --------------------------------------------------------
@router.get("/status")
async def pipeline_status(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_read),
):
    from sqlalchemy import func

    from app.models.language import RootDerivation, RootOccurrence
    from app.models.morphology import MorphologicalAnalysis, Token

    counts = {}
    for label, column in (
        ("tokens", Token.id),
        ("analyses", MorphologicalAnalysis.id),
        ("occurrences", RootOccurrence.id),
    ):
        counts[label] = await session.scalar(select(func.count(column))) or 0

    by_derivation = {
        value.value: (
            await session.scalar(
                select(func.count(RootOccurrence.id)).where(
                    RootOccurrence.derivation == value
                )
            )
            or 0
        )
        for value in RootDerivation
    }
    counts["occurrences_by_derivation"] = by_derivation
    counts["sources"] = await MorphologyService(session).list_sources()
    return ok(request, counts)
