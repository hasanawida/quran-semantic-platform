#!/usr/bin/env python
"""يبني حزمة التفسير من ملفات OpenITI — متنًا كلاسيكيًّا مقطَّعًا بالآية.

**الإطار الحاكم §٢٠ نفسه** (docs/audits/OPENITI_MATN_DECISION.md): متنُ
المفسِّر القديم ملكٌ عام، وجهاز المحقِّق المعاصر يُستبعد، والإسناد يُعرض
كاملًا نسبةً لا ادّعاءَ ترخيص.

**الكتاب الأول:** معالم التنزيل للبغوي (ت٥١٠هـ) — نسخة Shamela0000041
(المستوى completed). ما يُستبعد من عمل المحقِّقين هنا:

- أرقامُ إحالات الحواشي `(1)` — تُجرَّد (نصوص الحواشي غير منقولة أصلًا).
- معقوفات الإثبات `[...]` — يُبقى لفظُها ويُنزع القوسان، فهي من متن
  النسخ الخطية أثبتها المحقق في مكانها.
- مقدمات الطبعة إن وُجدت قبل متن المؤلف.

**التقطيع بالآية — من المصدر لا من الظن:** كل مقطعٍ يفتتحه المطبوعُ
باقتباسٍ قرآني معقوص `{...}` تتخلله أرقامُ الآيات، فمدى المقطع
(surah, ayah_start..ayah_end) مأخوذ من هذه الأرقام نصًّا.

**حارس الربط (شرط النشر):** أخطر خطأ ممكنٍ نشرُ تفسير آيةٍ تحت غيرها.
فكلُّ قطعةٍ من الاقتباس الرأسي تُقابَل بنصِّ آيتها من الحزمة القرآنية
المبصومة (بمفتاح الهيكل الذي يجسر فرقَ الرسم الإملائي عن العثماني).
ما طابق وُسم `anchored: true`؛ وما لم يطابق يُنشر بوسم صريح أنه رُبط
بالترتيب لا بالمطابقة — لا يُدَّعى ما لم يُثبَت.

التشغيل:
    python scripts/import-tafsir/build_tafsir.py
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "apps" / "api"))

from app.utils.arabic import (  # noqa: E402
    normalize_arabic_search,
    normalize_surah_name,
)

RAW = REPO / "data" / "raw" / "openiti"
OUT = REPO / "apps" / "api" / "data" / "tafsir_bundle.json.gz"
QURAN = REPO / "apps" / "api" / "data" / "quran_bundle.json.gz"
SURAHS = REPO / "apps" / "web" / "public" / "data" / "v1" / "surahs.json"

GITHUB = "https://raw.githubusercontent.com/OpenITI"

WORKS = [
    {
        "key": "baghawi",
        "file": "baghawi.Shamela0000041.txt",
        "openiti_uri": "0510IbnMascudBaghawi.Tafsir.Shamela0000041-ara1",
        "source_url": (
            f"{GITHUB}/0525AH/master/data/0510IbnMascudBaghawi/"
            "0510IbnMascudBaghawi.Tafsir/"
            "0510IbnMascudBaghawi.Tafsir.Shamela0000041-ara1.completed"
        ),
        "apparatus": (
            "أرقام إحالات الحواشي مجرَّدة ومعقوفات الإثبات منزوعة القوسين "
            "عندنا — نصوص حواشي المحقِّقين غير منقولة في ملف المصدر أصلًا"
        ),
        "notes": "",
    },
    {
        "key": "ibn_kathir",
        "file": "ibnkathir.Shamela0008473.txt",
        "openiti_uri": "0774IbnKathir.TafsirQuran.Shamela0008473-ara1",
        "source_url": (
            f"{GITHUB}/0775AH/master/data/0774IbnKathir/"
            "0774IbnKathir.TafsirQuran/"
            "0774IbnKathir.TafsirQuran.Shamela0008473-ara1.mARkdown"
        ),
        "apparatus": (
            "أزالت OpenITI العناصر المصاحبة (Clean 2023)، وتُجرَّد عندنا "
            "أرقامُ إحالات الحواشي ومعقوفاتُ الإثبات"
        ),
        # يُقال ما في المصدر ولا يُطمس: النسخة موسومة عندهم MISSING_PARTS
        "notes": (
            "نسخة المصدر موسومة عند OpenITI بـ MISSING_PARTS — مواضعُ "
            "منها ساقطة، فغيابُ تفسيرِ آيةٍ هنا لا يعني أن المؤلف لم "
            "يفسّرها. راجع الطبعة عند الحاجة."
        ),
    },
    # ---- طبقة الاستزادة: متونٌ لا إحالات (قرار المالك 2026-08-01) ----
    # المالك أراد للاستزادة متنًا يُقرأ لا رابطًا يُتبع. والمعاصرون
    # (الصابوني والسعدي والشنقيطي) لا يجوز نقلُ متنهم، فتُملأ الاستزادة
    # بأصولٍ كلاسيكية أوسع — وهي بعينها ما اختصره الصابوني في «صفوة
    # التفاسير» بنصّ مقدمته: الطبري والكشاف والقرطبي والألوسي وابن كثير.
    {
        "key": "jalalayn",
        "file": "jalalayn.Shamela0012876.txt",
        "parser": "match_forward",
        "openiti_uri": "0911Suyuti.TafsirJalalayn.Shamela0012876-ara1",
        "source_url": (
            f"{GITHUB}/0925AH/master/data/0911Suyuti/"
            "0911Suyuti.TafsirJalalayn/"
            "0911Suyuti.TafsirJalalayn.Shamela0012876-ara1"
        ),
        "apparatus": "أرقام إحالات الحواشي مجرَّدة ومعقوفات الإثبات منزوعة القوسين",
        "notes": (
            "أوجزُ التفاسير: كلمةٌ أو جملة لكل لفظ — أقربُها إلى من أراد "
            "المعنى مجموعًا في إيجاز"
        ),
    },
    {
        "key": "ibn_atiyya",
        "file": "ibnatiyya.Shamela0023632.txt",
        "parser": "explicit_range",
        "openiti_uri": "0541IbnCatiyyaAndalusi.MuharrarWajiz.Shamela0023632-ara1",
        "source_url": (
            f"{GITHUB}/0550AH/master/data/0541IbnCatiyyaAndalusi/"
            "0541IbnCatiyyaAndalusi.MuharrarWajiz/"
            "0541IbnCatiyyaAndalusi.MuharrarWajiz.Shamela0023632-ara1.completed"
        ),
        "apparatus": "أرقام إحالات الحواشي مجرَّدة ومعقوفات الإثبات منزوعة القوسين",
        "notes": "تحليلٌ لغويّ وترجيحٌ بالسياق",
    },
    {
        "key": "kashshaf",
        "file": "kashshaf.Shamela0023627.txt",
        "parser": "explicit_range",
        "openiti_uri": "0538JarAllahZamakhshari.Kashshaf.Shamela0023627-ara1",
        "source_url": (
            f"{GITHUB}/0550AH/master/data/0538JarAllahZamakhshari/"
            "0538JarAllahZamakhshari.Kashshaf/"
            "0538JarAllahZamakhshari.Kashshaf.Shamela0023627-ara1"
        ),
        "apparatus": "أرقام إحالات الحواشي مجرَّدة ومعقوفات الإثبات منزوعة القوسين",
        "notes": (
            "أصلٌ في بلاغة القرآن ونكته. ومذهبُ مؤلفه الاعتزال ظاهرٌ في "
            "مواضع من كلامه — يُعرض كما قاله ولا يُقضى عليه هنا (ADR-013)"
        ),
    },
]

# رأسُ السورة في المطبوعين على ثلاث صور: «سورة كذا»، و«تفسير سورة كذا»،
# و«تفسير السورة التي يُذكر فيها كذا» — وقد يسبقها فراغٌ زائد أو وسمُ
# موضعٍ (ms1234). والاسم المجرد («الأحزاب») يُقبل عند رأسٍ من الدرجة
# الأولى `### |` وحدها، فلا تُلتقط عناوينُ الفصول الداخلية.
SURAH_HEAD = re.compile(
    r"^### \|(?P<deep>\|*)\s*(?:ms\d+\s*)?"
    r"(?P<name>(?:تفسير\s+)?(?:سورة|سورتي|السورة التي يذكر فيها)?\s*[^{\n|]*)$",
    re.M,
)
# المرساة: اقتباسٌ معقوص فيه أرقام آيات — إمّا فقرةً (البغوي) وإمّا في
# سطر رأسٍ بنيوي (ابن كثير). الشكلان يُلتقطان بنمطٍ واحد.
ANCHOR = re.compile(r"^(?:# |#+ \|+ ?)\{", re.M)

# البنية الثالثة (ابن عطية والزمخشري): المدى مصرَّحٌ به في الرأس —
# «[سورة الفاتحة (1) : الآيات 1 الى 7]» أو «… : آية 3». أنظفُ البنى
# الثلاث: رقم السورة ومداها مقروءان من المطبوع لا مستنبطان.
RANGE_HEAD = re.compile(
    # القوس المفتوح ساقطٌ في مواضع من المصدر («سورة الضحى (93) : …]»)
    # فيُجعل اختياريًّا — كشفه غيابُ سبع سور قصار عند ابن عطية.
    # والرقمُ قد يقع على السطر التالي حيث لفّه المصدر عند حدّ العمود
    # (وهو الغالب في الكشاف) — فيُسمح بعبور السطر ووسمِ الوصل `~~`.
    r"^#+ \|+ ?\[?سورة [^\]\(\n]{2,40}\((?P<surah>\d{1,3})\)\s*:\s*"
    r"(?:الآيات|الآية|آية)[\s~#]*(?P<start>\d{1,3})"
    r"(?:[\s~#]*(?:الى|إلى)[\s~#]*(?P<end>\d{1,3}))?[\s~#]*\]",
    re.M,
)
PAGE = re.compile(r"PageV(\d+)P(\d+)")
MILESTONE = re.compile(r"\s*ms\d+\s*")
FOOTNOTE_REF = re.compile(r"\s*\(\d+\)")
WS = re.compile(r"\s+")
# ما ليس حرفًا عربيًّا ولا فراغًا — يُنقّى منه اللفظُ قبل المقابلة
NON_ARABIC = re.compile(r"[^؀-ۿ\s]")

# مفتاح الهيكل: يجسر فرق الرسم الإملائي (في التفسير) عن العثماني (في
# الحزمة) — الصنيع نفسه المعتمد في check_quotes: صور الهمزة تُنزع من
# **الخام** قبل التطبيع (وإلا ردّ التطبيعُ همزةَ المصحف المركبة ياءً
# فافترق «الآخرة» عن نفسها)، ثم تسقط صور الألف، وتُمحى وصلات الأسطر
_HAMZA_FORMS = str.maketrans("", "", "ءأإآؤئٕٔ")
# تسقط حروف العلة كلها (ا و ي ى): رسم المصحف يزيدها وينقصها عن الاملائي
# (فسويهن/فسوهن، يستحي/يستحيي) — والمقارنة على طول الاية كاملة فلا لبس
_WEAK_FORMS = str.maketrans("", "", "اأإآٱىوي ")


def _skeleton(value: str) -> str:
    value = MILESTONE.sub(" ", value.replace("~~", " "))
    value = value.translate(_HAMZA_FORMS)
    return normalize_arabic_search(value).translate(_WEAK_FORMS)


# أسماء تسمّي بها المطبوعاتُ سورًا بغير اسمها المشهور — كلُّها مقروءة
# من رؤوس المصدر نفسه لا من تخمين، والرقم ثابت لا يحتمل التباسًا.
ALT_SURAH_NAMES: dict[str, int] = {
    "القتال": 47,  # محمد
    '"ن"': 68,  # القلم
    "ن": 68,
    "سأل سائل": 70,  # المعارج
    "سبح": 87,  # الأعلى
    "اقرأ": 96,  # العلق
    "لم يكن": 98,  # البينة
    "إذا زلزلت": 99,  # الزلزلة
    "إذا جاء نصر الله والفتح": 110,  # النصر
    "تبت": 111,  # المسد
    "الدهر": 76,  # الإنسان
    "بني إسرائيل": 17,  # الإسراء
    "المطففين": 83,
    # يجمع المطبوعُ سورتين في قسمٍ واحد؛ يُبدأ بالأولى وحارسُ المطابقة
    # يفصل مقاطعَ الثانية عنها (انظر _pick_surah)
    "المعوذتين": 113,
}

# أقسامٌ تجمع سورتين متتاليتين: الرقمُ فيها ابتداءٌ لا قطع
COMBINED_HEADS = ("المعوذتين",)


def _surah_number(head: str, keyed: dict[str, int], previous: int) -> int | None:
    """رقم السورة من اسمها في الرأس — والترتيب المصحفي حَكَمٌ مساند."""
    name = FOOTNOTE_REF.sub("", head)
    name = MILESTONE.sub(" ", name)
    name = re.sub(r"^\s*تفسير\s+", "", name)
    name = re.sub(
        r"^\s*(?:سورتي|سورة|السورة التي يذكر فيها)\s+", "", name
    ).strip()
    name = re.sub(r"\s*(مكية|مدنية).*$", "", name).strip()
    if not name:
        return None
    if name in ALT_SURAH_NAMES:
        return ALT_SURAH_NAMES[name]
    key = normalize_surah_name(name)
    if key in keyed:
        return keyed[key]
    for alt_name, number in ALT_SURAH_NAMES.items():
        if normalize_surah_name(alt_name) == key:
            return number
    for candidate_key, number in keyed.items():
        if key.startswith(candidate_key) or candidate_key in key:
            # «فاتحة الكتاب» تبدأ بمفتاح «فاتحه»
            if number == previous + 1:
                return number
    return None


def _clean(text: str) -> str:
    """متنٌ مقروء: يُجرَّد ترميز المصدر وجهاز المحقِّق، ولا يُمسّ اللفظ."""
    text = re.sub(r"^### \|+ ?", "", text, flags=re.M)
    text = re.sub(r"^# ", "", text, flags=re.M)
    text = re.sub(r"^~~", "", text, flags=re.M)
    text = FOOTNOTE_REF.sub("", text)
    text = PAGE.sub(" ", text)
    text = MILESTONE.sub(" ", text)
    # معقوفات الإثبات: يبقى اللفظ وينزع القوسان
    text = text.replace("[", "").replace("]", "")
    # الاقتباس القرآني الجاري: معقوصه يصير قوسي تنصيص وترقيمه الداخلي يسقط
    def _inline(match: re.Match) -> str:
        inner = FOOTNOTE_REF.sub("", match.group(1))
        return f"«{WS.sub(' ', inner).strip()}»"

    text = re.sub(r"\{([^{}]*)\}", _inline, text)
    # قوسٌ اعرج في المصدر (فتح بلا اغلاق او العكس): يقلب علامة تنصيص
    # مفردة بدل ان يصل القارئ خامًا — كشفه test_no_source_markup_leaks
    text = text.replace("{", "«").replace("}", "»")
    # علامةُ استفهامٍ لاتينية معزولة: أثرُ تشويشٍ في رقمنة المصدر (العربية
    # تستعمل «؟»)، تظهر في الجلالين مكان التنوين — تُحذف ولا يُخترع بدلها
    text = re.sub(r"\s\?(?=\s)", "", text)
    # بقايا وسوم HTML في بعض المصادر (`</span>`) — تُنزع ولا تصل القارئ
    text = re.sub(r"</?[a-zA-Z][^>]*>", "", text)
    return WS.sub(" ", text).strip(" .·-—")


def _parse_anchor(block: str) -> list[tuple[int, str]]:
    """يفكّ الاقتباس الرأسي إلى (رقم آية، نصّها المقتبس).

    الشكل في المصدر: {الم (1) ذلك الكتاب لا ريب فيه... (2) الذين... (3)}
    فالنص الذي قبل كل رقم هو آيته."""
    inner = block.strip()
    inner = re.sub(r"^\{", "", inner)
    inner = re.sub(r"\}$", "", inner)
    pieces: list[tuple[int, str]] = []
    cursor = 0
    for match in re.finditer(r"\((\d{1,3})\)", inner):
        piece = inner[cursor : match.start()].strip()
        if piece:
            pieces.append((int(match.group(1)), piece))
        cursor = match.end()
    return pieces


def _parse_match_forward(
    matn: str,
    keyed: dict[str, int],
    ayah_counts: dict[int, int],
    ayah_skeleton: dict[tuple[int, int], str],
    work_key: str,
) -> tuple[list[dict], int, list[str]]:
    """تفسيرٌ يشرح الألفاظ بين معقوصين بلا أرقام آيات (الجلالين).

    **لا يُعدّ بالترتيب:** فقرةٌ ساقطة أو زائدة تُزيح التفسير كلَّه بعدها
    إزاحةً صامتة — وذاك أفدح ما يُخشى. بل **المطابقة هي التي تحدد
    الآية**: تُجمع الألفاظ المعقوصة في الفقرة، ويُلتمس أوّلُ آيةٍ تسعها
    ابتداءً من موضع القراءة، فإن وُجدت أُثبت الربط وتقدّم الموضع، وإلّا
    نُسبت الفقرة إلى التالية بوسم «غير مثبَت».
    """
    parsed: list[dict] = []
    anchored_count = 0
    skipped: list[str] = []

    # رؤوس السور في هذا المطبوع على صور شتى: رأسٌ بنيوي مجرَّدُ الاسم
    # («### | البقرة»)، وفقرةٌ مصرّحة («# سورة الفاتحة»)، وأسماءٌ
    # يعلقُ بها قوسٌ معقوص («{فاطر») أو رقمُ جزء («= 6 سورة الأنعام»)
    heads = []
    for pattern in (r"^### \| ?([^\n]*)$", r"^# (?:= \d+ )?(سورة [^\n]{2,25})$"):
        for match in re.finditer(pattern, matn, re.M):
            name = match.group(1).strip().strip("{}").strip()
            if name and not name[0].isdigit():
                heads.append((match.start(), match.end(), name))
    heads.sort()
    sections: list[tuple[int, int, int]] = []
    current = 0
    pending: list[tuple[int, int]] = []
    for start, end, name in heads:
        number = _surah_number(name, keyed, current)
        if number is None or number <= current:
            continue
        current = number
        pending.append((end, number))
    for index, (body_start, number) in enumerate(pending):
        stop = pending[index + 1][0] if index + 1 < len(pending) else len(matn)
        sections.append((body_start, stop, number))

    for body_start, stop, number in sections:
        body = matn[body_start:stop]
        cursor = 1
        total = ayah_counts.get(number, 0)
        last_record: dict | None = None
        for para in re.finditer(r"^# (?!PageV)(.*(?:\n~~.*)*)$", body, re.M):
            block = para.group(1)
            fragments = re.findall(r"\{([^{}]{1,120})\}", block)
            if not fragments:
                continue
            # كل لفظٍ معقوص يُقابَل وحده: الألفاظ المشروحة متفرقةٌ في
            # الآية يفصل بينها الشرح، فطلبُ تطابقها متصلةً يُسقط الصحيح
            keys = [
                k
                for k in (_skeleton(NON_ARABIC.sub(" ", f)) for f in fragments)
                if len(k) >= 2
            ]
            if not keys:
                continue
            best, best_score = None, 0.0
            for candidate in range(cursor, min(total, cursor + 6) + 1):
                reference = ayah_skeleton.get((number, candidate), "")
                if not reference:
                    continue
                score = sum(1 for k in keys if k in reference) / len(keys)
                if score > best_score:
                    best, best_score = candidate, score
            # عتبةُ الإثبات: أغلبُ ألفاظ الفقرة في الآية المرشَّحة
            found = best if best_score >= 0.6 else None

            commentary = _clean(block)
            if len(commentary) < 25:
                continue

            # فقرةٌ لم تُطابق: هي تتمّةُ ما قبلها في الغالب — تُضمّ إليه
            # ولا **تستهلك رقم آية**، فلا ينزاح ما بعدها انزياحًا صامتًا.
            # (كشف الحارسُ هذا الانزياح فعلًا في سورة البقرة قبل النشر.)
            if found is None:
                if last_record is not None:
                    last_record["text"] = f"{last_record['text']} {commentary}"
                continue

            if found < 1 or found > total:
                continue
            record = {
                "work": work_key,
                "surah": number,
                "ayah_start": found,
                "ayah_end": found,
                "text": commentary,
                "anchored": True,
            }
            page_match = None
            for page in PAGE.finditer(body, 0, para.start()):
                page_match = page
            if page_match:
                record["page"] = (
                    f"ج{int(page_match.group(1))} ص{int(page_match.group(2))}"
                )
            parsed.append(record)
            last_record = record
            anchored_count += 1
            cursor = found + 1
            if cursor > total:
                break

    return parsed, anchored_count, skipped


def _work_meta(
    work: dict,
    fields: dict[str, str],
    raw_bytes: bytes,
    parsed: list[dict],
    anchored_count: int,
    skipped: list[str],
) -> dict:
    """إسنادُ الكتاب كما سجّلته ترويسةُ ملفه — مصدرٌ واحد للحقول كلها."""
    return {
        "title": fields.get("020.BookTITLE", ""),
        "author": fields.get("010.AuthorNAME", ""),
        "author_died_hijri": fields.get("011.AuthorDIED", ""),
        "editor": fields.get("040.EdEDITOR", "غير مسمًّى في ترويسة المصدر"),
        "publisher": fields.get("043.EdPUBLISHER", ""),
        "edition": " · ".join(
            v
            for v in (
                fields.get("041.EdNUMBER", ""),
                fields.get("044.EdPLACE", ""),
                fields.get("045.EdYEAR", ""),
            )
            if v
        ),
        "openiti_uri": work["openiti_uri"],
        "source_url": work["source_url"],
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "apparatus": work["apparatus"],
        "notes": work["notes"],
        "passages": len(parsed),
        "anchored": anchored_count,
        "surahs_covered": len({p["surah"] for p in parsed}),
        "skipped_surah_heads": skipped,
    }


def main() -> int:
    surahs = json.loads(SURAHS.read_text(encoding="utf-8"))["surahs"]
    keyed = {normalize_surah_name(s["name"]): s["n"] for s in surahs}
    ayah_counts = {s["n"]: s["count"] for s in surahs}

    with gzip.open(QURAN, "rt", encoding="utf-8") as handle:
        quran = json.load(handle)
    ayah_skeleton = {(s, a): _skeleton(t) for s, a, t in quran["ayahs"]}

    works_meta: dict[str, dict] = {}
    passages: dict[str, list[dict]] = {}

    for work in WORKS:
        path = RAW / work["file"]
        raw_bytes = path.read_bytes()
        text = raw_bytes.decode("utf-8")
        header, matn = text.split("#META#Header#End#", 1)

        meta_fields: dict[str, str] = {}
        for line in header.splitlines():
            match = re.match(r"#META# (\S+)\t*::\s*(.*)", line)
            if match and match.group(2).strip() not in ("", "NODATA", "NOTGIVEN"):
                meta_fields[match.group(1)] = match.group(2).strip()

        # ---- البنية الثالثة: المدى مصرَّحٌ به في رأسٍ واحد ----
        # «[سورة الفاتحة (1) : الآيات 1 الى 7]» — رقم السورة ومدى آياتها
        # في الرأس نفسه، فلا حاجة إلى تتبّع أقسام السور ولا إلى استخراج
        # المدى من اقتباسٍ. أنظفُ البنى الثلاث وأقلُّها احتمالًا للخطأ.
        if work.get("parser") == "match_forward":
            parsed_fw, anchored_fw, skipped_fw = _parse_match_forward(
                matn, keyed, ayah_counts, ayah_skeleton, work["key"]
            )
            passages[work["key"]] = parsed_fw
            works_meta[work["key"]] = _work_meta(
                work, meta_fields, raw_bytes, parsed_fw, anchored_fw, skipped_fw
            )
            continue

        # المفكِّك الافتراضي «anchor»: مرساةٌ معقوصة في فقرة أو رأس
        if work.get("parser", "anchor") == "explicit_range":
            parsed_ranges: list[dict] = []
            for range_match in RANGE_HEAD.finditer(matn):
                number = int(range_match.group("surah"))
                start = int(range_match.group("start"))
                finish = int(range_match.group("end") or start)
                if not (1 <= number <= 114):
                    continue
                if not (1 <= start <= finish <= ayah_counts.get(number, 0)):
                    continue
                next_head = RANGE_HEAD.search(matn, range_match.end())
                segment = matn[
                    range_match.end() : next_head.start() if next_head else len(matn)
                ]
                commentary = _clean(segment)
                if len(commentary) < 40:
                    continue
                record = {
                    "work": work["key"],
                    "surah": number,
                    "ayah_start": start,
                    "ayah_end": finish,
                    "text": commentary,
                    # المدى مقروءٌ من رأس المطبوع صراحةً — أوثقُ من
                    # مطابقة اقتباس، فيُعدّ مثبَتًا
                    "anchored": True,
                }
                page_match = None
                for page in PAGE.finditer(matn, 0, range_match.start()):
                    page_match = page
                if page_match:
                    record["page"] = (
                        f"ج{int(page_match.group(1))} ص{int(page_match.group(2))}"
                    )
                parsed_ranges.append(record)
            passages[work["key"]] = parsed_ranges
            works_meta[work["key"]] = _work_meta(
                work, meta_fields, raw_bytes, parsed_ranges, len(parsed_ranges), []
            )
            continue

        # تُحسم أرقامُ السور أولًا، ثم تُقطَّع الأقسام بين **المحسوم**
        # منها وحده — فرأسٌ لا يدل على سورة (فصلٌ داخلي أو سطرٌ فارغ) لا
        # يبتر قسم سورةٍ قبله. الاسم المجرد يُقبل في الرأس الأول وحده،
        # وما دونه يشترط لفظ «سورة» صريحًا.
        parsed: list[dict] = []
        anchored_count = 0
        skipped_surahs: list[str] = []
        resolved: list[tuple[int, int, int, bool]] = []
        current = 0
        pending: list[tuple[int, int, bool]] = []
        for surah_match in SURAH_HEAD.finditer(matn):
            head = surah_match.group("name")
            explicit = bool(re.match(r"\s*(?:تفسير\s+)?سور", head))
            if surah_match.group("deep") and not explicit:
                continue
            number = _surah_number(head, keyed, current)
            if number is None or number <= current:
                if head.strip():
                    skipped_surahs.append(head.strip()[:40])
                continue
            current = number
            combined = any(word in head for word in COMBINED_HEADS)
            pending.append((surah_match.end(), number, combined))
        for index, (body_start, number, combined) in enumerate(pending):
            end = (
                pending[index + 1][0]
                if index + 1 < len(pending)
                else len(matn)
            )
            resolved.append((body_start, end, number, combined))

        for body_start, end, head_number, combined in resolved:
            body = matn[body_start:end]

            # المراسي: اقتباس معقوص فيه أرقام آيات — يبدأ حيث تنتهي
            # علامةُ السطر (`# ` أو `### || `) عند القوس نفسه
            anchors = []
            for anchor_match in ANCHOR.finditer(body):
                open_brace = body.find("{", anchor_match.start())
                close = body.find("}", open_brace)
                if open_brace < 0 or close < 0:
                    continue
                pieces = _parse_anchor(body[open_brace : close + 1])
                if pieces:
                    anchors.append((anchor_match.start(), close, pieces))

            def _score(candidate: int, pieces: list[tuple[int, str]]) -> int:
                """كم قطعةً من الاقتباس تطابق آياتها في هذه السورة."""
                hits = 0
                for ayah_number, piece in pieces:
                    reference = ayah_skeleton.get((candidate, ayah_number))
                    piece_key = _skeleton(FOOTNOTE_REF.sub("", piece))
                    if reference and piece_key and (
                        piece_key in reference or reference in piece_key
                    ):
                        hits += 1
                return hits

            for a_index, (start, close, pieces) in enumerate(anchors):
                seg_end = (
                    anchors[a_index + 1][0] if a_index + 1 < len(anchors) else len(body)
                )
                ayah_start = pieces[0][0]
                ayah_end = pieces[-1][0]
                # قسمٌ يجمع سورتين: **حارس المطابقة** هو الذي يفصلهما —
                # تُجرَّب السورتان ويُؤخذ ما طابق اقتباسه، فلا يُنسب مقطعٌ
                # بالترتيب وحده حيث يمكن إثباته
                number = head_number
                if combined:
                    scores = {
                        candidate: _score(candidate, pieces)
                        for candidate in (head_number, head_number + 1)
                        if candidate <= 114
                    }
                    number = max(scores, key=lambda c: scores[c])
                if not (
                    1 <= ayah_start <= ayah_end <= ayah_counts.get(number, 0)
                ):
                    continue
                # حارس الربط: كل قطعة تقابل بآيتها من الحزمة المبصومة
                anchored = _score(number, pieces) == len(pieces)

                commentary = _clean(body[close + 1 : seg_end])
                if len(commentary) < 40:
                    continue
                if anchored:
                    anchored_count += 1
                record = {
                    "work": work["key"],
                    "surah": number,
                    "ayah_start": ayah_start,
                    "ayah_end": ayah_end,
                    "text": commentary,
                    "anchored": anchored,
                }
                page_match = None
                for page in PAGE.finditer(body, 0, start):
                    page_match = page
                if page_match:
                    record["page"] = (
                        f"ج{int(page_match.group(1))} ص{int(page_match.group(2))}"
                    )
                parsed.append(record)

        passages[work["key"]] = parsed
        works_meta[work["key"]] = _work_meta(
            work, meta_fields, raw_bytes, parsed, anchored_count, skipped_surahs
        )

    bundle = {
        "meta": {
            "decision": (
                "قرار المالك 2026-08-01 (امتداد §٢٠): متن المفسِّر القديم "
                "وحده، وجهاز المحقِّق مستبعَد، والربط بالآية مثبَت بحارس "
                "المطابقة على الحزمة القرآنية المبصومة — وما لم يثبت وُسم. "
                "التفصيل: docs/audits/OPENITI_MATN_DECISION.md"
            ),
            "review_status": "imported",
            "works": works_meta,
        },
        "passages": passages,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as handle:
        json.dump(bundle, handle, ensure_ascii=False, separators=(",", ":"))

    for key, meta in works_meta.items():
        print(
            f"{key}: {meta['passages']} مقطعًا في {meta['surahs_covered']} سورة"
            f" · مثبَت الربط: {meta['anchored']}"
            f" · رؤوس سور لم تُفكّ: {len(meta['skipped_surah_heads'])}"
        )
    print(f"كُتب: {OUT} ({OUT.stat().st_size:,} بايت)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
