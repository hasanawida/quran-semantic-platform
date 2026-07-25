"""وسائط الأمان (المرحلة J): حدّ المعدل، ترويسات الحماية، حدّ حجم الطلب.

الحدود دفاع في العمق لا بديل عن الصلاحيات: RBAC يبقى المرجع، وهذه تمنع
الإساءة والإرهاق وتضييق سطح الهجوم.

حدّ المعدل هنا في الذاكرة لكل عملية (process): كافٍ لنشر بعملية واحدة،
وفي النشر متعدد العمليات يُستبدل بمخزن مشترك (Redis) — الواجهة نفسها.
"""

from __future__ import annotations

import ipaddress
import time
from collections import deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.response import error_body
from app.core.config import get_settings

settings = get_settings()

# مسارات المصادقة أشد حدًّا: هي هدف تخمين كلمات المرور
_AUTH_PATHS = ("/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh")

# مسارات تقدّم HTML من طرف ثالث (Swagger/ReDoc) تُستثنى من سياسة المحتوى
# المغلقة، وتُعطَّل أصلًا في الإنتاج
_HTML_DOC_PATHS = ("/docs", "/redoc", "/docs/oauth2-redirect")

# تنظيف دلاء حدّ المعدل كل دقيقة — يمنع نمو القاموس بلا حد
_EVICT_EVERY_SECONDS = 60

# 1 ميجابايت يكفي لكل مدخلات المنصة عدا الاستيراد الإداري
MAX_BODY_BYTES = 1_048_576
_LARGE_BODY_ALLOWED = ("/api/v1/admin/quran-versions/import",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """نافذة منزلقة بسيطة لكل (عميل + فئة مسار)."""

    def __init__(self, app) -> None:  # noqa: ANN001
        super().__init__(app)
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._last_evict = 0.0

    @staticmethod
    def _client_key(request: Request) -> str:
        """مفتاح العميل.

        `request.client.host` قد يكون قيمة X-Forwarded-For حين يُشغَّل
        uvicorn بـ `--proxy-headers`. لو وثق الخادم بالترويسة من أي عميل
        صار المفتاح قابلًا للتزوير ويسقط الحد كله؛ لذلك يُرفض هنا كل ما
        ليس عنوان IP صالحًا ويُجمع تحت مفتاح واحد بدل أن يفتح دلوًا جديدًا.
        """
        raw = request.client.host if request.client else ""
        try:
            return str(ipaddress.ip_address(raw.strip()))
        except ValueError:
            return "unparsable-client"

    def _allowed(self, key: tuple[str, str], limit: int, window: int) -> bool:
        now = time.monotonic()
        self._evict(now, window)
        bucket = self._hits.setdefault(key, deque())
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True

    def _evict(self, now: float, window: float) -> None:
        """يحذف الدلاء المنتهية دوريًا.

        بدونه ينمو القاموس بلا حد مع كل مفتاح جديد (مصدر إرهاق ذاكرة)."""
        if now - self._last_evict < _EVICT_EVERY_SECONDS:
            return
        self._last_evict = now
        stale = [
            key
            for key, bucket in self._hits.items()
            if not bucket or now - bucket[-1] > window
        ]
        for key in stale:
            self._hits.pop(key, None)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/"):
            is_auth = path in _AUTH_PATHS
            limit = (
                settings.auth_rate_limit_requests
                if is_auth
                else settings.rate_limit_requests
            )
            window = (
                settings.auth_rate_limit_window_seconds
                if is_auth
                else settings.rate_limit_window_seconds
            )
            bucket = "auth" if is_auth else "api"
            if not self._allowed((self._client_key(request), bucket), limit, window):
                request.state.request_id = getattr(
                    request.state, "request_id", "rate-limited"
                )
                return JSONResponse(
                    status_code=429,
                    content=error_body(
                        request,
                        "RATE_LIMITED",
                        "تجاوزت حد الطلبات المسموح. أعد المحاولة بعد قليل.",
                    ),
                    headers={"Retry-After": str(window)},
                )
        return await call_next(request)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path not in _LARGE_BODY_ALLOWED:
            declared = request.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
                request.state.request_id = getattr(
                    request.state, "request_id", "too-large"
                )
                return JSONResponse(
                    status_code=413,
                    content=error_body(
                        request, "PAYLOAD_TOO_LARGE", "حجم الطلب أكبر من المسموح."
                    ),
                )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """ترويسات حماية. الـ API لا يقدّم HTML، فسياسة المحتوى مغلقة تمامًا."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        if request.url.path not in _HTML_DOC_PATHS:
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
            )
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response
