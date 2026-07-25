import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.deps import AuthHTTPError
from app.api.response import error_body
from app.api.v1.router import router
from app.core.config import get_settings
from app.core.middleware import (
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.db.init_db import init_db
from app.db.session import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield
    await engine.dispose()


_docs_enabled = settings.enable_docs and not settings.is_production

app = FastAPI(
    title="Quran Semantic Research API",
    version="0.1.0",
    description="واجهة تأسيسية لمنصة الاستقراء الدلالي.",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# ترتيب الوسائط عكس ترتيب الإضافة عند التنفيذ: الحد ثم الحجم ثم الترويسات
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict):
        code = exc.detail.get("code", "HTTP_ERROR")
        message = exc.detail.get("message", "")
    else:
        code = "HTTP_ERROR"
        message = str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(request, code, message),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=error_body(request, "VALIDATION_ERROR", "المدخلات غير صالحة."),
    )


@app.exception_handler(AuthHTTPError)
async def auth_exception_handler(request: Request, exc: AuthHTTPError):
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(request, exc.code, exc.message),
        headers=headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # لا تُكشف تفاصيل الخطأ الداخلي للعميل
    return JSONResponse(
        status_code=500,
        content=error_body(request, "INTERNAL_ERROR", "حدث خطأ داخلي غير متوقع."),
    )


app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    db_ok = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return {"status": status, "database": "ok" if db_ok else "unavailable"}
