"""حارس فهرس الكلمات: كل موضعٍ يشير إلى الكلمة التي يدّعيها.

**لماذا:** فهرس `words/*.json` يربط صورةً مطبَّعة بمواضعها في المصحف
(فهرس الآية + رقم الكلمة). وانحرافُ رقمٍ واحدٍ فيه يعطي القارئ آيةً
صحيحة بكلمةٍ مميَّزة **خاطئة** — وهو أسوأ من ألّا يجد شيئًا، لأنه يبدو
صحيحًا.

ولا يكشفه فحصُ الأنواع ولا البناء: الأرقام أرقامٌ صالحة مهما كانت.
فيُفحص هنا **كل موضعٍ من السبعة والسبعين ألفًا** مقابل الحزمة نفسها.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from app.core.paths import data_file
from app.utils.arabic import normalize_arabic_search, tokenize_ayah

OUT = Path(__file__).resolve().parents[3] / "apps" / "web" / "public" / "data" / "v1"


@pytest.fixture(scope="module")
def ayahs() -> list[tuple[int, int, str]]:
    with gzip.open(data_file("quran_bundle.json.gz"), "rt", encoding="utf-8") as handle:
        return [tuple(row) for row in json.load(handle)["ayahs"]]


@pytest.fixture(scope="module")
def shards() -> list[dict]:
    directory = OUT / "words"
    if not directory.is_dir():
        pytest.skip(
            "فهرس الكلمات غير مولَّد. شغّل:\n"
            "  python scripts/export-static/build_data.py"
        )
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.json"))]


def test_every_indexed_position_resolves_to_that_exact_word(ayahs, shards):
    """العقد الأهم: الموضع يعطي الكلمة المفهرسة نفسها، لا جارتها."""
    wrong: list[str] = []
    total = 0
    for shard in shards:
        for form, (_count, _analyses, occurrences) in shard["forms"].items():
            for i in range(0, len(occurrences), 2):
                position, order = occurrences[i], occurrences[i + 1]
                surah, ayah, text = ayahs[position]
                tokens = tokenize_ayah(text)
                total += 1
                if not 1 <= order <= len(tokens):
                    wrong.append(f"{form}: {surah}:{ayah} الكلمة {order} خارج الحدود")
                    continue
                actual = normalize_arabic_search(tokens[order - 1][2])
                if actual != form:
                    wrong.append(f"{form}: {surah}:{ayah}#{order} أعطت {actual}")

    assert total == 77433, f"عدد المواضع {total} لا يطابق كلمات المصحف"
    assert not wrong, "مواضع تشير إلى كلمةٍ غير المفهرسة:\n  " + "\n  ".join(wrong[:20])


def test_declared_count_matches_stored_positions(shards):
    """العدد المعروض للمستعمل هو عدد المواضع المخزَّنة، لا رقمًا مستقلًا."""
    bad = [
        f"{form}: أُعلن {count} وخُزّن {len(occurrences) // 2}"
        for shard in shards
        for form, (count, _analyses, occurrences) in shard["forms"].items()
        if count * 2 != len(occurrences)
    ]
    assert not bad, "عددٌ معلَن يخالف المخزَّن:\n  " + "\n  ".join(bad[:20])


def test_every_form_lands_in_the_shard_named_by_its_first_letter(shards):
    """التشريح على الحرف الأول المطبَّع — وإلا بحث المتصفح في شريحةٍ لا
    تحوي الكلمة فأعطى «غير موجودة» وهي موجودة."""
    misplaced: list[str] = []
    for path, shard in zip(sorted((OUT / "words").glob("*.json")), shards):
        stem = path.stem
        for form in shard["forms"]:
            expected = (
                f"{ord(form[0]):04x}" if form[0].isalpha() else "_"
            )
            if expected != stem:
                misplaced.append(f"{form} في {stem} والمتوقع {expected}")
    assert not misplaced, "صور في الشريحة الخطأ:\n  " + "\n  ".join(misplaced[:20])


def test_analysis_indexes_point_inside_their_shard_tables(shards):
    """فهرس الجذر واللمّة داخل جدولَي الشريحة — و«−1» يعني أن المصدر
    لم يعطِ القيمة، ويُعرض كذلك ولا يُخمَّن."""
    broken: list[str] = []
    for shard in shards:
        roots, lemmas = shard["roots"], shard["lemmas"]
        for form, (_count, analyses, _occ) in shard["forms"].items():
            for pair in analyses:
                root_index, lemma_index = (int(part) for part in pair.split(","))
                if root_index >= len(roots) or lemma_index >= len(lemmas):
                    broken.append(f"{form}: {pair}")
                if root_index < -1 or lemma_index < -1:
                    broken.append(f"{form}: {pair} قيمة سالبة غير −1")
    assert not broken, "فهارس تحليل خارج الجداول:\n  " + "\n  ".join(broken[:20])
