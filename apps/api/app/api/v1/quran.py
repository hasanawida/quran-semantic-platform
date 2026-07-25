from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.response import ok
from app.db.session import get_session
from app.services.quran import QuranService

router = APIRouter(tags=["Quran"])

# أعلى عدد آيات في سورة هو 286 (البقرة) وفق العد الكوفي
MAX_AYAH_NUMBER = 286


@router.get("/surahs")
async def list_surahs(
    request: Request,
    q: str | None = Query(default=None, max_length=60),
    session: AsyncSession = Depends(get_session),
):
    """فهرست السور. مع `q` ترشيح بالاسم أو بالرقم.

    تطبيع الاسم يقع في الخادم وحده (`normalize_surah_name`) فلا يُعاد
    تنفيذه في الواجهة بمنطق مستقل ينحرف عنه بمرور الوقت."""
    data = await QuranService(session).list_surahs(q)
    return ok(request, data)


@router.get("/search/ayahs")
async def search_ayahs(
    request: Request,
    q: str = Query(min_length=2, max_length=100),
    surah: int | None = Query(default=None, ge=1, le=114),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """بحث نصي في آيات الإصدار النشط، على طبقتين موسومتين.

    المعروض `uthmani_text` من سجل الآية كما ورد، والمطابقة على العمود
    المطبَّع وحده. تُعاد كتلة الإصدار وحالة مراجعته مع كل استجابة، وتُعاد
    `normalized_query` فيعلم المستعمل بأي صورة بُحث فعلًا."""
    data = await QuranService(session).search_ayahs(q, surah, offset, limit)
    if data is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "NO_ACTIVE_VERSION",
                "message": "لا يوجد إصدار نص مفعَّل، فلا يمكن البحث في الآيات.",
            },
        )
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
