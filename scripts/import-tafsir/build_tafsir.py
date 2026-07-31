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
    },
]

SURAH_HEAD = re.compile(r"^### \| ?(سورة .*)$", re.M)
# اقتباسٌ رأسي: فقرة تبدأ بقوس معقوص وفي داخله أرقام آيات
ANCHOR = re.compile(r"^# \{", re.M)
PAGE = re.compile(r"PageV(\d+)P(\d+)")
MILESTONE = re.compile(r"\s*ms\d+\s*")
FOOTNOTE_REF = re.compile(r"\s*\(\d+\)")
WS = re.compile(r"\s+")

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


def _surah_number(head: str, keyed: dict[str, int], previous: int) -> int | None:
    """رقم السورة من اسمها في الرأس — والترتيب المصحفي حَكَمٌ مساند."""
    name = FOOTNOTE_REF.sub("", head)
    name = re.sub(r"^سورة\s+", "", name).strip()
    name = re.sub(r"\s*(مكية|مدنية).*$", "", name).strip()
    key = normalize_surah_name(name)
    if key in keyed:
        return keyed[key]
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

        surah_heads = list(SURAH_HEAD.finditer(matn))
        current = 0
        parsed: list[dict] = []
        anchored_count = 0
        skipped_surahs: list[str] = []

        for index, surah_match in enumerate(surah_heads):
            end = (
                surah_heads[index + 1].start()
                if index + 1 < len(surah_heads)
                else len(matn)
            )
            number = _surah_number(surah_match.group(1), keyed, current)
            if number is None or number <= current:
                skipped_surahs.append(surah_match.group(1)[:40])
                continue
            current = number
            body = matn[surah_match.end() : end]

            # المراسي: فقرات تفتتح بمعقوص فيه أرقام آيات
            anchors = []
            for anchor_match in ANCHOR.finditer(body):
                close = body.find("}", anchor_match.start())
                if close < 0:
                    continue
                block = body[anchor_match.start() + 2 : close + 1]
                pieces = _parse_anchor(block)
                if pieces:
                    anchors.append((anchor_match.start(), close, pieces))

            for a_index, (start, close, pieces) in enumerate(anchors):
                seg_end = (
                    anchors[a_index + 1][0] if a_index + 1 < len(anchors) else len(body)
                )
                ayah_start = pieces[0][0]
                ayah_end = pieces[-1][0]
                if not (
                    1 <= ayah_start <= ayah_end <= ayah_counts.get(number, 0)
                ):
                    continue
                # حارس الربط: كل قطعة تقابل بآيتها من الحزمة المبصومة
                matched = 0
                for ayah_number, piece in pieces:
                    reference = ayah_skeleton.get((number, ayah_number))
                    piece_key = _skeleton(FOOTNOTE_REF.sub("", piece))
                    if reference and piece_key and (
                        piece_key in reference or reference in piece_key
                    ):
                        matched += 1
                anchored = matched == len(pieces)

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
        works_meta[work["key"]] = {
            "title": meta_fields.get("020.BookTITLE", ""),
            "author": meta_fields.get("010.AuthorNAME", ""),
            "author_died_hijri": meta_fields.get("011.AuthorDIED", ""),
            "editor": meta_fields.get("040.EdEDITOR", "غير مسمًّى في ترويسة المصدر"),
            "publisher": meta_fields.get("043.EdPUBLISHER", ""),
            "edition": " · ".join(
                v
                for v in (
                    meta_fields.get("041.EdNUMBER", ""),
                    meta_fields.get("044.EdPLACE", ""),
                    meta_fields.get("045.EdYEAR", ""),
                )
                if v
            ),
            "openiti_uri": work["openiti_uri"],
            "source_url": work["source_url"],
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "apparatus": work["apparatus"],
            "passages": len(parsed),
            "anchored": anchored_count,
            "surahs_covered": len({p["surah"] for p in parsed}),
            "skipped_surah_heads": skipped_surahs,
        }

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
