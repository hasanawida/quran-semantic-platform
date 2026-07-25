"""عرض التحليل الصرفي للباحث — مقروء للعموم، منسوب لمصادره."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.response import ok
from app.db.session import get_session
from app.services.morphology import MorphologyError, MorphologyService

router = APIRouter(tags=["Morphology"])

_STATUS_BY_CODE = {
    "AYAH_NOT_FOUND": 404,
    "ROOT_NOT_FOUND": 404,
    "NO_ACTIVE_VERSION": 409,
    "NO_FILTERS": 422,
    "INVALID_ROOT": 422,
}


def _err(exc: MorphologyError) -> HTTPException:
    return HTTPException(
        status_code=_STATUS_BY_CODE.get(exc.code, 400),
        detail={"code": exc.code, "message": exc.message},
    )


@router.get("/morphology/ayahs/{surah}/{ayah}")
async def ayah_analysis(
    request: Request,
    surah: int = Path(ge=1, le=114),
    ayah: int = Path(ge=1, le=286),
    session: AsyncSession = Depends(get_session),
):
    """تحليل صرفي لكل كلمة في الآية، مفصولًا بحسب المصدر مع إظهار الاختلاف."""
    try:
        data = await MorphologyService(session).ayah_analysis(surah, ayah)
    except MorphologyError as exc:
        raise _err(exc) from None
    return ok(request, data)


@router.get("/morphology/dimensions")
async def search_dimensions(request: Request):
    """أبعاد البحث الصرفي وقيمها المتاحة بتسمياتها العربية.

    تُقرأ من مصدر واحد فلا تفترق قوائم الواجهة عن ما يقبله الخادم."""
    from app.utils.morphology_tags import (
        FEATURE_LABELS,
        FEATURE_TITLES,
        POS_LABELS_AR,
    )

    dimensions = [
        {
            "key": "pos",
            "title": FEATURE_TITLES["pos"],
            "values": [
                {"value": key, "label": label}
                for key, label in sorted(POS_LABELS_AR.items())
            ],
        }
    ]
    for key, values in FEATURE_LABELS.items():
        dimensions.append(
            {
                "key": key,
                "title": FEATURE_TITLES.get(key, key),
                "values": [
                    {"value": value, "label": label}
                    for value, label in values.items()
                ],
            }
        )
    return ok(request, {"dimensions": dimensions})


@router.get("/morphology/search")
async def search_morphology(
    request: Request,
    pos: str | None = Query(default=None, max_length=16),
    aspect: str | None = Query(default=None, max_length=8),
    verb_form: str | None = Query(default=None, max_length=6),
    voice: str | None = Query(default=None, max_length=4),
    mood: str | None = Query(default=None, max_length=8),
    person: str | None = Query(default=None, max_length=1),
    gender: str | None = Query(default=None, max_length=1),
    grammatical_number: str | None = Query(default=None, max_length=1),
    case_marking: str | None = Query(default=None, max_length=4),
    definiteness: str | None = Query(default=None, max_length=8),
    nominal_form: str | None = Query(default=None, max_length=6),
    root: str | None = Query(default=None, max_length=40),
    lemma: str | None = Query(default=None, max_length=120),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """بحث في التحليل الصرفي بأبعاده — الزمن والوزن والبناء والإعراب."""
    filters = {
        "pos": pos,
        "aspect": aspect,
        "verb_form": verb_form,
        "voice": voice,
        "mood": mood,
        "person": person,
        "gender": gender,
        "grammatical_number": grammatical_number,
        "case_marking": case_marking,
        "definiteness": definiteness,
        "nominal_form": nominal_form,
    }
    try:
        data = await MorphologyService(session).search_analyses(
            filters, root_query=root, lemma=lemma, offset=offset, limit=limit
        )
    except MorphologyError as exc:
        raise _err(exc) from None
    return ok(request, data)
