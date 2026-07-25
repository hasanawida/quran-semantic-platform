from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# قاعدة بيانات التطوير الافتراضية: SQLite محلي بلا أي تثبيت.
# في الإنتاج تُضبط DATABASE_URL إلى postgresql+asyncpg://...
_DEV_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "app.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = f"sqlite+aiosqlite:///{_DEV_DB_PATH.as_posix()}"
    redis_url: str = "redis://localhost:6379/0"
    allowed_origins: str = "http://localhost:3000"

    # الأمان — يجب ضبط JWT_SECRET في الإنتاج بقيمة سرية قوية
    jwt_secret: str = "dev-insecure-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 14

    # يُنشأ المخطط تلقائيًا في التطوير (SQLite)؛ في الإنتاج يُدار عبر Alembic
    auto_create_schema: bool = True

    # حدود المعدل (نافذة/طلبات) على المسارات العامة
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    # مسارات المصادقة أشد: هي هدف تخمين كلمات المرور
    auth_rate_limit_requests: int = 10
    auth_rate_limit_window_seconds: int = 60
    # توثيق Swagger/ReDoc: سطح معلومات لا لزوم له في الإنتاج
    enable_docs: bool = True
    # ميزات الذكاء الاصطناعي: معطَّلة افتراضيًا، ولا تعمل إلا إذا اجتازت
    # بوابة الشروط المسبقة أيضًا (app/services/ai_gate.py)
    ai_features_enabled: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


INSECURE_JWT_SECRET = "dev-insecure-secret-change-in-production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # حارس إقلاع: سر التوقيع الافتراضي معلن في المستودع، فتشغيل الإنتاج
    # به يعني أن أي أحد يزوّر رمزًا لأي حساب — بما فيه المدير التقني.
    # الفشل هنا مقصود: تشغيل غير آمن أسوأ من عدم التشغيل.
    if settings.is_production and (
        settings.jwt_secret == INSECURE_JWT_SECRET or len(settings.jwt_secret) < 32
    ):
        raise RuntimeError(
            "JWT_SECRET غير صالح للإنتاج: يجب ضبطه بسر قوي (32 محرفًا فأكثر) "
            "ولا يجوز ترك القيمة الافتراضية. ولّده بـ: openssl rand -base64 48"
        )

    # قيم القوالب: `${VAR:?required}` في compose يرفض **الفارغ** وحده،
    # ولا يرفض `example.org`. فمن نسخ `.env.production.example` ولم يملأه
    # يُقلع بأصل خاطئ فينكسر CORS صامتًا على المتصفح. والحارس هنا لأن
    # compose لا يستطيعه. (نبّهت إليه مراجعة خارجية في 2026-07-26.)
    if settings.is_production:
        for name, value in (("ALLOWED_ORIGINS", settings.allowed_origins),):
            if any(token in value for token in ("example.org", "example.com")):
                raise RuntimeError(
                    f"{name} ما زال على قيمة القالب ({value}). املأ ملف "
                    ".env بقيم موقعك الحقيقية قبل تشغيل الإنتاج."
                )
        if "localhost" in settings.allowed_origins:
            raise RuntimeError(
                "ALLOWED_ORIGINS يحوي localhost في الإنتاج — هذا أصل "
                "تطوير لا أصل موقع منشور."
            )

    return settings
