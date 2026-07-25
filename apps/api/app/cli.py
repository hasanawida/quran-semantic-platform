"""أوامر تشغيل خط الصرف (المرحلة D) من سطر الأوامر.

الاستيراد عملية إدارية موثقة لا تجري تلقائيًا عند الإقلاع: هي بطيئة
(~128 ألف مقطع)، ويجب أن تُسجَّل في سجل التدقيق بفاعل معروف.

    python -m app.cli bootstrap         # مخطط + بذر + خط الصرف كاملًا
    python -m app.cli pipeline          # ترميز + استيراد + اشتقاق + فحص
    python -m app.cli tokenize
    python -m app.cli import-morphology [--surahs 1,112,113,114]
    python -m app.cli rebuild-occurrences
    python -m app.cli seed-golden
    python -m app.cli golden-check
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time


def _parse_surahs(value: str | None) -> set[int] | None:
    if not value:
        return None
    return {int(part) for part in value.split(",") if part.strip()}


async def _run(command: str, surahs: set[int] | None) -> int:
    from app.db.session import SessionFactory, engine
    from app.services.morphology import (
        MorphologyError,
        MorphologyService,
        load_morphology_bundle,
    )

    async def step(name: str, coro_factory):
        started = time.time()
        async with SessionFactory() as session:
            result = await coro_factory(MorphologyService(session))
        print(f"  {name}: {json.dumps(result, ensure_ascii=False)}")
        print(f"    ({time.time() - started:.1f} ثانية)")
        return result

    try:
        if command == "bootstrap":
            from app.db.init_db import init_db

            started = time.time()
            await init_db()
            print(f"  تهيئة المخطط والبذر: ({time.time() - started:.1f} ثانية)")
            command = "pipeline"

        if command in ("tokenize", "pipeline"):
            await step("ترميز الكلمات", lambda s: s.tokenize_version(surahs=surahs))

        if command in ("import-morphology", "pipeline"):
            bundle = load_morphology_bundle()
            await step(
                "استيراد التحليل الصرفي",
                lambda s: s.import_bundle(bundle, surahs=surahs),
            )

        if command in ("rebuild-occurrences", "pipeline"):
            await step(
                "اشتقاق مواضع الجذور",
                lambda s: s.rebuild_occurrences(surahs=surahs),
            )

        if command in ("seed-golden", "pipeline"):
            await step("تحميل المواضع المرجعية", lambda s: s.seed_golden_cases())

        if command in ("golden-check", "pipeline"):
            result = await step("فحص المواضع المرجعية", lambda s: s.golden_check())
            if result["failed"]:
                print("فشل الفحص المرجعي:", file=sys.stderr)
                for failure in result["failures"]:
                    print(f"  {failure}", file=sys.stderr)
                return 1
    except MorphologyError as exc:
        print(f"خطأ [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2
    finally:
        await engine.dispose()
    return 0


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="app.cli", description="خط الصرف")
    parser.add_argument(
        "command",
        choices=[
            "bootstrap",
            "pipeline",
            "tokenize",
            "import-morphology",
            "rebuild-occurrences",
            "seed-golden",
            "golden-check",
        ],
    )
    parser.add_argument("--surahs", help="حصر النطاق بأرقام سور مفصولة بفواصل")
    args = parser.parse_args()
    print(f"تنفيذ: {args.command}")
    raise SystemExit(asyncio.run(_run(args.command, _parse_surahs(args.surahs))))


if __name__ == "__main__":
    main()
