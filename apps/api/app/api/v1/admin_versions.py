from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.api.response import ok
from app.db.session import get_session
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.text_version import (
    ActivateRequest,
    CompareRequest,
    ImportVersionRequest,
    ValidateRequest,
)
from app.services.text_version import (
    APPROVER_ROLES,
    TextVersionService,
    VersionError,
)

router = APIRouter(tags=["Admin: Quran Versions"], prefix="/admin/quran-versions")

_manage = require_roles(UserRole.TEXT_OFFICER.value, UserRole.TECH_ADMIN.value)
_approve = require_roles(*APPROVER_ROLES)
_read = require_roles(*APPROVER_ROLES)


def _err(exc: VersionError) -> HTTPException:
    status = {
        "VERSION_NOT_FOUND": 404,
        "VERSION_CONFLICT": 409,
        "SELF_REVIEW_FORBIDDEN": 409,
        "SECOND_REVIEW_REQUIRED": 409,
        "ALREADY_APPROVED": 409,
        "NOT_VALIDATED": 409,
        "REASON_REQUIRED": 422,
    }.get(exc.code, 400)
    return HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message})


@router.get("")
async def list_versions(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_read),
):
    return ok(request, await TextVersionService(session).list_versions())


@router.post("/import")
async def import_version(
    request: Request,
    body: ImportVersionRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_manage),
):
    meta = body.model_dump(exclude={"ayahs"})
    ayahs = [(a.surah, a.ayah, a.text) for a in body.ayahs]
    try:
        version = await TextVersionService(session).import_version(meta, ayahs, actor.id)
    except VersionError as exc:
        raise _err(exc) from None
    return ok(request, TextVersionService._to_dict(version))


@router.post("/{version_id}/validate")
async def validate_version(
    request: Request,
    version_id: uuid.UUID,
    body: ValidateRequest | None = None,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_manage),
):
    require_full = body.require_full if body else True
    try:
        result = await TextVersionService(session).validate(
            version_id, actor.id, require_full=require_full
        )
    except VersionError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/{version_id}/compare")
async def compare_versions(
    request: Request,
    version_id: uuid.UUID,
    body: CompareRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(_read),
):
    try:
        other = uuid.UUID(body.other_version_id)
        result = await TextVersionService(session).compare(version_id, other)
    except ValueError:
        raise HTTPException(
            status_code=422, detail={"code": "VALIDATION_ERROR", "message": "معرف غير صالح."}
        ) from None
    except VersionError as exc:
        raise _err(exc) from None
    return ok(request, result)


@router.post("/{version_id}/approve")
async def approve_version(
    request: Request,
    version_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    reviewer: User = Depends(_approve),
):
    try:
        version = await TextVersionService(session).approve(version_id, reviewer.id)
    except VersionError as exc:
        raise _err(exc) from None
    return ok(request, TextVersionService._to_dict(version))


@router.post("/{version_id}/publish")
async def publish_version(
    request: Request,
    version_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_manage),
):
    try:
        version = await TextVersionService(session).publish(version_id, actor.id)
    except VersionError as exc:
        raise _err(exc) from None
    return ok(request, TextVersionService._to_dict(version))


@router.post("/{version_id}/activate")
async def activate_version(
    request: Request,
    version_id: uuid.UUID,
    body: ActivateRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(_manage),
):
    try:
        version = await TextVersionService(session).activate(
            version_id, actor.id, body.reason
        )
    except VersionError as exc:
        raise _err(exc) from None
    return ok(request, TextVersionService._to_dict(version))
