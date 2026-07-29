#!/usr/bin/env python
"""يبني حزمة معجم لِين من مجموعة Perseus العربية.

**لماذا لِين، ولماذا وحده:** فحصُ المعاجم (docs/audits/LISAN_AL_ARAB_SOURCING.md
و SOURCE_ASSEMBLY_ROUTES.md) انتهى إلى أنه المعجم الوحيد الذي يجتاز §10
كاملًا اليوم — «الكتاب + الطبعة + الملف + الترخيص + البصمة» — وكلُّها
**مقروءةٌ من داخل الملف نفسه** لا من وصف ناشرٍ ولا وسيط:

    <sourceDesc>  London · Williams and Norgate · 1863
    <availability status="free">  بثلاثة شروط منصوصة

**والخطوط الحمراء المحروسة هنا:**

1. **لا يُفكّ ترميزُ المصدر إلى حرفٍ عربي.** نصّ لِين العربي مكتوب بترميز
   لاتيني خاصّ بـPerseus — ليس باكوولتر قياسيًّا: لا `>` ولا `<` ولا `|`
   فيه، وفيه `^` و`=` غير موثَّقين. وأيُّ فكٍّ ظنّي يولّد عربيةً لم يكتبها
   لِين. فيُنقل الترميز **كما هو** ويُوسم، ويُترك فكُّه لمن يوثّق جدوله.
2. **المطابقة بجذورنا لا بجذوره.** يُحوَّل جذرُنا العربي إلى هيكلٍ صامت
   ويُقابَل بهيكل مفتاح لِين — فالاتجاه من المعلوم إلى المجهول، ولا
   يُستنتج جذرٌ عربي من ترميز.
3. **لا مادةَ بلا صفحة.** كل مدخلٍ يحمل رقم صفحته من طبعة ١٨٦٣ كما ورد
   في `<pb n="…"/>`، وإلا أُسقط.

التشغيل:
    python scripts/import-lexicon/build_lane.py <مسار hopper-texts-Arabic.tar.gz>

المصدر:
    https://www.perseus.tufts.edu/hopper/opensource/downloads/texts/hopper-texts-Arabic.tar.gz
"""

from __future__ import annotations

import gzip
import html
import hashlib
import json
import re
import sys
import tarfile
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "apps" / "api" / "data" / "lane_bundle.json.gz"
ROOTS = REPO / "apps" / "web" / "public" / "data" / "v1" / "roots.json"

# مقيسٌ من الأرشيف نفسه بتاريخ 2026-07-29، ويُتحقَّق منه في كل بناء
EXPECTED_BYTES = 15_506_171
EXPECTED_SHA256 = "091f578bc744748e05b40179206c6dda54e059b0becbde4d95a1d1066f08a741"
EXPECTED_LANE_FILES = 36

# تقابل الصوامت وحدها — ولا يُستعمل إلا في اتجاه: عربي ← هيكل لاتيني.
CONSONANTS = {
    "ء": "'", "ا": "A", "ب": "b", "ة": "p", "ت": "t", "ث": "v", "ج": "j",
    "ح": "H", "خ": "x", "د": "d", "ذ": "*", "ر": "r", "ز": "z", "س": "s",
    "ش": "$", "ص": "S", "ض": "D", "ط": "T", "ظ": "Z", "ع": "E", "غ": "g",
    "ف": "f", "ق": "q", "ك": "k", "ل": "l", "م": "m", "ن": "n", "ه": "h",
    "و": "w", "ى": "Y", "ي": "y",
}
# ما يُحذف من مفاتيح لِين: حركاتٌ وتنوينٌ وشدّةٌ وسكون وزياداتُ Perseus
LANE_MARKS = set("auioFNK~^=`_@.,0PGB ")

ENTRY = re.compile(r'<entryFree\b[^>]*\bkey="([^"]*)"[^>]*>')
PAGE = re.compile(r'<pb\b[^>]*\bn="(\d+)"')
TAG = re.compile(r"<[^>]+>")
FOREIGN = re.compile(r'<foreign\b[^>]*>([^<]*)</foreign>')


def skeleton(key: str) -> str:
    """هيكل الصوامت من مفتاح لِين — بحذف الحركات لا بتأويلها."""
    return "".join(c for c in key if c not in LANE_MARKS)


def root_skeleton(root: str) -> str | None:
    """هيكل جذرنا العربي. يعيد None إن ورد حرف خارج الجدول — ولا يُخمَّن."""
    out = []
    for char in root:
        mapped = CONSONANTS.get(char)
        if mapped is None:
            return None
        out.append(mapped)
    return "".join(out)


# لواحق الضمير في صيغ لِين المُستشهَد بها: مفتاح كَتَبَهُ هو `katabahu`
# فهيكله `ktbh` لا `ktb`. وتجريدها **مقيسٌ آمن**: لا جذر في فهرسنا يساوي
# جذرًا آخر مضافًا إليه لاحقة (فُحصت الـ١٦٤٢ فكانت حالات اللبس صفرًا).
PRONOUNS = ("humA", "hun~", "hum", "hA", "hu", "h", "kmA", "km", "ky", "k", "nA", "ny")


def candidates(shape: str) -> list[str]:
    """أشكالُ المفتاح التي تقابل هذا الجذر — الأضبطُ أولًا."""
    forms = [shape]
    forms += [shape + suffix for suffix in PRONOUNS]
    # الهمزة: جذورنا تكتبها ألفًا، ولِين يكتبها `'`
    if shape.startswith("A"):
        alt = "'" + shape[1:]
        forms += [alt] + [alt + suffix for suffix in PRONOUNS]
    return forms


def read_header(xml: str) -> dict:
    """بيان المصدر والإتاحة **من داخل الملف** — لا من وصفٍ خارجه."""
    place = re.search(r"<pubPlace>([^<]+)</pubPlace>\s*<publisher>([^<]+)</publisher>\s*<date>([^<]+)</date>", xml)
    avail = re.search(r"<availability[^>]*>(.*?)</availability>", xml, re.S)
    quote = re.search(r"<quote>(.*?)</quote>", avail.group(1), re.S) if avail else None
    items = re.findall(r"<item>(.*?)</item>", avail.group(1), re.S) if avail else []
    return {
        "edition_place": place.group(1).strip() if place else None,
        "edition_publisher": place.group(2).strip() if place else None,
        "edition_year": place.group(3).strip() if place else None,
        "attribution_required": re.sub(r"\s+", " ", TAG.sub("", quote.group(1))).strip()
        if quote
        else None,
        "conditions": [re.sub(r"\s+", " ", TAG.sub("", i)).strip() for i in items],
    }


def entry_text(chunk: str) -> tuple[str, list[str]]:
    """نصّ المدخل الإنجليزي، ومواضع الترميز اللاتيني **موسومةً لا مفكوكة**."""
    transliterations = [t.strip() for t in FOREIGN.findall(chunk) if t.strip()]
    text = html.unescape(re.sub(r"\s+", " ", TAG.sub(" ", chunk)).strip())
    return text, transliterations


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__.strip().splitlines()[-3].strip())
    archive = Path(sys.argv[1])
    if not archive.exists():
        raise SystemExit(f"الأرشيف غير موجود: {archive}")

    raw = archive.read_bytes()
    archive_sha = hashlib.sha256(raw).hexdigest()

    # **حارسٌ لزِمَ بعد عطبٍ وقع فعلًا:** أوّل تنزيلٍ استُؤنف بالمدى قبِل
    # ردودًا تجاهلت `Range` فتضاعفت أجزاؤه — ٤٩ م.ب فيها توقيعا gzip،
    # وقرأ منها tarfile أربعةَ ملفاتٍ من ستةٍ وثلاثين ثم صمت. فبُنيت حزمةٌ
    # ناقصةٌ تبدو سليمة. ولذلك: البصمة والحجم يُتحقَّق منهما هنا لا هناك.
    if len(raw) != EXPECTED_BYTES or archive_sha != EXPECTED_SHA256:
        raise SystemExit(
            "الأرشيف لا يطابق المتوقَّع — لا يُبنى منه شيء.\n"
            f"  الحجم:  {len(raw):,}  والمتوقَّع {EXPECTED_BYTES:,}\n"
            f"  البصمة: {archive_sha}\n"
            f"  المتوقَّع: {EXPECTED_SHA256}\n"
            "أعد التنزيل، ولا تقبل ردًّا جزئيًّا إلا بـ206 وContent-Range مطابق."
        )
    if raw.count(b"\x1f\x8b\x08") != 1:
        raise SystemExit("توقيعات gzip متعددة — الملف مُلصَقٌ من تنزيلات ناقصة.")

    with tarfile.open(archive, "r:gz") as tar:
        # **لِين وحده.** الأرشيف يضمّ ترجماتِ قرآنٍ (Pickthall وShakir
        # وYusuf Ali) ومعجم Salmone، ولكلٍّ حقوقٌ مستقلة لا تُورَّث بدخول
        # الأرشيف. فتُستبعَد صراحةً لا سهوًا.
        members = {
            m.name: tar.extractfile(m).read()
            for m in tar.getmembers()
            if m.isfile() and m.name.endswith(".xml") and "/Lane/" in m.name
        }
    if len(members) != EXPECTED_LANE_FILES:
        raise SystemExit(
            f"ملفات لِين {len(members)} والمتوقَّع {EXPECTED_LANE_FILES} — أرشيفٌ ناقص."
        )

    files_sha = {Path(n).name: hashlib.sha256(b).hexdigest() for n, b in members.items()}
    header = read_header(next(iter(members.values())).decode("utf-8", "replace"))
    assert header["edition_year"] == "1863", header
    assert header["conditions"], "بيان الإتاحة مفقود — لا يُدخَل مصدر بلا شروط مقروءة"

    # فهرس: هيكل ← [مداخل]
    index: dict[str, list[dict]] = defaultdict(list)
    for name, blob in members.items():
        xml = blob.decode("utf-8", "replace")
        letter = Path(name).name
        marks = [(m.start(), m.group(1)) for m in PAGE.finditer(xml)]
        hits = list(ENTRY.finditer(xml))
        for i, match in enumerate(hits):
            start = match.end()
            end = hits[i + 1].start() if i + 1 < len(hits) else len(xml)
            key = match.group(1)
            if " " in key:
                continue  # عبارةٌ لا مدخل
            shape = skeleton(key)
            if not 2 <= len(shape) <= 5:
                continue
            # الصفحة السارية: آخر <pb> قبل المدخل
            page = None
            for position, number in marks:
                if position <= match.start():
                    page = number
                else:
                    break
            if page is None:
                continue  # §لا مادة بلا صفحة
            text, translit = entry_text(xml[start:end])
            if len(text) < 40:
                continue
            index[shape].append(
                {
                    "key": key,
                    "page": int(page),
                    "file": letter,
                    "text": text[:4000],
                    "translit": translit[:12],
                }
            )

    roots = json.loads(ROOTS.read_text(encoding="utf-8"))["roots"]
    matched: dict[str, list[dict]] = {}
    for root in roots:
        shape = root_skeleton(root)
        if not shape:
            continue
        for form in candidates(shape):
            if form in index:
                matched[root] = index[form][:6]
                break

    bundle = {
        "meta": {
            "work": "An Arabic-English Lexicon",
            "author": "Edward William Lane",
            "edition": f"{header['edition_place']}: {header['edition_publisher']}, {header['edition_year']}",
            "digitised_by": "Perseus Digital Library, Tufts University",
            "source_url": (
                "https://www.perseus.tufts.edu/hopper/opensource/downloads/"
                "texts/hopper-texts-Arabic.tar.gz"
            ),
            "archive_sha256": archive_sha,
            "file_sha256": files_sha,
            "availability": header,
            "review_status": "imported",
            # حدودٌ تُعلَن ولا تُخفى
            "limits": {
                "letters_available": sorted(files_sha),
                "roots_matched": len(matched),
                "roots_total": len(roots),
                "script": (
                    "عربية المصدر بترميز Perseus اللاتيني، تُنقل كما هي ولا "
                    "تُفكّ — فكُّها الظنّي يولّد نصًّا لم يكتبه لِين."
                ),
                "language": "التعريفات بالإنجليزية؛ لِين شاهدٌ ثانوي لا أصلٌ عربي.",
            },
        },
        "entries": matched,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as handle:
        json.dump(bundle, handle, ensure_ascii=False, separators=(",", ":"))

    print(f"الطبعة: {bundle['meta']['edition']}")
    print(f"ملفات المصدر: {len(files_sha)} · بصمة الأرشيف: {archive_sha[:16]}…")
    print(f"جذور مطابَقة: {len(matched)} من {len(roots)} ({100*len(matched)/len(roots):.1f}%)")
    print(f"كُتب: {OUT} ({OUT.stat().st_size:,} بايت)")


if __name__ == "__main__":
    main()
