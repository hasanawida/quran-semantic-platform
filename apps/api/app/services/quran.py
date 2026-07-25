from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quran import Ayah, QuranTextVersion, Surah


class QuranService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _active_version(self) -> QuranTextVersion | None:
        result = await self.session.execute(
            select(QuranTextVersion).where(QuranTextVersion.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def list_surahs(self) -> list[dict]:
        version = await self._active_version()
        if version is None:
            return []
        # عدد الآيات يُشتق من آيات الإصدار النشط لا يخزَّن عالميًا
        counts = dict(
            (
                await self.session.execute(
                    select(Ayah.surah_number, func.count(Ayah.id))
                    .where(Ayah.text_version_id == version.id)
                    .group_by(Ayah.surah_number)
                )
            ).all()
        )
        result = await self.session.execute(select(Surah).order_by(Surah.number))
        return [
            {
                "number": s.number,
                "arabic_name": s.arabic_name,
                "revelation_type": s.revelation_type,
                "ayah_count": counts.get(s.number, 0),
            }
            for s in result.scalars()
        ]

    async def get_surah(
        self, surah: int, offset: int = 0, limit: int = 50
    ) -> dict | None:
        """سورة كاملة بآياتها وكلماتها المرقَّمة.

        البسملة تُعاد **بيانًا للسورة** لا جزءًا من آيتها الأولى، فيوافق
        العرضُ العدَّ الكوفي المعلن في الإصدار. الفاتحة بسملتها آية مستقلة
        (`basmala_text` فارغ)، وبراءة لا بسملة لها.

        كل آية تحمل مواضع كلماتها (`char_start`/`char_end`) ليُبنى التمييز
        عليها بالقطع من النص، لا بإعادة تركيبه من الكلمات."""
        version = await self._active_version()
        if version is None:
            return None
        surah_row = await self.session.get(Surah, surah)
        if surah_row is None:
            return None

        total = await self.session.scalar(
            select(func.count(Ayah.id)).where(
                Ayah.text_version_id == version.id, Ayah.surah_number == surah
            )
        )
        if not total:
            return None

        rows = (
            await self.session.execute(
                select(Ayah.id, Ayah.ayah_number, Ayah.uthmani_text)
                .where(
                    Ayah.text_version_id == version.id,
                    Ayah.surah_number == surah,
                )
                .order_by(Ayah.ayah_number)
                .offset(offset)
                .limit(limit)
            )
        ).all()

        from app.models.morphology import Token

        words_by_ayah: dict = {}
        if rows:
            for ayah_id, number, start, end in (
                await self.session.execute(
                    select(
                        Token.ayah_id,
                        Token.word_number,
                        Token.char_start,
                        Token.char_end,
                    )
                    .where(Token.ayah_id.in_([r[0] for r in rows]))
                    .order_by(Token.ayah_id, Token.word_number)
                )
            ).all():
                words_by_ayah.setdefault(ayah_id, []).append(
                    {"word_number": number, "char_start": start, "char_end": end}
                )

        return {
            "surah": {
                "number": surah_row.number,
                "arabic_name": surah_row.arabic_name,
                "revelation_type": surah_row.revelation_type,
                "basmala_text": surah_row.basmala_text,
                "ayah_count": total,
            },
            "version": {
                "version_code": version.version_code,
                "riwayah": version.riwayah,
                "script_type": version.script_type,
                "counting_system": version.counting_system,
                "review_status": version.status.value,
            },
            "ayahs": [
                {
                    "ayah_number": number,
                    "uthmani_text": text,
                    "words": words_by_ayah.get(ayah_id, []),
                }
                for ayah_id, number, text in rows
            ],
            "pagination": {"total": total, "offset": offset, "limit": limit},
        }

    async def get_ayah(self, surah: int, ayah: int) -> dict | None:
        version = await self._active_version()
        if version is None:
            return None
        result = await self.session.execute(
            select(Ayah, Surah.arabic_name)
            .join(Surah, Surah.number == Ayah.surah_number)
            .where(
                Ayah.text_version_id == version.id,
                Ayah.surah_number == surah,
                Ayah.ayah_number == ayah,
            )
        )
        row = result.first()
        if row is None:
            return None
        ayah_row, surah_name = row
        return {
            "surah_number": ayah_row.surah_number,
            "surah_name": surah_name,
            "ayah_number": ayah_row.ayah_number,
            "uthmani_text": ayah_row.uthmani_text,
            "version_code": version.version_code,
            "riwayah": version.riwayah,
            "script_type": version.script_type,
            "review_status": version.status.value,
        }
