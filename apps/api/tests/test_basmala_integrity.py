"""فصل البسملة: إثبات بايتيّ لا دعوى.

**طلبته مراجعة خارجية في 2026-07-26**، ومحقّة: قول السكربت «فصلها نقلًا
حرفيًا» ليس إثباتًا. المخاطر المذكورة حقيقية — قطع في وسط نقطة Unicode،
أو إسقاط علامة عثمانية، أو انزياح في الترقيم، أو خلط تمثيل العرض بالنص.

**العقد المُثبَت هنا، وهو أدقّ مما طُلب:**

    السطر الأصلي == البسملة + فاصل + نص الآية

والفاصل مسافة واحدة `U+0020` في ١١٢ سورة، وفارغ في الفاتحة وبراءة (لا
فصل فيهما). أي أن **لا حرف من النص يضيع**؛ الساقط هو المسافة الفاصلة
وحدها، وهي فاصل بين كلمتين لا جزء من أيٍّ منهما.

ويُقال بصراحة: المقارنة مع الملف الخام لا تجري في CI لأن `data/raw/`
خارج المستودع (ملفات المصدر لا تُوزَّع). فهنا مستويان:
  - ما يعمل دائمًا: تماسك الحزمة المشحونة نفسها.
  - وما يعمل عند توفّر الخام: المطابقة البايتية الكاملة — تُتخطّى إن غاب،
    ولا تُدَّعى نجاحًا وهي لم تُشغَّل.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from app.core.paths import data_file

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_TEXT = REPO_ROOT / "data" / "raw" / "quran-uthmani.txt"

# الفاتحة: البسملة فيها آية مستقلة. براءة: لا بسملة فيها.
NO_SEPARATION = {1, 9}


@pytest.fixture(scope="module")
def bundle() -> dict:
    with gzip.open(data_file("quran_bundle.json.gz"), "rt", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def raw_lines() -> dict[tuple[int, int], str]:
    if not RAW_TEXT.exists():
        pytest.skip(
            "ملف المصدر الخام غير متاح (data/raw/ خارج المستودع). "
            "المطابقة البايتية الكاملة تُشغَّل عند توفّره فقط."
        )
    lines: dict[tuple[int, int], str] = {}
    for line in RAW_TEXT.read_text(encoding="utf-8").splitlines():
        # `rstrip("\r\n")` لا `strip()`: الاختبار يدّعي مطابقة **بايتية**،
        # و`strip()` يحذف كل ما `isspace()` — ومنه المسافة الفاصلة نفسها
        # في آخر السطر والمسافة غير الفاصلة U+00A0. فلو ضاعت مسافةٌ من
        # المصدر لضاعت من الطرفين معًا فمرّ الاختبار على خطأ. والحذف هنا
        # يقتصر على فاصل الأسطر الذي يضيفه الملف لا النص.
        line = line.rstrip("\r\n")
        if not line.strip() or line.startswith("#"):
            continue
        surah, ayah, text = line.split("|", 2)
        lines[(int(surah), int(ayah))] = text
    return lines


# ---- ما يُثبَت دائمًا من الحزمة المشحونة -----------------------------------
def test_basmala_is_stored_for_every_surah_except_al_fatiha_and_bara_a(bundle):
    with_basmala = {s["number"] for s in bundle["surahs"] if s.get("basmala")}
    assert with_basmala == set(range(1, 115)) - NO_SEPARATION
    assert len(with_basmala) == 112


def test_no_first_ayah_still_begins_with_a_basmala_remnant(bundle):
    """لو فشل القطع في سورة لبقيت بسملتها داخل آيتها الأولى."""
    ayahs = {(s, a): t for s, a, t in bundle["ayahs"]}
    basmalas = {s.get("basmala") for s in bundle["surahs"] if s.get("basmala")}
    for surah in range(2, 115):
        first = ayahs[(surah, 1)]
        for basmala in basmalas:
            assert not first.startswith(basmala), f"سورة {surah}"


def test_stored_basmala_has_exactly_the_two_known_rasm_forms(bundle):
    """صورتان لا أكثر: خلافهما شذوذٌ يجب أن يُكتشف لا أن يمرّ.

    الأكثر في 110 سور، وصورة بشدّة على الباء في التين (95) والقدر (97)
    — وهو ما يرد في ملف تنزيل نفسه. لا نحكم بصوابه ولا بخطئه هنا؛ نُثبت
    أنه **لم يتغيّر**، وأن أي صورة ثالثة تكسر هذا الاختبار."""
    forms: dict[str, list[int]] = {}
    for surah in bundle["surahs"]:
        if surah.get("basmala"):
            forms.setdefault(surah["basmala"], []).append(surah["number"])
    assert len(forms) == 2, f"عدد صور البسملة {len(forms)} — يلزم فحص بشري"
    counts = sorted((len(v), sorted(v)) for v in forms.values())
    assert counts[0] == (2, [95, 97]), counts[0]
    assert counts[1][0] == 110


def test_every_ayah_is_non_empty_after_separation(bundle):
    ayahs = {(s, a): t for s, a, t in bundle["ayahs"]}
    assert len(ayahs) == 6236
    assert all(text.strip() for text in ayahs.values())


# ---- المطابقة البايتية الكاملة، عند توفّر المصدر الخام ---------------------
def test_separation_reconstructs_every_source_line_byte_for_byte(bundle, raw_lines):
    """العقد الأهم: لا حرف من النص يضيع في الفصل.

    يُفحص كل سورة على حدة — لا يكفي عدّ الأسطر كما نبّهت المراجعة."""
    ayahs = {(s, a): t for s, a, t in bundle["ayahs"]}
    basmalas = {s["number"]: s.get("basmala") for s in bundle["surahs"]}

    separators: set[str] = set()
    for surah in range(1, 115):
        original = raw_lines[(surah, 1)]
        ayah = ayahs[(surah, 1)]
        basmala = basmalas.get(surah)

        if surah in NO_SEPARATION:
            assert basmala is None, f"سورة {surah} لا يُفصل منها شيء"
            assert ayah == original, f"سورة {surah} تغيّرت بلا فصل"
            continue

        assert basmala is not None, f"سورة {surah} بلا بسملة محفوظة"
        # الجزآن مقتطعان من الأصل بمواضعهما، بلا تعديل ولا توحيد
        assert original.startswith(basmala), f"سورة {surah}: البسملة ليست بادئته"
        assert original.endswith(ayah), f"سورة {surah}: الآية ليست عجزه"
        gap = original[len(basmala) : len(original) - len(ayah)]
        separators.add(gap)

    # الفاصل الساقط مسافة واحدة لا غير — لا علامة وقف ولا حرفًا خفيًّا
    assert separators == {" "}, f"فواصل غير متوقَّعة: {separators!r}"


def test_no_unicode_normalisation_crept_into_the_bundle(bundle, raw_lines):
    """التطبيع الخفي (NFC/NFD) يغيّر النص بلا أن يبدو مختلفًا.

    كل آية غير مفصولة يجب أن تطابق سطرها الأصلي بايتيًا — وهو ما يكشف
    أي تطبيع مرّ على النص في خط البناء."""
    ayahs = {(s, a): t for s, a, t in bundle["ayahs"]}
    changed = [
        f"{s}:{a}"
        for (s, a), text in ayahs.items()
        if a != 1 and text != raw_lines[(s, a)]
    ]
    assert not changed, f"آيات تغيّرت عن المصدر: {changed[:10]}"


def test_the_uthmani_marks_survive(bundle, raw_lines):
    """علامات الوقف والألف الخنجرية والحروف الصغيرة تبقى كما وردت."""
    ayahs = {(s, a): t for s, a, t in bundle["ayahs"]}
    marks = "ٰۖۗۘۙۚۛۜۢۥۦ۪ۭۨ۫۬"
    for mark in marks:
        in_raw = sum(text.count(mark) for text in raw_lines.values())
        in_bundle = sum(text.count(mark) for text in ayahs.values())
        # البسملات انتقلت إلى جدول السور، فتُحسب معها
        in_basmala = sum(
            (s.get("basmala") or "").count(mark) for s in bundle["surahs"]
        )
        assert in_raw == in_bundle + in_basmala, (
            f"العلامة U+{ord(mark):04X}: المصدر {in_raw} ≠ "
            f"الحزمة {in_bundle} + البسملات {in_basmala}"
        )
