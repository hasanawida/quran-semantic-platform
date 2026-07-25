from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.response import ok
from app.db.session import get_session
from app.services.quran import QuranService

router = APIRouter(tags=["Quran"])

# أعلى عدد آيات في سورة هو 286 (البقرة) وفق العد الكوفي
MAX_AYAH_NUMBER = 286


@router.get("/surahs")
async def list_surahs(request: Request, session: AsyncSession = Depends(get_session)):
    data = await QuranService(session).list_surahs()
    return ok(request, data)


@router.get("/surahs/{surah_number}/ayahs")
async def get_surah_ayahs(
    request: Request,
    surah_number: int = Path(ge=1, le=114),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=300),
    session: AsyncSession = Depends(get_session),
):
    """سورة كاملة بآياتها ومواضع كلماتها، والبسملة بيانًا للسورة."""
    data = await QuranService(session).get_surah(surah_number, offset, limit)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SURAH_NOT_FOUND",
                "message": "لم يتم العثور على سورة بهذا الرقم في الإصدار المفعَّل.",
            },
        )
    return ok(request, data)


@router.get("/ayahs/{surah_number}/{ayah_number}")
async def get_ayah(
    request: Request,
    surah_number: int = Path(ge=1, le=114),
    ayah_number: int = Path(ge=1, le=MAX_AYAH_NUMBER),
    session: AsyncSession = Depends(get_session),
):
    data = await QuranService(session).get_ayah(surah_number, ayah_number)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "AYAH_NOT_FOUND",
                "message": "لم يتم العثور على آية بهذا المرجع.",
            },
        )
    return ok(request, data)
