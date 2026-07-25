"""حارس مسار البذر في الإنتاج.

**لماذا هذا الملف موجود:** فحص جاهزية النشر في 2026-07-25 وجد أن الأمر
الموثَّق للبذر في الإنتاج (`bootstrap`) لا يبذر شيئًا ثم يفشل، لأن
`init_db()` تعود مبكرًا حين `AUTO_CREATE_SCHEMA=false` — وهي قيمة الإنتاج.
النتيجة كانت: موقع حيّ بقاعدة فارغة، ولا إنذار.

فالاختبار هنا لا يُشغَّل داخل قاعدة الاختبارات المشتركة، بل **يحاكي
الإنتاج فعلًا**: قاعدة جديدة، ومخطط منشأ خطوةً مستقلة، ثم أمر البذر
بالبيئة الإنتاجية نفسها. لو عاد العطل لسقط هذا الاختبار وحده.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]


def _run(code_or_args: list[str], db_path: Path, auto_create: str) -> subprocess.CompletedProcess:
    """يشغّل عملية بايثون مستقلة بقاعدة بيانات معزولة.

    عملية مستقلة لا استدعاء مباشر: المحرك و`get_settings` كلاهما مُخبَّأ
    على مستوى الوحدة، فلا سبيل إلى تبديل القاعدة داخل العملية نفسها بلا
    ترقيع يُبطل معنى الاختبار."""
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{db_path.as_posix()}",
        "ENVIRONMENT": "test",
        "AUTO_CREATE_SCHEMA": auto_create,
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [sys.executable, *code_or_args],
        cwd=API_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )


@pytest.fixture
def fresh_db():
    with tempfile.TemporaryDirectory() as folder:
        yield Path(folder) / "seed_cli_test.db"


def test_seed_command_seeds_a_production_style_database(fresh_db):
    """المخطط ينشأ خطوةً، ثم `app.cli seed` يبذر رغم AUTO_CREATE_SCHEMA=false.

    هذا هو تسلسل الإنتاج حرفيًا كما في docs/DEPLOYMENT_AR.md §3 و§4."""
    # 1) المخطط — في الإنتاج تنشئه Alembic بدور المالك
    schema = _run(
        [
            "-c",
            "import asyncio;"
            "from app.db.init_db import create_schema;"
            "from app.db.session import engine;"
            "asyncio.run(create_schema());"
            "asyncio.run(engine.dispose())",
        ],
        fresh_db,
        auto_create="true",
    )
    assert schema.returncode == 0, schema.stderr

    # 2) البذر — بالبيئة الإنتاجية: الحارس مغلق
    seeded = _run(["-m", "app.cli", "seed"], fresh_db, auto_create="false")
    assert seeded.returncode == 0, seeded.stderr
    assert '"seeded": true' in seeded.stdout.lower(), seeded.stdout

    # 3) الشاهد الحاسم: المصحف كامل في القاعدة
    count = _run(
        [
            "-c",
            "import asyncio, json;"
            "from sqlalchemy import func, select;"
            "from app.db.session import SessionFactory, engine;"
            "from app.models import Ayah, Surah;"
            "\n"
            "async def main():\n"
            "    async with SessionFactory() as s:\n"
            "        a = await s.scalar(select(func.count()).select_from(Ayah))\n"
            "        u = await s.scalar(select(func.count()).select_from(Surah))\n"
            "    await engine.dispose()\n"
            "    print(json.dumps({'ayahs': a, 'surahs': u}))\n"
            "\n"
            "asyncio.run(main())",
        ],
        fresh_db,
        auto_create="false",
    )
    assert count.returncode == 0, count.stderr
    totals = json.loads(count.stdout.strip().splitlines()[-1])
    assert totals == {"ayahs": 6236, "surahs": 114}


def test_seed_is_idempotent_and_says_so(fresh_db):
    """تكرار البذر لا يضاعف الآيات ولا يفشل — يقول إن القاعدة مبذورة."""
    schema = _run(
        [
            "-c",
            "import asyncio;"
            "from app.db.init_db import create_schema;"
            "from app.db.session import engine;"
            "asyncio.run(create_schema());"
            "asyncio.run(engine.dispose())",
        ],
        fresh_db,
        auto_create="true",
    )
    assert schema.returncode == 0, schema.stderr

    first = _run(["-m", "app.cli", "seed"], fresh_db, auto_create="false")
    assert first.returncode == 0, first.stderr

    second = _run(["-m", "app.cli", "seed"], fresh_db, auto_create="false")
    assert second.returncode == 0, second.stderr
    assert '"seeded": false' in second.stdout.lower(), second.stdout
    assert "مبذورة" in second.stdout


def test_seed_without_a_schema_says_what_to_do(fresh_db):
    """قاعدة بلا هجرات: يخرج برمز غير صفري ويسمّي الأمر المطلوب.

    الصمت هنا أسوأ من الفشل — لأن الفشل الصامت هو ما أنتج العطل الأصلي."""
    result = _run(["-m", "app.cli", "seed"], fresh_db, auto_create="false")
    assert result.returncode == 3, (result.returncode, result.stdout, result.stderr)
    assert "alembic upgrade head" in result.stderr


def test_init_db_still_returns_early_when_the_schema_guard_is_off():
    """التمييز مقصود: `init_db` أداة تطوير تحترم الحارس، و`seed_only` لا.

    لو سوّى أحدهم بينهما لعاد الإقلاع في الإنتاج ينشئ المخطط من النماذج
    متجاوزًا Alembic — وهو ما مُنع عمدًا."""
    import inspect

    from app.db import init_db as module

    source = inspect.getsource(module.init_db)
    assert "auto_create_schema" in source
    assert "auto_create_schema" not in inspect.getsource(module.seed_only)
