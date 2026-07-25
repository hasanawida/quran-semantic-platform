from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.response import ok
from app.db.session import get_session
from app.models.language import Root
from app.models.quran import Ayah, QuranTextVersion

router = APIRouter(tags=["Meta"])


@router.get("/meta")
async def meta(request: Request, session: AsyncSession = Depends(get_session)):
    version = (
        await session.execute(
            select(QuranTextVersion).where(QuranTextVersion.is_active.is_(True))
        )
    ).scalar_one_or_none()

    data = {
        "api_version": "v1",
        "application_version": "0.1.0",
        "data_release": version.version_code if version else "none",
        "review_status": version.status.value if version else "none",
        "counts": {},
        "warning": (
            "البيانات مستوردة من مصادر خارجية موثقة، لم تعتمد بمراجعة المنصة "
            "المزدوجة بعد."
            if version
            else "لا يوجد إصدار نص نشط."
        ),
    }
    if version:
        data["counts"] = {
            "ayahs": await session.scalar(
                select(func.count(Ayah.id)).where(
                    Ayah.text_version_id == version.id
                )
            ),
            "roots": await session.scalar(select(func.count(Root.id))),
        }
    return ok(request, data)
