"""تهيئة الاختبارات: قاعدة بيانات SQLite مؤقتة مبذورة مرة واحدة للجلسة.

يُضبط DATABASE_URL قبل استيراد أي وحدة من التطبيق حتى يستخدم المحرك قاعدة
الاختبار لا قاعدة التطوير."""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

_TEST_DB = Path(tempfile.gettempdir()) / "qsp_test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}"
os.environ["ENVIRONMENT"] = "test"
os.environ["AUTO_CREATE_SCHEMA"] = "true"
# حدود المعدل تُرفع في الاختبارات حتى لا تحجب مجموعة الاختبارات نفسها؛
# سلوك الحد نفسه مُختبَر معزولًا في tests/test_security.py
os.environ["RATE_LIMIT_REQUESTS"] = "1000000"
os.environ["AUTH_RATE_LIMIT_REQUESTS"] = "1000000"


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    # قاعدة نظيفة لكل جلسة اختبار
    if _TEST_DB.exists():
        _TEST_DB.unlink()

    async def _build():
        from app.db.init_db import create_schema
        from app.db.seed import seed_from_bundle

        await create_schema()
        await seed_from_bundle()
        from app.db.session import engine

        await engine.dispose()

    asyncio.run(_build())
    yield
