"""بيان المنهج والمصادر ومواضع الخلاف — مفتوح للعموم.

يُخدم من الشيفرة لا من وثيقة جانبية: ما يُقال عن مصادر المنصة وخلافاتها
يجب أن يُختبر ويُصدَّر مع البيانات، لا أن يتخلّف عنها.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.response import ok
from app.content.methodology import methodology_payload

router = APIRouter(tags=["Methodology"])


@router.get("/methodology")
async def methodology(request: Request):
    return ok(request, methodology_payload())
