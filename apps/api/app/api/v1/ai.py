"""مسار بوابة الذكاء الاصطناعي (المرحلة I).

لا توجد ميزة ذكاء اصطناعي في المنصة بعد — بحكم خارطة التنفيذ. هذا المسار
يعرض شروط التشغيل المسبقة وما تحقق منها، ليكون المنع مرئيًا لا ضمنيًا.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.response import ok
from app.db.session import get_session
from app.services.ai_gate import AIGateService

router = APIRouter(tags=["AI Gate"], prefix="/ai")


@router.get("/readiness")
async def readiness(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    return ok(request, await AIGateService(session).readiness())
