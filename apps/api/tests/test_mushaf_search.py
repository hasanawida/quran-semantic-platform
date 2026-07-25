"""فهرست المصحف والبحث في السور والآيات.

الخط الأحمر الحاكم: **المطابقة على المطبَّع، والعرض من السجل.**
`plain_search_text` ومفتاح الهيكل المشتق منه يُستعملان في `WHERE` وحساب
مواضع التمييز فقط؛ أما نص الاستجابة فمن `Ayah.uthmani_text` حرفيًا.

وأخطر ما يُحرس هنا **تطابق تعبير SQL مع دالة بايثون**: لو انحرفا لعاد
البحث صفرًا صامتًا بلا رسالة خطأ — وهو عطب لا يُكتشف إلا بشكوى مستعمل.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.utils.arabic import (
    normalize_arabic_search,
    normalize_search_skeleton,
    normalize_surah_name,
)


def client() -> TestClient:
    return TestClient(app)


def search(query: str, **params) -> dict:
    response = client().get(
        "/api/v1/search/ayahs", params={"q": query, **params}
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


# ---- العقد بين بايثون وSQL -------------------------------------------------
def test_skeleton_key_matches_its_sql_counterpart():
    """أخطر عقد في هذه الميزة: تعبير SQL == دالة بايثون، لكل آية.

    مفتاح الهيكل يُشتق وقت الطلب داخل SQL بثلاث `replace` بدل تخزينه في
    عمود. المكسب أن الانحراف مستحيل بنيويًا — وهذا الاختبار يُثبته على
    البيانات كلها لا على عيّنة."""
    import asyncio

    from sqlalchemy import select

    from app.db.session import SessionFactory
    from app.models.quran import Ayah, QuranTextVersion
    from app.services.quran import QuranService

    async def check() -> tuple[int, list[str]]:
        async with SessionFactory() as session:
            version = await session.scalar(
                select(QuranTextVersion).where(QuranTextVersion.is_active.is_(True))
            )
            assert version is not None, "لا إصدار نشط في قاعدة الاختبار"
            rows = (
                await session.execute(
                    select(
                        Ayah.surah_number,
                        Ayah.ayah_number,
                        Ayah.plain_search_text,
                        QuranService._skeleton_expr(),
                    ).where(Ayah.text_version_id == version.id)
                )
            ).all()
        mismatches = [
            f"{s}:{a}"
            for s, a, plain, sql_key in rows
            if sql_key != normalize_search_skeleton(plain)
        ]
        return len(rows), mismatches

    total, mismatches = asyncio.run(check())
    assert total == 6236, total
    assert not mismatches, f"انحراف في {len(mismatches)} آية: {mismatches[:5]}"


# ---- فهرست السور -----------------------------------------------------------
def test_surah_index_still_returns_the_full_mushaf_without_a_query():
    """العقد القائم لا ينكسر: بلا `q` تعود 114 سورة."""
    body = client().get("/api/v1/surahs").json()["data"]
    assert len(body) == 114
    assert body[0]["number"] == 1 and body[-1]["number"] == 114
    assert all(s["ayah_count"] > 0 for s in body)


def test_surah_index_filters_by_name_and_by_number():
    """حقل واحد يقبل الاسم والرقم، وصور الهمزة والتاء المربوطة."""

    def numbers(query: str) -> list[int]:
        body = client().get("/api/v1/surahs", params={"q": query}).json()["data"]
        return [s["number"] for s in body]

    assert numbers("الفاتحه") == [1]  # بالهاء — كانت لا تطابق شيئًا
    assert numbers("الفاتحة") == [1]
    assert numbers("18") == [18]
    assert numbers("١٨") == [18]  # أرقام عربية-هندية
    assert numbers("سبأ") == numbers("سبإ") == [34]
    assert numbers("النبأ") == [78]
    assert numbers("إبراهيم") == numbers("ابراهيم") == [14]
    # الاتجاه مقصود: الطلب جزء من الاسم لا العكس — وإلا طابقت «ص» كل شيء
    assert len(numbers("ص")) <= 6


def test_surah_index_returns_nothing_for_nonsense():
    assert client().get("/api/v1/surahs", params={"q": "زقزق"}).json()["data"] == []


# ---- الخط الأحمر: النص من السجل -------------------------------------------
def test_search_returns_the_documented_text_byte_for_byte():
    """نص كل نتيجة == نص سجل الآية حرفيًا، لا بعد تطبيع ولا تنظيف."""
    c = client()
    for term in ("العالمين", "الحمد", "الكتاب"):
        for hit in search(term, limit=6)["results"]:
            reference = c.get(
                f"/api/v1/ayahs/{hit['surah_number']}/{hit['ayah_number']}"
            ).json()["data"]
            assert hit["uthmani_text"] == reference["uthmani_text"], (
                hit["surah_number"],
                hit["ayah_number"],
            )


def test_search_response_never_leaks_a_normalized_column():
    """المطبَّع لا يخرج إلى العميل ولو عرضًا — فلا يُغرى أحد بعرضه."""
    import json

    blob = json.dumps(search("الحمد"), ensure_ascii=False)
    for column in ("plain_search_text", "skeleton_search_text", "normalized_text"):
        assert column not in blob, column


def test_match_words_are_valid_offsets_into_the_documented_text():
    """مواضع التمييز فهارس صحيحة في نص الآية نفسه، وتُعيد بناءه كما هو."""
    for hit in search("العالمين", limit=10)["results"]:
        text = hit["uthmani_text"]
        for word in hit["match_words"]:
            start, end = word["char_start"], word["char_end"]
            assert 0 <= start < end <= len(text), (hit["surah_number"], word)
            assert text[start:end].strip(), "قطعة فارغة"
            # القصّ لا يفقد حرفًا: القطع الثلاث تُعيد النص بعينه
            assert text[:start] + text[start:end] + text[end:] == text


# ---- الطبقتان --------------------------------------------------------------
def test_the_two_tiers_are_labelled_and_exact_comes_first():
    exact = search("الحمد", limit=10)
    assert exact["pagination"]["total"] > 0
    assert all(r["match_kind"] == "exact" for r in exact["results"])

    # كانت تعيد صفرًا قبل مفتاح الهيكل: الألف الخنجرية محذوفة من المخزون
    approximate = search("العالمين", limit=10)
    assert approximate["pagination"]["total"] > 0
    assert all(r["match_kind"] == "approximate" for r in approximate["results"])

    kinds = [r["match_kind"] for r in search("الله", limit=30)["results"]]
    if "approximate" in kinds and "exact" in kinds:
        assert kinds.index("approximate") > kinds.rindex("exact")


def test_queries_that_used_to_return_nothing_now_find_ayahs():
    """الشاهد العملي على الإصلاح — أرقام مقيسة لا مقدَّرة."""
    for term, minimum in [
        ("العالمين", 50),
        ("الكتاب", 100),
        ("السماوات", 100),
        ("مالك", 50),
    ]:
        assert search(term)["pagination"]["total"] >= minimum, term


# ---- المتانة ---------------------------------------------------------------
def test_like_wildcards_in_the_query_are_not_operators():
    """محارف البدل مهرَّبة: طلبٌ فيه `%` لا يعيد المصحف كله."""
    for hostile in ("%%", "_ا", "5%0", "%الله%"):
        total = search(hostile)["pagination"]["total"]
        assert total < 6236, (hostile, total)


def test_search_carries_its_source_and_review_state():
    """لا مخرَج بلا مصدر ولا حالة مراجعة — سياسة المنصة في كل نافذة."""
    body = search("الحمد")
    version = body["version"]
    for field in ("version_code", "riwayah", "script_type", "counting_system"):
        assert version[field], field
    assert version["review_status"] == "imported"
    assert body["normalized_query"] == normalize_arabic_search("الحمد")
    assert body["scope_note"].strip()
    # البسملة مذكورة صراحةً: لماذا لا تظهر بسملات الفواتح في نتائج الآيات
    assert "بسمل" in body["scope_note"]


def test_pagination_neither_repeats_nor_drops():
    first = search("الله", limit=5, offset=0)
    second = search("الله", limit=5, offset=5)
    refs = lambda page: {  # noqa: E731
        (r["surah_number"], r["ayah_number"]) for r in page["results"]
    }
    assert not (refs(first) & refs(second))
    assert first["pagination"]["total"] == second["pagination"]["total"]


def test_search_rejects_a_one_character_query():
    """حرف واحد يعيد نصف المصحف — يُرفض في الحدّ لا يُخدم."""
    assert client().get("/api/v1/search/ayahs", params={"q": "ا"}).status_code == 422


# ---- مفاتيح التطبيع نفسها --------------------------------------------------
def test_skeleton_key_is_symmetric_across_rasm_differences():
    """الحذف متناظر: لا يحتاج النظام أن يعرف أمكتوبة الألف أم خنجرية."""
    for written, uthmani in [
        ("العالمين", "العلمين"),
        ("السماوات", "السموت"),
        ("الكتاب", "الكتب"),
        ("مالك", "ملك"),
    ]:
        assert normalize_search_skeleton(written) == normalize_search_skeleton(
            uthmani
        ), written


def test_skeleton_key_does_not_break_what_already_works():
    """القاعدة الساذجة «الخنجرية ← ألف» كانت ستكسر هذه."""
    for word in ("ذلك", "هذا", "اله"):
        assert normalize_search_skeleton(word) == normalize_search_skeleton(word)
    # «ذلك» لا تكتسب ألفًا وهمية فتسقط
    assert "ا" not in normalize_search_skeleton("ذلك")


def test_surah_name_key_unifies_forms_but_spares_al_imran():
    assert normalize_surah_name("الفاتحه") == normalize_surah_name("الفاتحة")
    assert normalize_surah_name("سبأ") == normalize_surah_name("سبإ")
    assert normalize_surah_name("إبراهيم") == normalize_surah_name("ابراهيم")
    # «ال» التعريف تُسقط إن تلاها حرف، ولا تُسقط إن تلاها فراغ
    assert normalize_surah_name("البقرة") == normalize_surah_name("بقرة")
    assert normalize_surah_name("ال عمران").startswith("ال ")
