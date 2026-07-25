"""قراءة المصحف: الفهرست والسور والآيات والبحث النصي.

**الخط الأحمر الحاكم لهذا الملف:** المطابقة تقع على العمود المطبَّع
(`plain_search_text`) والعرض يأتي من سجل الآية (`uthmani_text`) حرفيًا.
النص لا يُعاد تركيبه من كلماته، ولا يُعاد أي عمود مطبَّع في الاستجابة.
"""


from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quran import Ayah, QuranTextVersion, Surah
from app.utils.arabic import (
    normalize_arabic_search,
    normalize_search_skeleton,
    normalize_surah_name,
)

# محرف هروب LIKE — يمنع أن يصير «%» أو «_» في طلب المستعمل محرفَ بدل
LIKE_ESCAPE = "/"

# أقل طول لمفتاح الهيكل حتى تُفعَّل الطبقة التقريبية. قياس على الإصدار
# النشط: مفتاح من حرفين يفيض ضجيجًا (طلب «إله» مفتاحه «له» فيطابق 2687
# آية مقابل 191 بالمطابقة الصارمة)، ومن ثلاثة فأكثر ينضبط.
MIN_SKELETON_LENGTH = 3

# أقل طول لكلمة الطلب في التمييز الاحتياطي — يمنع تمييز حرف واحد في كل كلمة
MIN_FALLBACK_WORD = 2


def _word_window(values: list[str], target: list[str]) -> set[int]:
    """فهارس نافذة متتالية من الكلمات تساوي كلمات الطلب تمامًا."""
    if not target or len(target) > len(values):
        return set()
    hits: set[int] = set()
    for start in range(len(values) - len(target) + 1):
        if values[start : start + len(target)] == target:
            hits.update(range(start, start + len(target)))
    return hits


def _filter_surahs(surahs: list[dict], query: str) -> list[dict]:
    """ترشيح السور بالرقم أو بمفتاح الاسم — خادميًا لا في المتصفح.

    التطبيع تنفيذ واحد في بايثون بلا نظير له في TypeScript، فلا تفترق
    نتيجة الخادم عن نتيجة الواجهة بمرور الوقت.

    الاتجاه مقصود: **الطلب** بادئة أو جزء من الاسم، لا العكس. الاتجاه
    المعكوس يجعل السور ذوات الاسم الحرف الواحد (ص، ق) تطابق كل طلب.
    والترتيب: مطابقة تامة ثم بادئة ثم تضمين — والتضمين لا يُقبل إلا من
    ثلاثة أحرف فصاعدًا.

    الأرقام العربية-الهندية تعمل بلا معالجة: `str.isdigit` و`int` في
    بايثون يفهمان ٠-٩ كما يفهمان 0-9."""
    raw = query.strip()
    if raw.isdigit():
        number = int(raw)
        return [s for s in surahs if s["number"] == number]

    key = normalize_surah_name(raw)
    if not key:
        return []

    exact: list[dict] = []
    prefix: list[dict] = []
    contains: list[dict] = []
    for surah in surahs:
        name_key = normalize_surah_name(surah["arabic_name"])
        if name_key == key:
            exact.append(surah)
        elif name_key.startswith(key):
            prefix.append(surah)
        elif len(key) >= MIN_SKELETON_LENGTH and key in name_key:
            contains.append(surah)
    return exact + prefix + contains


class QuranService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _active_version(self) -> QuranTextVersion | None:
        result = await self.session.execute(
            select(QuranTextVersion).where(QuranTextVersion.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _version_block(version: QuranTextVersion) -> dict:
        """مصدر المخرَج وحالة مراجعته — يُرفق بكل استجابة تحمل نصًّا."""
        return {
            "version_code": version.version_code,
            "riwayah": version.riwayah,
            "script_type": version.script_type,
            "counting_system": version.counting_system,
            "review_status": version.status.value,
        }

    async def list_surahs(self, query: str | None = None) -> list[dict]:
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
        surahs = [
            {
                "number": s.number,
                "arabic_name": s.arabic_name,
                "revelation_type": s.revelation_type,
                "ayah_count": counts.get(s.number, 0),
            }
            for s in result.scalars()
        ]
        if query is None or not query.strip():
            return surahs
        return _filter_surahs(surahs, query)

    # ---- البحث النصي في الآيات ---------------------------------------------
    @staticmethod
    def _like_pattern(key: str) -> str:
        """نمط LIKE محتوٍ، بعد تحييد محارف البدل في طلب المستعمل."""
        for char in (LIKE_ESCAPE, "%", "_"):
            key = key.replace(char, LIKE_ESCAPE + char)
        return f"%{key}%"

    @staticmethod
    def _skeleton_expr():
        """مفتاح الهيكل محسوبًا في SQL من `plain_search_text` المخزَّن.

        **عمدًا لا يُخزَّن في عمود.** اشتقاقه وقت الطلب يجعل انحرافه عن
        العمود المخزَّن مستحيلًا بنيويًا، ويوفّر هجرة وإعادة توليد لـ6236
        صفًا. و`replace` دالة قياسية في SQLite وPostgres معًا.

        القياس على الإصدار النشط: عدّ كامل 22 مللي ثانية، وصفحة 20 نتيجة
        5 مللي — مقابل 250 مللي تستهلكها طبقة HTTP نفسها. فلا حاجة إلى
        فهرس. (وعند الانتقال إلى Postgres، إن لزم قياسًا لا تخمينًا،
        فالخيار الصحيح فهرس تعبير GIN مع pg_trgm على التعبير نفسه —
        لا btree، فهو لا يخدم LIKE على الوجهين أصلًا.)

        **يجب أن يبقى مطابقًا حرفًا بحرف لـ`normalize_search_skeleton`**
        مطبَّقًا على مخرَج `normalize_arabic_search`: ة→ه ثم حذف الألف
        ثم حذف الهمزة المفردة. يحرس ذلك اختبارٌ صريح."""
        expr = func.replace(Ayah.plain_search_text, "ة", "ه")
        expr = func.replace(expr, "ا", "")
        return func.replace(expr, "ء", "")

    async def _match_words(
        self, ayah_ids: list, exact_key: str, skeleton_key: str
    ) -> dict:
        """مواضع الكلمات المطابقة — من جدول الكلمات حصرًا.

        لا خريطة إزاحات بين النص المطبَّع والنص الموثق ولا يمكن أن توجد:
        التطبيع يحذف ويستبدل ويضغط الفراغات فليس حافظًا للطول. أما
        `char_start`/`char_end` فمواضع في نص الآية نفسه.

        أدنى حبيبة تمييز هي **الكلمة كاملة**: لا خريطة داخل الكلمة، فلا
        يجوز قصّ جزء منها. ولذلك إن وقع الطلب داخل كلمة (نحو طلب «الحمد»
        في موضع 6:45 حيث الكلمة بواو) يُميَّز الرمز كاملًا.

        وإن لم تكن السورة مرمَّزة بعد تعود القائمة فارغة — نتيجة بلا
        تمييز خير من تمييز مخترع."""
        if not ayah_ids:
            return {}

        from app.models.morphology import Token

        rows = (
            await self.session.execute(
                select(
                    Token.ayah_id,
                    Token.word_number,
                    Token.char_start,
                    Token.char_end,
                    Token.normalized_text,
                )
                .where(Token.ayah_id.in_(ayah_ids))
                .order_by(Token.ayah_id, Token.word_number)
            )
        ).all()

        tokens_by_ayah: dict = {}
        for ayah_id, number, start, end, normalized in rows:
            tokens_by_ayah.setdefault(ayah_id, []).append(
                (number, start, end, normalized)
            )

        exact_words = exact_key.split()
        skeleton_words = skeleton_key.split() if skeleton_key else []
        matches: dict = {}
        for ayah_id, tokens in tokens_by_ayah.items():
            plain = [token[3] for token in tokens]
            skeleton = [normalize_search_skeleton(token[3]) for token in tokens]

            # 1) نافذة كلمات متطابقة تمامًا، 2) فنافذة على مفتاح الهيكل
            hits = _word_window(plain, exact_words)
            if not hits and skeleton_words:
                hits = _word_window(skeleton, skeleton_words)
            # 3) فاحتياطًا: كل رمز يحوي كلمة من الطلب داخله، مميَّزًا كاملًا
            if not hits:
                parts = [w for w in exact_words if len(w) >= MIN_FALLBACK_WORD]
                hits = {
                    index
                    for index, word in enumerate(plain)
                    if any(part in word for part in parts)
                }
            if not hits and skeleton_words:
                parts = [w for w in skeleton_words if len(w) >= MIN_SKELETON_LENGTH]
                hits = {
                    index
                    for index, word in enumerate(skeleton)
                    if any(part in word for part in parts)
                }

            matches[ayah_id] = [
                {
                    "word_number": tokens[index][0],
                    "char_start": tokens[index][1],
                    "char_end": tokens[index][2],
                }
                for index in sorted(hits)
            ]
        return matches

    async def search_ayahs(
        self,
        query: str,
        surah: int | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> dict | None:
        """بحث نصي في آيات الإصدار النشط، على طبقتين معلنتين للمستعمل.

        **الخط الأحمر:** المطابقة تقع على `plain_search_text` (مطبَّع،
        للبحث فقط) بينما المعروض `uthmani_text` كما ورد في سجل الآية
        حرفيًا — لا يُبنى نص العرض من المطبَّع ولا يُعاد تركيبه من كلماته.
        ولا يُعاد أي عمود مطبَّع في الاستجابة أصلًا.

        الطبقتان: `exact` مطابقة صارمة على صورة الرسم كما طُبِّعت، ثم
        `approximate` على مفتاح الهيكل (فروق الرسم العثماني). تُرتَّب
        الصارمة أولًا، ويحمل كل عنصر وسمه فيعلم المستعمل درجة يقين ما
        يرى — وهي عين سياسة المنصة في إظهار الحالة لا إخفائها."""
        version = await self._active_version()
        if version is None:
            return None

        exact_key = normalize_arabic_search(query)
        skeleton_key = normalize_search_skeleton(query)
        use_skeleton = len(skeleton_key) >= MIN_SKELETON_LENGTH

        exact_match = Ayah.plain_search_text.like(
            self._like_pattern(exact_key), escape=LIKE_ESCAPE
        )
        conditions = [exact_match]
        if use_skeleton:
            conditions.append(
                self._skeleton_expr().like(
                    self._like_pattern(skeleton_key), escape=LIKE_ESCAPE
                )
            )

        filters = [Ayah.text_version_id == version.id, or_(*conditions)]
        if surah is not None:
            filters.append(Ayah.surah_number == surah)

        total = await self.session.scalar(
            select(func.count(Ayah.id)).where(*filters)
        )

        # الصارمة أولًا ثم التقريبية، وداخل كل طبقة ترتيب المصحف.
        # استعلام واحد لا استعلامان: الترقيم عبر طبقتين منفصلتين يفسد
        # عند تخطي الصفحات، والعدّ يصير مركّبًا لا صادقًا.
        match_rank = case((exact_match, 0), else_=1)
        rows = (
            await self.session.execute(
                select(
                    Ayah.id,
                    Ayah.surah_number,
                    Ayah.ayah_number,
                    Ayah.uthmani_text,
                    Surah.arabic_name,
                    match_rank,
                )
                .join(Surah, Surah.number == Ayah.surah_number)
                .where(*filters)
                .order_by(match_rank, Ayah.surah_number, Ayah.ayah_number)
                .offset(offset)
                .limit(limit)
            )
        ).all()

        words_by_ayah = await self._match_words(
            [row[0] for row in rows],
            exact_key,
            skeleton_key if use_skeleton else "",
        )

        return {
            "query": query,
            # الصورة التي بُحث بها فعلًا، معلنة للمستعمل لا مخفية عنه
            "normalized_query": exact_key,
            "skeleton_query": skeleton_key if use_skeleton else None,
            "surah_filter": surah,
            "version": self._version_block(version),
            "results": [
                {
                    "surah_number": surah_number,
                    "surah_name": surah_name,
                    "ayah_number": ayah_number,
                    # نص السجل كما ورد — لا يُقطَّع ولا يُبرَز في الخادم
                    "uthmani_text": text,
                    "match_kind": "exact" if rank == 0 else "approximate",
                    "match_words": words_by_ayah.get(ayah_id, []),
                }
                for (
                    ayah_id,
                    surah_number,
                    ayah_number,
                    text,
                    surah_name,
                    rank,
                ) in rows
            ],
            "pagination": {"total": total or 0, "offset": offset, "limit": limit},
            "scope_note": (
                "البحث يجري في نص آيات الإصدار النشط. وبسملات فواتح السور "
                "مسجَّلة بيانًا للسورة خارج عدّ آياتها، فلا تظهر هنا إلا حيث "
                "كانت آية معدودة في العدّ المعلن."
            ),
        }

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
            "version": self._version_block(version),
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
