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


async def init_db() -> None:
    """يُستدعى عند الإقلاع في التطوير: ينشئ المخطط ويبذر من الحزمة إن كانت
    القاعدة فارغة."""
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
