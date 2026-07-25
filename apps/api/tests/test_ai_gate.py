"""اختبارات المرحلة I — بوابة الذكاء الاصطناعي.

لا توجد ميزة ذكاء اصطناعي بعد بحكم خارطة التنفيذ؛ المطلوب أن يكون المنع
صريحًا وقابلًا للفحص، وأن يبقى معطَّلًا ما دامت شروط السلامة ناقصة.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionFactory
from app.main import app
from app.services.ai_gate import AIDisabledError, AIGateService


def client() -> TestClient:
    return TestClient(app)


def _readiness() -> dict:
    async def _run():
        async with SessionFactory() as session:
            return await AIGateService(session).readiness()

    return asyncio.run(_run())


def test_readiness_endpoint_lists_every_precondition():
    body = client().get("/api/v1/ai/readiness").json()
    assert body["success"] is True
    data = body["data"]
    keys = {check["key"] for check in data["checks"]}
    assert {
        "active_text_version",
        "text_version_validated",
        "text_version_double_approved",
        "golden_cases",
        "morphology_conflicts_resolved",
        "morphology_sources_attributed",
        "scholarly_sources_reviewed",
        "no_open_disputes",
        "golden_cases_seeded",
    } <= keys
    assert "لا تبدأ ميزات الذكاء الاصطناعي" in data["policy"]


def test_ai_is_disabled_while_preconditions_are_unmet():
    data = _readiness()
    # الإصدار المبذور مستورد ولم يعتمده مراجعان — فالبوابة يجب أن تمنع
    assert data["ready"] is False
    assert data["enabled"] is False
    unmet_keys = {check["key"] for check in data["unmet"]}
    assert "text_version_double_approved" in unmet_keys


def test_require_enabled_raises_with_the_unmet_reasons():
    async def _run():
        async with SessionFactory() as session:
            with pytest.raises(AIDisabledError) as exc:
                await AIGateService(session).require_enabled()
            return exc.value

    error = asyncio.run(_run())
    assert error.code == "AI_DISABLED"
    assert error.unmet
    assert all("title" in item for item in error.unmet)


def test_flag_alone_cannot_enable_ai():
    """رفع العلم في الإعدادات لا يكفي: البوابة تبقى الحكم."""
    from app.core.config import get_settings

    settings = get_settings()
    original = settings.ai_features_enabled
    object.__setattr__(settings, "ai_features_enabled", True)
    try:
        data = _readiness()
        assert data["ready"] is False
        assert data["enabled"] is False
    finally:
        object.__setattr__(settings, "ai_features_enabled", original)
