"""حرّاس حزمة المتون الكلاسيكية الثلاثة (قرار المالك 2026-07-31).

القرار في `docs/audits/OPENITI_MATN_DECISION.md` قام على دعوى قابلة
للإثبات: **المنشور متنٌ كلاسيكي خالص، وجهاز المحقِّق المعاصر مستبعَد
كلُّه، والإسناد كامل**. هذه الاختبارات هي الإثبات — سقوطُ أيٍّ منها
يعني أن الدعوى لم تعد صادقة فيتوقف النشر (§١٨).
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
BUNDLE = REPO / "apps" / "api" / "data" / "openiti_lexicon.json.gz"
ROOTS = REPO / "apps" / "web" / "public" / "data" / "v1" / "roots.json"


@pytest.fixture(scope="module")
def bundle() -> dict:
    if not BUNDLE.exists():
        pytest.skip("حزمة openiti غير مولَّدة")
    with gzip.open(BUNDLE, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def test_every_book_carries_full_attribution(bundle):
    """الإسناد الكامل شرطُ القرار لا زينتُه: كتابٌ بلا محقِّق أو بصمة لا يُنشر."""
    assert set(bundle["meta"]["books"]) == {
        "sihah_jawhari",
        "maqayis",
        "mufradat",
        "lisan",
    }
    for key, meta in bundle["meta"]["books"].items():
        for field in (
            "title",
            "author",
            "author_died_hijri",
            "editor",
            "publisher",
            "openiti_uri",
            "source_url",
            "sha256",
            "apparatus",
        ):
            assert meta.get(field), f"{key}: حقل الإسناد {field} فارغ"
        assert re.fullmatch(r"[0-9a-f]{64}", meta["sha256"]), key
        # مؤلفون متقدمون قرونًا — هذا مناطُ كون المتن ملكًا عامًّا
        # (أحدثُهم ابن منظور ت٧١١هـ — قبل سبعة قرون)
        assert int(meta["author_died_hijri"]) <= 711, key


def test_published_roots_are_ours(bundle):
    """كل جذرٍ منشور من فهرس جذور المصحف — فالبحث الآلي مقفول على مدونتنا."""
    roots = set(json.loads(ROOTS.read_text(encoding="utf-8"))["roots"])
    published = set(bundle["entries"])
    assert published <= roots, sorted(published - roots)[:5]
    assert bundle["meta"]["roots_covered"] == len(published)


def test_no_modern_apparatus_leaks_into_entries(bundle):
    """جهاز المحقِّق مستبعَد: لا مقدماتِ طبعاتٍ ولا أعلامَ تقديمٍ معاصرين
    ولا أرقامَ إحالات حواشٍ في أي مادة منشورة."""
    forbidden = (
        "فهد بن عبد العزيز",  # تقديم الطبعة — معاصر
        "مقدمة الطبعة",
        "مقدمة المحقق",
        "دار العلم للملايين",  # ذكر الناشر داخل متنٍ علامةُ تسرب جهاز
    )
    footnote_ref = re.compile(r"\(\d+\)")
    for root, per_book in bundle["entries"].items():
        for book, records in per_book.items():
            for record in records:
                text = record["text"]
                for needle in forbidden:
                    assert needle not in text, f"{root}/{book}: تسرب «{needle}»"
                if book == "sihah_jawhari":
                    assert not footnote_ref.search(text), f"{root}: إحالة حاشية"


def test_entries_are_substantial_and_carry_heads(bundle):
    """كل مادة تحمل رأسها كما في المصدر ونصًّا غير تافه — فالعرض صادق."""
    total = 0
    for root, per_book in bundle["entries"].items():
        for book, records in per_book.items():
            for record in records:
                assert record.get("head"), f"{root}/{book}: بلا رأس"
                assert len(record["text"]) >= 25, f"{root}/{book}: نص تافه"
                total += 1
    assert total >= 3000  # الكتب الثلاثة مجتمعة — انهيار التقطيع يُرى هنا


def test_no_openiti_markup_survives(bundle):
    """ترميز mARkdown لا يصل القارئ: لا وسومَ صفحات ولا سياجاتِ آيات خام."""
    markup = re.compile(r"PageV\d+P\d+|@QB@|@QE@|~~|\^ \(|ms\d{3,}|@\d+@")
    for root, per_book in bundle["entries"].items():
        for book, records in per_book.items():
            for record in records:
                found = markup.search(record["text"])
                assert not found, f"{root}/{book}: بقية ترميز {found.group(0)!r}"


def test_review_status_is_honest(bundle):
    """المتون مستوردة لا مراجَعة — الوسم لا يدّعي ما لم يقع (§٢٠)."""
    assert bundle["meta"]["review_status"] == "imported"
    assert "قرار المالك" in bundle["meta"]["decision"]
