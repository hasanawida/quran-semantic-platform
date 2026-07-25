"""إنشاء المخطط وبذر بيانات التطوير (SQLite). في الإنتاج يُدار المخطط عبر Alembic."""

from __future__ import annotations

from sqlalchemy import select

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app.models import Ayah  # noqa: F401 — ضمان تحميل كل النماذج
import app.db.audit  # noqa: F401 — تفعيل محرّك حماية سجل التدقيق

settings = get_settings()


async def create_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def is_seeded() -> bool:
    from app.db.session import SessionFactory

    async with SessionFactory() as session:
        result = await session.execute(select(Ayah.id).limit(1))
        return result.first() is not None


class SeedError(RuntimeError):
    """يوقف البذر برسالة تقول ما العمل، لا بأثر استثناء."""


async def seed_only() -> dict:
    """يبذر النص من الحزمة **بمعزل عن حارس إنشاء المخطط**.

    هذا هو مسار الإنتاج. `init_db()` أدناه تعود مبكرًا حين
    `AUTO_CREATE_SCHEMA=false` — وهي قيمة الإنتاج في `Dockerfile` وفي
    `docker-compose.prod.yml` — فكان أمر البذر الموثَّق يخرج بلا أن يبذر
    شيئًا، ثم يسقط خط المعالجة بـ`NO_ACTIVE_VERSION`، ويبقى موقع حيّ
    بقاعدة فارغة. (رصده فحص جاهزية النشر في 2026-07-25.)

    الفصل صحيح منطقيًا كذلك: البذر **إدخال بيانات** لا DDL، فدور التطبيق
    غير المميز يملكه، والمخطط تنشئه Alembic خطوةً مستقلة بدور المالك.

    يُرجع تقريرًا، ولا يبذر مرتين: تكراره آمن."""
    try:
        already = await is_seeded()
    except Exception as exc:  # جدول مفقود ⇐ المخطط لم يُهاجَر بعد
        raise SeedError(
            "تعذّر قراءة جدول الآيات. شغّل الهجرات أولًا:\n"
            "  alembic upgrade head\n"
            f"(الأصل: {type(exc).__name__})"
        ) from exc

    if already:
        return {"seeded": False, "reason": "القاعدة مبذورة أصلًا"}

    from app.db.seed import seed_from_bundle

    await seed_from_bundle()
    return {"seeded": True}


async def init_db() -> None:
    """يُستدعى عند الإقلاع في التطوير: ينشئ المخطط ويبذر من الحزمة إن كانت
    القاعدة فارغة.

    **لا يُستعمل في الإنتاج** — استعمل `seed_only()` عبر `app.cli seed`."""
    if not settings.auto_create_schema:
        return
    await create_schema()
    if not await is_seeded():
        from app.db.seed import seed_from_bundle

        await seed_from_bundle()

    # حسابات تجريبية للتطوير فقط (لا تُنشأ في الإنتاج)
    if not settings.is_production:
        from app.db.bootstrap import bootstrap_dev_users

        await bootstrap_dev_users()
