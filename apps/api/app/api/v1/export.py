"""مسارات التصدير (المرحلة H). كل مخرَج يحمل بيان أصوله وبصمته."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.response import ok
from app.db.session import get_session
from app.models.user import User
from app.services.export import ExportError, ExportService

router = APIRouter(tags=["Export"], prefix="/export")

_STATUS_BY_CODE = {
    "ROOT_NOT_FOUND": 404,
    "VERSION_NOT_FOUND": 404,
    "NO_ACTIVE_VERSION": 409,
    "NOT_PUBLISHED": 409,
    "PROJECT_FORBIDDEN": 403,
    "INVALID_ROOT": 422,
}


def _err(exc: Exception) -> HTTPException:
    code = getattr(exc, "code", "EXPORT_ERROR")
    return HTTPException(
        status_code=_STATUS_BY_CODE.get(code, 400),
        detail={"code": code, "message": getattr(exc, "message", str(exc))},
    )


@router.get("/provenance")
async def provenance(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """بيان الأصول الكامل — مفتوح للعموم ليتحقق أي أحد من مصادر المنصة."""
    try:
        return ok(request, await ExportService(session).provenance())
    except ExportError as exc:
        raise _err(exc) from None


@router.get("/roots/{root_query}")
async def export_root(
    request: Request,
    root_query: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        return ok(request, await ExportService(session).export_root(root_query))
    except ExportError as exc:
        raise _err(exc) from None


@router.get("/roots/{root_query}/csv", response_class=PlainTextResponse)
async def export_root_csv(
    root_query: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        body = await ExportService(session).export_root_csv(root_query)
    except ExportError as exc:
        raise _err(exc) from None
    return PlainTextResponse(
        body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="root-occurrences.csv"'},
    )


@router.get("/report-versions/{version_id}")
async def export_report_version(
    request: Request,
    version_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        result = await ExportService(session).export_report_version(version_id, user)
    except Exception as exc:  # ExportError أو ProjectError
        if not hasattr(exc, "code"):
            raise
        raise _err(exc) from None
    return ok(request, result)


@router.get(
    "/report-versions/{version_id}/markdown", response_class=PlainTextResponse
)
async def export_report_version_markdown(
    version_id: uuid.UUID = Path(),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        body = await ExportService(session).export_report_version_markdown(
            version_id, user
        )
    except Exception as exc:
        if not hasattr(exc, "code"):
            raise
        raise _err(exc) from None
    return PlainTextResponse(
        body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="report.md"'},
    )
