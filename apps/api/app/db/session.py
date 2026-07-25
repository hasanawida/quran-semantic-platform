from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# SQLite: check_same_thread=False + NullPool لتفادي ربط الاتصالات بحلقة أحداث
# واحدة (يمنع أخطاء "attached to a different loop" في الاختبارات وuvicorn)
if settings.is_sqlite:
    engine = create_async_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )

    # تفعيل مفاتيح الأجنبية في SQLite (معطلة افتراضيًا) لفرض سلامة العلاقات
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

else:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)


SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
