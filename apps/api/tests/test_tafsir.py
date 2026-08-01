"""حرّاس حزمة التفسير (§٢٠ — قرار المالك 2026-08-01).

الدعوى القابلة للإثبات: متنُ مفسِّرٍ قديم خالص، وجهاز المحقِّق مستبعَد،
والإسناد كامل، **وربطُ كل مقطعٍ بآيته مأخوذ من أرقام آيات المطبوع
ومثبَت بمطابقة اقتباسه بنص المصحف المبصوم — وما لم يثبت موسوم**.
سقوط أي اختبار = الدعوى لم تعد صادقة فيتوقف النشر (§١٨).
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
BUNDLE = REPO / "apps" / "api" / "data" / "tafsir_bundle.json.gz"
SURAHS = REPO / "apps" / "web" / "public" / "data" / "v1" / "surahs.json"


@pytest.fixture(scope="module")
def bundle() -> dict:
    if not BUNDLE.exists():
        pytest.skip("حزمة التفسير غير مولَّدة")
    with gzip.open(BUNDLE, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def test_every_work_carries_full_attribution(bundle):
    for key, meta in bundle["meta"]["works"].items():
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
        assert "notes" in meta, f"{key}: حقل التحفظات غائب"
        assert re.fullmatch(r"[0-9a-f]{64}", meta["sha256"]), key
        # مؤلفون متقدمون قرونًا — مناط كون المتن ملكًا عامًّا (§٢٠).
        # أحدثُهم السيوطي (ت٩١١هـ) شريكُ المحلّي في الجلالين.
        assert int(meta["author_died_hijri"]) <= 911, key


def test_passages_reference_real_ayahs(bundle):
    """مدى كل مقطع داخل حدود سورته الفعلية — لا آية مخترعة."""
    counts = {
        s["n"]: s["count"]
        for s in json.loads(SURAHS.read_text(encoding="utf-8"))["surahs"]
    }
    for work, passages in bundle["passages"].items():
        assert passages, work
        for passage in passages:
            surah = passage["surah"]
            assert 1 <= surah <= 114, f"{work}: سورة {surah}"
            assert (
                1
                <= passage["ayah_start"]
                <= passage["ayah_end"]
                <= counts[surah]
            ), f"{work}: {surah}:{passage['ayah_start']}-{passage['ayah_end']}"


def test_surah_coverage_is_complete(bundle):
    """المصحف كلُّه مغطًّى — والنقصُ الفرديّ محدودٌ ومعلوم.

    اتحادُ الكتب يجب أن يبلغ ١١٤ سورة: فلا آيةٌ بلا تفسيرٍ في المنصة.
    وكتابٌ بعينه قد تنقصه سورةٌ أو سورتان لأن رأسها ساقطٌ من نسخة
    المصدر لا لأن المؤلف لم يفسّرها — فيُحدّ النقصُ ولا يُمنع، وانهيارُ
    التغطية (كتابٌ يهوي دون ٩٥٪) يوقف النشر."""
    union: set[int] = set()
    for work, passages in bundle["passages"].items():
        covered = {p["surah"] for p in passages}
        union |= covered
        assert len(covered) >= 108, (
            f"{work}: تغطيته {len(covered)} سورة — انهيار تقطيع لا نقص مصدر"
        )
    missing = [n for n in range(1, 115) if n not in union]
    assert not missing, f"سور لا تفسير لها في المنصة كلها: {missing}"


def test_anchoring_rate_is_high_and_honest(bundle):
    """اغلب المقاطع مثبتة المطابقة، والعدد المعلن صادق — انهيار الحارس
    (نسبة متدنية فجأة) يوقف النشر قبل ان يصل قارئًا."""
    for work, passages in bundle["passages"].items():
        anchored = sum(1 for p in passages if p["anchored"])
        assert anchored == bundle["meta"]["works"][work]["anchored"], work
        assert anchored / len(passages) >= 0.85, (
            f"{work}: المثبت {anchored}/{len(passages)} دون العتبة"
        )


def test_no_source_markup_leaks(bundle):
    markup = re.compile(r"~~|ms\d{3,}|PageV\d+P\d+|###|\{|\}|\(\d+\)|\s\?\s")
    for work, passages in bundle["passages"].items():
        for passage in passages:
            found = markup.search(passage["text"])
            assert not found, (
                f"{work} {passage['surah']}:{passage['ayah_start']}: "
                f"بقية ترميز {found.group(0)!r}"
            )
            # العتبة عشرون حرفًا لا أربعون: الجلالين موجزٌ بطبعه —
            # «(الم) الله أعلم بمراده بذلك» تفسيرٌ تامٌّ عنده لا نصٌّ مبتور
            assert len(passage["text"]) >= 20, f"{work}: مقطع تافه"


def test_review_status_is_honest(bundle):
    assert bundle["meta"]["review_status"] == "imported"
    assert "قرار المالك" in bundle["meta"]["decision"]
