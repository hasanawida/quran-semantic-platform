from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.response import ok
from app.db.session import get_session
from app.services.root_comparison import (
    RootComparisonError,
    RootComparisonService,
)
from app.services.roots import RootService
from app.utils.arabic import normalize_root_input

router = APIRouter(tags=["Roots"])


def _validated_root(root_query: str) -> str:
    normalized = normalize_root_input(root_query)
    if not normalized:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "المدخل لا يحتوي حروفًا عربية صالحة لجذر.",
            },
        )
    return normalized


def _root_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "code": "ROOT_NOT_FOUND",
            "message": "لم يتم العثور على جذر بهذا الإدخال. جرّب صيغة أخرى.",
        },
    )


@router.get("/roots/compare")
async def compare_roots(
    request: Request,
    roots: str = Query(description="جذور مفصولة بفواصل، مثال: سأل,طلب"),
    limit: int = Query(default=30, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """مقارنة توزيع جذرين فأكثر على المصحف — عرض بيانات لا حكم دلالي."""
    try:
        data = await RootComparisonService(session).compare(
            roots.split(","), limit=limit
        )
    except RootComparisonError as exc:
        status = {
            "ROOT_NOT_FOUND": 404,
            "NO_ACTIVE_VERSION": 409,
            "TOO_FEW_ROOTS": 422,
            "TOO_MANY_ROOTS": 422,
            "INVALID_ROOT": 422,
        }.get(exc.code, 400)
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": exc.message},
        ) from None
    return ok(request, data)


@router.get("/roots/{root_query}")
async def get_root(
    request: Request,
    root_query: str,
    session: AsyncSession = Depends(get_session),
):
    _validated_root(root_query)
    data = await RootService(session).get_root(root_query)
    if data is None:
        raise _root_not_found()
    return ok(request, data)


@router.get("/roots/{root_query}/occurrences")
async def get_root_occurrences(
    request: Request,
    root_query: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    _validated_root(root_query)
    data = await RootService(session).get_occurrences(
        root_query, offset=offset, limit=limit
    )
    if data is None:
        raise _root_not_found()
    return ok(request, data)
