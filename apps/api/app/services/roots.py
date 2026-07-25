from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.language import Root, RootOccurrence
from app.models.quran import Ayah, QuranTextVersion, Surah
from app.utils.arabic import normalize_root_input


class RootService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _active_version_id(self):
        result = await self.session.execute(
            select(QuranTextVersion.id).where(QuranTextVersion.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def _get_root_row(self, normalized: str) -> Root | None:
        result = await self.session.execute(
            select(Root).where(Root.normalized_root == normalized)
        )
        return result.scalar_one_or_none()

    async def _root_stats(self, root: Root, version_id) -> dict:
        occ_count = await self.session.scalar(
            select(func.count(RootOccurrence.id))
            .join(Ayah, Ayah.id == RootOccurrence.ayah_id)
            .where(
                RootOccurrence.root_id == root.id,
                Ayah.text_version_id == version_id,
            )
        )
        ayah_count = await self.session.scalar(
            select(func.count(func.distinct(RootOccurrence.ayah_id)))
            .join(Ayah, Ayah.id == RootOccurrence.ayah_id)
            .where(
                RootOccurrence.root_id == root.id,
                Ayah.text_version_id == version_id,
            )
        )
        return {
            "display_root": root.display_root,
            "normalized_root": root.normalized_root,
            "status": root.status.value,
            "confidence": root.confidence.value,
            "occurrence_count": occ_count or 0,
            "ayah_count": ayah_count or 0,
        }

    async def get_root(self, query: str) -> dict | None:
        normalized = normalize_root_input(query)
        if not normalized:
            return None
        root = await self._get_root_row(normalized)
        if root is None:
            return None
        version_id = await self._active_version_id()
        if version_id is None:
            return None
        return await self._root_stats(root, version_id)

    async def get_occurrences(
        self, query: str, offset: int, limit: int
    ) -> dict | None:
        normalized = normalize_root_input(query)
        if not normalized:
            return None
        root = await self._get_root_row(normalized)
        if root is None:
            return None
        version_id = await self._active_version_id()
        if version_id is None:
            return None

        # الآيات المرتبطة بالجذر، مرتبة بترتيب المصحف، مع صفحات
        ayah_subq = (
            select(
                RootOccurrence.ayah_id,
                Ayah.surah_number,
                Ayah.ayah_number,
            )
            .join(Ayah, Ayah.id == RootOccurrence.ayah_id)
            .where(
                RootOccurrence.root_id == root.id,
                Ayah.text_version_id == version_id,
            )
            .group_by(RootOccurrence.ayah_id, Ayah.surah_number, Ayah.ayah_number)
            .order_by(Ayah.surah_number, Ayah.ayah_number)
        )
        total_ayahs = await self.session.scalar(
            select(func.count()).select_from(ayah_subq.subquery())
        )
        page = (await self.session.execute(ayah_subq.offset(offset).limit(limit))).all()

        items = []
        for ayah_id, surah_number, ayah_number in page:
            ayah_row = await self.session.get(Ayah, ayah_id)
            surah_name = await self.session.scalar(
                select(Surah.arabic_name).where(Surah.number == surah_number)
            )
            words = (
                await self.session.execute(
                    select(RootOccurrence.word_number, RootOccurrence.is_highlight_safe)
                    .where(
                        RootOccurrence.root_id == root.id,
                        RootOccurrence.ayah_id == ayah_id,
                    )
                    .order_by(RootOccurrence.word_number)
                )
            ).all()
            word_indexes = [w for w, safe in words if safe]
            items.append(
                {
                    "surah_number": surah_number,
                    "surah_name": surah_name,
                    "ayah_number": ayah_number,
                    "uthmani_text": ayah_row.uthmani_text,
                    "word_indexes": word_indexes,
                }
            )

        return {
            "root": await self._root_stats(root, version_id),
            "occurrences": items,
            "pagination": {
                "total_ayahs": total_ayahs or 0,
                "offset": offset,
                "limit": limit,
            },
        }
