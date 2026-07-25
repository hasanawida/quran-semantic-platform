"""اختبارات المرحلة J — الحدود وترويسات الأمان.

حدّ المعدل يُختبر معزولًا بتطبيق صغير بحدود ضيقة، لأن رفعه في بقية
مجموعة الاختبارات ضروري حتى لا تحجب الاختبارات نفسها.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.core.middleware import (
    MAX_BODY_BYTES,
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.main import app as real_app


def _tiny_app(**overrides) -> TestClient:
    from app.core.config import get_settings

    settings = get_settings()
    saved = {key: getattr(settings, key) for key in overrides}
    for key, value in overrides.items():
        object.__setattr__(settings, key, value)

    application = FastAPI()
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(BodySizeLimitMiddleware)
    application.add_middleware(RateLimitMiddleware)

    @application.middleware("http")
    async def _request_id(request: Request, call_next):
        request.state.request_id = "test"
        return await call_next(request)

    @application.get("/api/v1/ping")
    async def ping():
        return JSONResponse({"ok": True})

    @application.post("/api/v1/echo")
    async def echo():
        return JSONResponse({"ok": True})

    client = TestClient(application)
    client._restore = (settings, saved)  # type: ignore[attr-defined]
    return client


def _restore(client: TestClient) -> None:
    settings, saved = client._restore  # type: ignore[attr-defined]
    for key, value in saved.items():
        object.__setattr__(settings, key, value)


def test_rate_limit_blocks_after_the_configured_burst():
    client = _tiny_app(rate_limit_requests=3, rate_limit_window_seconds=60)
    try:
        for _ in range(3):
            assert client.get("/api/v1/ping").status_code == 200
        blocked = client.get("/api/v1/ping")
        assert blocked.status_code == 429
        body = blocked.json()
        assert body["success"] is False
        assert body["error"]["code"] == "RATE_LIMITED"
        assert blocked.headers["Retry-After"] == "60"
    finally:
        _restore(client)


def test_oversized_body_is_refused_before_parsing():
    client = _tiny_app(rate_limit_requests=1000)
    try:
        response = client.post(
            "/api/v1/echo",
            content=b"x",
            headers={"Content-Length": str(MAX_BODY_BYTES + 1)},
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    finally:
        _restore(client)


def test_security_headers_present_on_api_responses():
    response = TestClient(real_app).get("/api/v1/export/provenance")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert "geolocation=()" in response.headers["Permissions-Policy"]


def test_request_id_header_still_returned():
    response = TestClient(real_app).get("/health")
    assert response.headers.get("X-Request-ID")


def test_internal_errors_do_not_leak_details():
    """المعالج العام يعيد رسالة موحدة بلا أثر داخلي."""
    from app.api.response import error_body

    class _FakeRequest:
        class state:  # noqa: N801
            request_id = "abc"

    body = error_body(_FakeRequest, "INTERNAL_ERROR", "حدث خطأ داخلي غير متوقع.")
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "Traceback" not in str(body)


def test_spoofed_forwarded_ip_cannot_open_a_new_rate_limit_bucket():
    """مفتاح الحد يُشتق من عنوان IP صالح فقط.

    لو وثق الخادم بترويسة X-Forwarded-For من أي عميل صار request.client.host
    قيمة نصية يتحكم بها المهاجم، فيفتح دلوًا جديدًا لكل طلب ويسقط سقف
    محاولات تسجيل الدخول. المفتاح هنا يوحّد كل ما ليس عنوانًا صالحًا."""
    from app.core.middleware import RateLimitMiddleware

    class _FakeClient:
        def __init__(self, host: str) -> None:
            self.host = host

    class _FakeRequest:
        def __init__(self, host: str) -> None:
            self.client = _FakeClient(host)

    keys = {
        RateLimitMiddleware._client_key(_FakeRequest(value))
        for value in ("a1", "a2", "evil, 10.0.0.1", "", "not-an-ip")
    }
    assert keys == {"unparsable-client"}
    assert RateLimitMiddleware._client_key(_FakeRequest("203.0.113.9")) == "203.0.113.9"


def test_production_refuses_to_start_with_the_default_jwt_secret():
    """سر التوقيع الافتراضي معلن في المستودع: تشغيل الإنتاج به يعني
    تزوير رمز لأي حساب. الحارس يفشل الإقلاع بدل أن يمرّره."""
    import os

    from app.core.config import INSECURE_JWT_SECRET, Settings, get_settings

    saved = {k: os.environ.get(k) for k in ("ENVIRONMENT", "JWT_SECRET")}
    get_settings.cache_clear()
    try:
        os.environ["ENVIRONMENT"] = "production"
        os.environ["JWT_SECRET"] = INSECURE_JWT_SECRET
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            get_settings()

        os.environ["JWT_SECRET"] = "short"
        get_settings.cache_clear()
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            get_settings()

        os.environ["JWT_SECRET"] = "x" * 48
        get_settings.cache_clear()
        assert get_settings().is_production
        assert Settings().jwt_secret == "x" * 48
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        get_settings()
