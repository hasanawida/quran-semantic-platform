"""توليد المواضع المرجعية من المصدر — لا اختراع ولا إدخال يدوي.

كل موضع يُنتقى من حزمة الصرف نفسها بموضعه واستشهاده، فلا يمكن أن يحمل
جذرًا لم يقله المصدر. الغرض من هذه المواضع **كشف انحراف خط المعالجة**
(ترميز ← استيراد ← اشتقاق)، لا الفصل في خلاف لغوي.

التغطية مقصودة نمطًا نمطًا: المهموز والأجوف والناقص والمضعّف والمثال
والرباعي، والسوابق واللواحق المركبة، و«لا جذر» مقابل «لا تحليل»،
والآيات غير المحاذية، وحدود المصحف.

الاختيار حتمي وموزَّع: تُجمع كل المواضع المطابقة لكل نمط ثم تُنتقى بخطوة
ثابتة على امتداد المصحف، فلا تتكدس المراسي في السور الأولى ولا يتغيّر
الملف بين تشغيلين.
"""

from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MORPH_BUNDLE = REPO_ROOT / "apps" / "api" / "data" / "morphology_qac04.json.gz"
TEXT_BUNDLE = REPO_ROOT / "apps" / "api" / "data" / "quran_bundle.json.gz"
OUT_PATH = REPO_ROOT / "apps" / "api" / "data" / "golden_roots.json"

sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
from app.utils.arabic import tokenize_ayah  # noqa: E402

# عدد المواضع المنتقاة لكل نمط
PER_PATTERN = 12

# آيات يختلف فيها عدّ الكلمات بين النص والمصدر (تُعامَل بحذر: يُحفظ
# التحليل بترقيم المصدر ويُمنع التمييز)
MISALIGNED = [(2, 181), (8, 6), (13, 37), (37, 130)]


def load(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def root_patterns(root_key: str) -> list[str]:
    """تصنيف الجذر بأنماط الصرف العربي.

    ملاحظة: «ا» في مفتاح الجذر همزة دائمًا لا ألفًا أصلية — الألف الخالصة
    ليست من أصول الجذر أبدًا (اصطلاح المدونة، ووثيقة سياسة الهمزات)."""
    patterns: list[str] = []
    if len(root_key) == 4:
        patterns.append("رباعي")
    if "ا" in root_key:
        patterns.append("مهموز")
    if len(root_key) >= 3 and root_key[1] in "وي":
        patterns.append("أجوف")
    if root_key and root_key[-1] in "وي":
        patterns.append("ناقص")
    if root_key and root_key[0] in "وي":
        patterns.append("مثال")
    if len(root_key) >= 3 and root_key[-1] == root_key[-2]:
        patterns.append("مضعّف")
    return patterns or ["سالم"]


PATTERN_NOTES = {
    "سالم": "جذر سالم — الحالة الأساس",
    "مهموز": "جذر مهموز: الهمزة تُمثَّل ألفًا في المفتاح (سياسة الهمزات)",
    "أجوف": "جذر أجوف: حرف علة في الوسط — يكشف خطأ تطبيع الألف",
    "ناقص": "جذر ناقص: حرف علة في الآخر — يكشف خلط الألف المقصورة بالياء",
    "مثال": "جذر مثال: حرف علة في الأول",
    "مضعّف": "جذر مضعّف: تكرار الحرف الأخير — يكشف فك الإدغام الخاطئ",
    "رباعي": "جذر رباعي — يكشف حدًّا خاطئًا لطول الجذر",
}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    morph = load(MORPH_BUNDLE)
    text_bundle = load(TEXT_BUNDLE)
    texts = {(s, a): t for s, a, t in text_bundle["ayahs"]}

    by_word: dict[tuple[int, int, int], list] = defaultdict(list)
    for segment in morph["segments"]:
        by_word[(segment[0], segment[1], segment[2])].append(segment)

    source_words = {(s, a): count for s, a, count in morph["source_words_per_ayah"]}
    aligned = {
        key
        for key, count in source_words.items()
        if count == len(tokenize_ayah(texts[key]))
    }

    cases: list[dict] = []
    seen: set[tuple[int, int, int]] = set()

    def add(position, roots, citation, note) -> None:
        if position in seen:
            return
        seen.add(position)
        cases.append(
            {
                "surah": position[0],
                "ayah": position[1],
                "word": position[2],
                "roots": sorted(roots),
                "citation": citation,
                "note": note,
            }
        )

    def qac_ref(position, segments) -> str:
        stems = [s for s in segments if s[11]]
        parts = " و".join(
            f"({s[0]}:{s[1]}:{s[2]}:{s[3]}) ROOT:{s[10]}" for s in stems
        )
        return f"QAC {parts}" if parts else f"QAC ({position[0]}:{position[1]}:{position[2]}) بلا ROOT"

    ordered = sorted(by_word)

    # ---- 1) أنماط الجذور ------------------------------------------------
    # تُجمع كل المواضع المطابقة لكل نمط ثم تُنتقى موزَّعة على المصحف
    # (لا أوائلها) حتى لا تتكدس المراسي في السور الأولى. الانتقاء بخطوة
    # ثابتة فيبقى حتميًا.
    candidates: dict[str, list] = defaultdict(list)
    for position in ordered:
        if position[:2] not in aligned:
            continue
        segments = by_word[position]
        roots = {s[11] for s in segments if s[11]}
        if len(roots) != 1:
            continue
        pattern = root_patterns(next(iter(roots)))[0]
        candidates[pattern].append((position, segments, roots))

    per_pattern: dict[str, int] = defaultdict(int)
    for pattern, matches in sorted(candidates.items()):
        step = max(1, len(matches) // PER_PATTERN)
        for position, segments, roots in matches[::step][:PER_PATTERN]:
            per_pattern[pattern] += 1
            add(
                position,
                roots,
                qac_ref(position, segments),
                PATTERN_NOTES.get(pattern, pattern),
            )

    # ---- 2) السوابق واللواحق المركّبة -----------------------------------
    pre_matches, suf_matches = [], []
    for position in ordered:
        if position[:2] not in aligned:
            continue
        segments = by_word[position]
        roots = {s[11] for s in segments if s[11]}
        if not roots:
            continue
        pre = sum(1 for s in segments if "PREFIX" in s[6])
        suf = sum(1 for s in segments if "SUFFIX" in s[6])
        if pre >= 2:
            pre_matches.append((position, segments, roots, pre))
        elif suf >= 2:
            suf_matches.append((position, segments, roots, suf))

    prefixes = suffixes = 0
    for matches, label in ((pre_matches, "سوابق"), (suf_matches, "لواحق")):
        step = max(1, len(matches) // PER_PATTERN)
        for position, segments, roots, count in matches[::step][:PER_PATTERN]:
            note = (
                f"كلمة بـ{count} سوابق — الجذر من الجذع لا من السابقة"
                if label == "سوابق"
                else f"كلمة بـ{count} لواحق — اللاحقة لا تُدخل جذرًا"
            )
            add(position, roots, qac_ref(position, segments), note)
            if label == "سوابق":
                prefixes += 1
            else:
                suffixes += 1

    # ---- 3) «لا جذر» مقابل «لا تحليل» -----------------------------------
    no_root_matches = []
    for position in ordered:
        if position[:2] not in aligned:
            continue
        segments = by_word[position]
        if any(s[11] for s in segments):
            continue
        pos_tags = {s[7] for s in segments if s[7]}
        if pos_tags:
            no_root_matches.append((position, segments, pos_tags))

    step = max(1, len(no_root_matches) // PER_PATTERN)
    no_root = 0
    for position, segments, pos_tags in no_root_matches[::step][:PER_PATTERN]:
        no_root += 1
        add(
            position,
            set(),
            qac_ref(position, segments),
            f"محلَّلة بلا جذر ({'، '.join(sorted(pos_tags))}) — "
            "تمييز «لا جذر» عن «لا تحليل»",
        )

    # ---- 4) الكلمة الوحيدة بجذرين ---------------------------------------
    for position, segments in by_word.items():
        roots = {s[11] for s in segments if s[11]}
        if len(roots) > 1:
            add(
                position,
                roots,
                qac_ref(position, segments),
                "الكلمة الوحيدة في المصحف بجذرين — لا يُفرض جذر واحد للكلمة",
            )

    # ---- 5) الآيات غير المحاذية -----------------------------------------
    for surah, ayah in MISALIGNED:
        for word in range(1, source_words[(surah, ayah)] + 1):
            position = (surah, ayah, word)
            segments = by_word.get(position, [])
            roots = {s[11] for s in segments if s[11]}
            if not roots:
                continue
            add(
                position,
                roots,
                qac_ref(position, segments),
                "آية غير محاذية: الموضع يُحفظ بترقيم المصدر ويُمنع التمييز — "
                "مرساة السلوك المحافظ",
            )
            break

    # ---- 6) مرساتا فصل البسملة وحدود المصحف ------------------------------
    anchors = [
        ((2, 1, 1), "مرساة فصل البسملة: قبل الفصل كانت الكلمة الأولى «بِسْمِ»"),
        ((112, 1, 1), "مرساة فصل البسملة في السور القصيرة"),
        ((1, 1, 1), "أول كلمة في المصحف — حدّ النطاق"),
        ((114, 6, 3), "آخر آية في المصحف — حدّ النطاق"),
        ((2, 108, 4), "همزة على نبرة (تَسْـَٔلُوا۟) تصل إلى مفتاح سال"),
        ((2, 108, 7), "صورة همزة أخرى (سُئِلَ) بالمفتاح نفسه"),
        ((2, 186, 2), "همزة على ألف (سَأَلَكَ) بالمفتاح نفسه"),
        ((2, 255, 1), "اسم علم له جذر"),
    ]
    for position, note in anchors:
        segments = by_word.get(position, [])
        roots = {s[11] for s in segments if s[11]}
        # يُحذف الموضع من مجموعة المرئي ليُعاد بملاحظته الخاصة
        if position in seen:
            for index, case in enumerate(cases):
                if (case["surah"], case["ayah"], case["word"]) == position:
                    cases[index]["note"] = note
                    break
            continue
        add(position, roots, qac_ref(position, segments), note)

    cases.sort(key=lambda c: (c["surah"], c["ayah"], c["word"]))

    payload = {
        "purpose": (
            "مواضع مرجعية تكشف انحراف خط الاشتقاق (ترميز ← استيراد ← اشتقاق). "
            "ليست حكمًا علميًا مستقلًا: كل موضع منقول عن المدونة القرآنية "
            "بموضعه، والغرض أن يفشل الاختبار فورًا إن تغيّر سلوك الترميز أو "
            "المحاذاة أو الاستيراد. مولَّد بـ scripts/build-golden-cases.py "
            "ولا يُحرَّر يدويًا."
        ),
        "source": "Quranic Arabic Corpus 0.4 — https://corpus.quran.com",
        "cases": cases,
    }
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with_root = sum(1 for c in cases if c["roots"])
    print(f"تم توليد {len(cases)} موضعًا مرجعيًا في {OUT_PATH.name}")
    print(f"  بجذر: {with_root} | بلا جذر: {len(cases) - with_root}")
    print(f"  أنماط الجذور: {dict(per_pattern)}")
    print(f"  سوابق مركّبة: {prefixes} | لواحق مركّبة: {suffixes}")


if __name__ == "__main__":
    main()
