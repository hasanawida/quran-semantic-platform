"""مقارنة الجذور بتوزيعها على المصحف (المقترح 3).

**عرض بيانات لا حكم دلالي.** الاشتراك في الورود لا يعني الترادف، ولا
تُحسب هنا أي «نسبة تشابه» ولا يُقترح أي تقارب. كل استنتاج دلالي مكانه
الادعاءات بأدلتها ومراجعيها — وهذا هو الفرق بين «البيانات» و«الدعوى»
في هذه المنصة.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.language import Root, RootOccurrence
from app.models.quran import Ayah, QuranTextVersion, Surah
from app.utils.arabic import normalize_root_input

MAX_COMPARED_ROOTS = 5

COMPARISON_NOTICE = (
    "مقارنة توزيع لا حكم دلالي: الاشتراك في الورود لا يعني الترادف، ولا "
    "تُحسب هنا أي نسبة تشابه. كل استنتاج دلالي مكانه الادعاءات بأدلتها "
    "ومراجعيها."
)


class RootComparisonError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


class RootComparisonService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _resolve(self, queries: list[str]) -> list[Root]:
        cleaned = [q for q in (query.strip() for query in queries) if q]
        if len(cleaned) < 2:
            raise RootComparisonError(
                "TOO_FEW_ROOTS", "المقارنة تحتاج جذرين مختلفين على الأقل."
            )
        if len(cleaned) > MAX_COMPARED_ROOTS:
            raise RootComparisonError(
                "TOO_MANY_ROOTS",
                f"لا تُقارن أكثر من {MAX_COMPARED_ROOTS} جذور في مرة واحدة.",
            )

        resolved: list[Root] = []
        seen: set[str] = set()
        for query in cleaned:
            key = normalize_root_input(query)
            if not key:
                raise RootComparisonError(
                    "INVALID_ROOT", f"مدخل غير صالح لجذر: {query}"
                )
            if key in seen:
                continue
            seen.add(key)
            root = (
                await self.session.execute(
                    select(Root).where(Root.normalized_root == key)
                )
            ).scalar_one_or_none()
            if root is None:
                raise RootComparisonError(
                    "ROOT_NOT_FOUND", f"لا يوجد جذر بالمفتاح {key}"
                )
            resolved.append(root)

        if len(resolved) < 2:
            # صور مختلفة لجذر واحد (سأل/سءل/سؤل) تعود إلى مفتاح واحد
            raise RootComparisonError(
                "TOO_FEW_ROOTS", "الجذور المدخلة تعود إلى مفتاح واحد."
            )
        return resolved

    async def compare(self, queries: list[str], limit: int = 30) -> dict:
        roots = await self._resolve(queries)

        version_id = await self.session.scalar(
            select(QuranTextVersion.id).where(QuranTextVersion.is_active.is_(True))
        )
        if version_id is None:
            raise RootComparisonError("NO_ACTIVE_VERSION", "لا يوجد إصدار نص مفعَّل.")

        surah_rows = (
            await self.session.execute(
                select(Surah.number, Surah.arabic_name, Surah.revelation_type)
            )
        ).all()
        surah_names = {n: name for n, name, _t in surah_rows}
        revelation = {n: kind for n, _name, kind in surah_rows}

        payload = []
        ayahs_by_root: dict[str, set[tuple[int, int]]] = {}
        ayah_ids: dict[tuple[int, int], object] = {}

        for root in roots:
            rows = (
                await self.session.execute(
                    select(
                        Ayah.id,
                        Ayah.surah_number,
                        Ayah.ayah_number,
                        func.count(RootOccurrence.id),
                    )
                    .join(RootOccurrence, RootOccurrence.ayah_id == Ayah.id)
                    .where(
                        RootOccurrence.root_id == root.id,
                        Ayah.text_version_id == version_id,
                    )
                    .group_by(Ayah.id, Ayah.surah_number, Ayah.ayah_number)
                )
            ).all()

            positions = set()
            by_surah: dict[int, int] = {}
            for ayah_id, surah, ayah, count in rows:
                positions.add((surah, ayah))
                ayah_ids[(surah, ayah)] = ayah_id
                by_surah[surah] = by_surah.get(surah, 0) + count
            ayahs_by_root[root.normalized_root] = positions

            meccan = sum(
                count
                for surah, count in by_surah.items()
                if revelation.get(surah) == "Meccan"
            )
            total = sum(by_surah.values())
            payload.append(
                {
                    "display_root": root.display_root,
                    "normalized_root": root.normalized_root,
                    "status": root.status.value,
                    "confidence": root.confidence.value,
                    "occurrence_count": total,
                    "ayah_count": len(positions),
                    "surah_count": len(by_surah),
                    # نوع النزول بيان وصفي من بيانات السور، لا ترتيب نزول
                    "by_revelation": {"meccan": meccan, "medinan": total - meccan},
                    "by_surah": [
                        {
                            "surah_number": surah,
                            "surah_name": surah_names.get(surah),
                            "count": count,
                        }
                        for surah, count in sorted(by_surah.items())
                    ],
                }
            )

        keys = list(ayahs_by_root)
        shared_ayahs = set.intersection(*(ayahs_by_root[k] for k in keys))
        shared_surahs = set.intersection(
            *({surah for surah, _ayah in ayahs_by_root[k]} for k in keys)
        )

        shared_items = []
        for surah, ayah in sorted(shared_ayahs)[:limit]:
            ayah_id = ayah_ids[(surah, ayah)]
            text = await self.session.scalar(
                select(Ayah.uthmani_text).where(Ayah.id == ayah_id)
            )
            per_root = {}
            for root in roots:
                words = (
                    await self.session.execute(
                        select(RootOccurrence.word_number)
                        .where(
                            RootOccurrence.root_id == root.id,
                            RootOccurrence.ayah_id == ayah_id,
                            RootOccurrence.is_highlight_safe.is_(True),
                        )
                        .order_by(RootOccurrence.word_number)
                    )
                ).scalars()
                per_root[root.display_root] = list(words)
            shared_items.append(
                {
                    "surah_number": surah,
                    "surah_name": surah_names.get(surah),
                    "ayah_number": ayah,
                    "uthmani_text": text,
                    "word_indexes_by_root": per_root,
                }
            )

        return {
            "roots": payload,
            "shared": {
                "ayah_count": len(shared_ayahs),
                "surah_count": len(shared_surahs),
                "surahs": [
                    {"surah_number": s, "surah_name": surah_names.get(s)}
                    for s in sorted(shared_surahs)
                ],
                "ayahs": shared_items,
                "shown": len(shared_items),
            },
            "notice": COMPARISON_NOTICE,
        }
