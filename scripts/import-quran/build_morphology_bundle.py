"""بناء حزمة التحليل الصرفي الكامل من المدونة القرآنية (جامعة ليدز).

المصدر: quranic-corpus-morphology-0.4.txt — رخصة GNU GPL، يلزم ذكر المصدر
ورابطه <https://corpus.quran.com> وعدم تعديل الملف الأصلي.

المخرج: apps/api/data/morphology_qac04.json.gz — كل مقطع صرفي بموضعه
وصيغته ووسمه وسماته **حرفيًا كما في المصدر**، مع بصمة الملف المصدري.
لا يُشتق منه نص قرآني للعرض إطلاقًا؛ نص العرض من إصدار النص الموثق وحده.

التحقق البنيوي قبل الكتابة:
  - تسلسل المقاطع داخل كل كلمة يبدأ من 1 بلا فجوات
  - تسلسل الكلمات داخل كل آية يبدأ من 1 بلا فجوات
  - مجموعة آيات المدونة تطابق مجموعة آيات نص تنزيل تمامًا
  - كل محارف بكوولتر في الصيغ والأصول والجذور معروفة
  - كل مقطع STEM له قسم (POS)، وكل جذر يعطي مفتاحًا قانونيًا غير فارغ
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
OUT_PATH = REPO_ROOT / "apps" / "api" / "data" / "morphology_qac04.json.gz"

sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
from app.utils.arabic import normalize_root_input  # noqa: E402
from app.utils.buckwalter import split_lemma, to_arabic  # noqa: E402

MORPH_FILE = RAW_DIR / "quranic-corpus-morphology-0.4.txt"
TEXT_FILE = RAW_DIR / "quran-uthmani.txt"

SOURCE_CODE = "qac-0.4"
EXPECTED_SEGMENTS = 128219
EXPECTED_WORDS = 77429


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_text_ayah_keys() -> set[tuple[int, int]]:
    keys: set[tuple[int, int]] = set()
    for line in TEXT_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip("﻿")
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        keys.add((int(parts[0]), int(parts[1])))
    return keys


def parse_segments() -> list[dict]:
    segments: list[dict] = []
    for lineno, raw in enumerate(
        MORPH_FILE.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw.strip("﻿")
        if not line or line.startswith("#") or line.startswith("LOCATION"):
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            raise SystemExit(f"سطر غير متوقع ({lineno}): {raw!r}")
        location, form_bw, tag, features = parts
        loc = location.strip("()").split(":")
        if len(loc) != 4:
            raise SystemExit(f"موضع غير صالح ({lineno}): {location!r}")
        surah, ayah, word, segment = (int(x) for x in loc)

        lemma_bw: str | None = None
        root_bw: str | None = None
        is_stem = False
        pos: str | None = None
        for feature in features.split("|"):
            if feature == "STEM":
                is_stem = True
            elif feature.startswith("POS:"):
                pos = feature[4:]
            elif feature.startswith("LEM:"):
                lemma_bw = feature[4:]
            elif feature.startswith("ROOT:"):
                root_bw = feature[5:]

        if is_stem and not pos:
            raise SystemExit(f"مقطع STEM بلا قسم ({lineno}): {raw!r}")

        # يرفع BuckwalterError عند أي محرف غير معروف — لا تمرير بيانات مشوهة
        to_arabic(form_bw)
        lemma_ar = None
        lemma_index = None
        if lemma_bw:
            bare, lemma_index = split_lemma(lemma_bw)
            lemma_ar = to_arabic(bare)
        root_ar = None
        root_key = None
        if root_bw:
            root_ar = to_arabic(root_bw)
            root_key = normalize_root_input(root_ar)
            if not root_key:
                raise SystemExit(f"جذر يعطي مفتاحًا فارغًا ({lineno}): {root_bw!r}")

        segments.append(
            {
                "surah": surah,
                "ayah": ayah,
                "word": word,
                "segment": segment,
                "form_bw": form_bw,
                "tag": tag,
                "features": features,
                "pos": pos,
                "is_stem": is_stem,
                "lemma_bw": lemma_bw,
                "lemma_ar": lemma_ar,
                "lemma_index": lemma_index,
                "root_bw": root_bw,
                "root_ar": root_ar,
                "root_key": root_key,
            }
        )
    return segments


def validate(segments: list[dict]) -> dict[tuple[int, int], int]:
    """يتحقق من تسلسل الكلمات والمقاطع، ويعيد عدد كلمات كل آية وفق المدونة."""
    by_word: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    words_per_ayah: dict[tuple[int, int], set[int]] = defaultdict(set)
    for seg in segments:
        key = (seg["surah"], seg["ayah"], seg["word"])
        by_word[key].append(seg["segment"])
        words_per_ayah[(seg["surah"], seg["ayah"])].add(seg["word"])

    for (surah, ayah, word), seg_numbers in by_word.items():
        if seg_numbers != list(range(1, len(seg_numbers) + 1)):
            raise SystemExit(
                f"تسلسل مقاطع غير صحيح في {surah}:{ayah}:{word} → {seg_numbers}"
            )

    counts: dict[tuple[int, int], int] = {}
    for (surah, ayah), word_numbers in words_per_ayah.items():
        expected = set(range(1, len(word_numbers) + 1))
        if word_numbers != expected:
            raise SystemExit(f"تسلسل كلمات غير صحيح في {surah}:{ayah}")
        counts[(surah, ayah)] = len(word_numbers)

    text_keys = parse_text_ayah_keys()
    morph_keys = set(counts)
    if morph_keys != text_keys:
        missing = len(text_keys - morph_keys)
        extra = len(morph_keys - text_keys)
        raise SystemExit(f"عدم تطابق الآيات مع نص تنزيل: ناقص {missing}، زائد {extra}")

    if len(segments) != EXPECTED_SEGMENTS:
        raise SystemExit(f"عدد المقاطع {len(segments)} ≠ {EXPECTED_SEGMENTS}")
    if len(by_word) != EXPECTED_WORDS:
        raise SystemExit(f"عدد الكلمات {len(by_word)} ≠ {EXPECTED_WORDS}")
    return counts


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for path in (MORPH_FILE, TEXT_FILE):
        if not path.exists():
            raise SystemExit(f"ملف مصدر مفقود: {path}")

    segments = parse_segments()
    words_per_ayah = validate(segments)

    roots = {s["root_key"] for s in segments if s["root_key"]}
    lemmas = {s["lemma_ar"] for s in segments if s["lemma_ar"]}
    stems = sum(1 for s in segments if s["is_stem"])

    bundle = {
        "meta": {
            "source_code": SOURCE_CODE,
            "name": "Quranic Arabic Corpus (Kais Dukes, University of Leeds)",
            "url": "https://corpus.quran.com",
            "source_version": "0.4",
            "license": "GNU GPL — الإسناد ورابط المصدر وعدم تعديل الملف الأصلي",
            "review_status": "imported",
            "confidence": "machine_only",
            "notice": (
                "تحليل صرفي مستورد من مصدر خارجي موثق، لم يخضع لمراجعة المنصة. "
                "لا يُشتق منه نص قرآني للعرض."
            ),
            "file_sha256": sha256_file(MORPH_FILE),
            "counts": {
                "segments": len(segments),
                "words": len(words_per_ayah) and sum(words_per_ayah.values()),
                "ayahs": len(words_per_ayah),
                "stems": stems,
                "roots": len(roots),
                "lemmas": len(lemmas),
            },
        },
        # ترتيب ثابت: سورة ثم آية ثم كلمة ثم مقطع — يجعل البناء حتميًا
        "segments": [
            [
                s["surah"],
                s["ayah"],
                s["word"],
                s["segment"],
                s["form_bw"],
                s["tag"],
                s["features"],
                s["pos"],
                s["lemma_ar"],
                s["lemma_index"],
                s["root_ar"],
                s["root_key"],
            ]
            for s in sorted(
                segments, key=lambda s: (s["surah"], s["ayah"], s["word"], s["segment"])
            )
        ],
        "source_words_per_ayah": [
            [s, a, words_per_ayah[(s, a)]] for (s, a) in sorted(words_per_ayah)
        ],
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    # mtime=0 حتى يكون الملف الناتج متطابقًا بايتيًا عند إعادة البناء
    with gzip.GzipFile(OUT_PATH, "wb", mtime=0) as f:
        f.write(payload.encode("utf-8"))

    print("تم بناء حزمة الصرف:", OUT_PATH)
    print(
        f"  المقاطع: {len(segments):,} | الكلمات: {sum(words_per_ayah.values()):,} | "
        f"الجذوع: {stems:,}"
    )
    print(f"  الجذور: {len(roots):,} | الأصول (lemmas): {len(lemmas):,}")
    print(f"  الحجم: {OUT_PATH.stat().st_size:,} بايت")
    print("  بصمة الحزمة:", sha256_file(OUT_PATH)[:32])


if __name__ == "__main__":
    main()
