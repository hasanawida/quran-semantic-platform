"""بناء حزمة بيانات قرآنية موثقة من مصادر خارجية معتمدة.

المصادر:
  - نص المصحف (رواية حفص، رسم عثماني): مشروع تنزيل https://tanzil.net
  - البيانات الوصفية للسور: مشروع تنزيل (quran-data.xml)
  - الجذور والصرف: المدونة القرآنية بجامعة ليدز https://corpus.quran.com
    (رخصة GNU — يلزم ذكر المصدر ورابطه وعدم تعديل الملف الأصلي)

المخرج: apps/api/data/quran_bundle.json.gz — حزمة تحمل بصمات مصادرها
وحالة علمية «مستورد» (لم تعتمد بمراجعة المنصة بعد).

لا يكتب هذا السكربت أي نص قرآني يدويًا؛ كل المحتوى من الملفات المصدرية،
والتحقق بنيوي: عدد السور والآيات وتسلسلها وتطابق المصدرين.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
OUT_PATH = REPO_ROOT / "apps" / "api" / "data" / "quran_bundle.json.gz"

sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
from app.utils.arabic import (  # noqa: E402
    count_word_tokens,
    normalize_arabic_search,
    normalize_root_input,
    tokenize_ayah,
)
from app.utils.buckwalter import to_arabic  # noqa: E402

TEXT_FILE = RAW_DIR / "quran-uthmani.txt"
META_FILE = RAW_DIR / "quran-data.xml"
MORPH_FILE = RAW_DIR / "quranic-corpus-morphology-0.4.txt"

EXPECTED_SURAHS = 114
EXPECTED_AYAHS = 6236  # العد الكوفي


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_tanzil_text() -> dict[tuple[int, int], str]:
    ayahs: dict[tuple[int, int], str] = {}
    for line in TEXT_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip("﻿").rstrip("\n")
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        surah, ayah, text = int(parts[0]), int(parts[1]), parts[2]
        if not text:
            raise ValueError(f"آية فارغة في {surah}:{ayah}")
        ayahs[(surah, ayah)] = text
    return ayahs


def separate_basmala(
    ayahs: dict[tuple[int, int], str],
) -> tuple[dict[int, str], list[int]]:
    """يفصل البسملة المدمجة في أول كل سورة ويعيدها بيانًا للسورة.

    ملف تنزيل المستعمل يدمج البسملة داخل نص الآية الأولى من كل سورة عدا
    الفاتحة (البسملة فيها آية مستقلة) وبراءة (لا بسملة فيها). إبقاؤها مدمجة
    يجعل «2:1» تُعرض «بسم الله… الٓمٓ» وهو مخالف للعد الكوفي المعلن، ويزيح
    ترقيم الكلمات أربعًا فتفشل محاذاة التحليل الصرفي.

    الفصل **نقل حرفي لا تعديل**: تُقتطع بادئة مطابقة بايتيًا لصورة البسملة
    كما وردت في الملف نفسه (بصورتيها: بِسْمِ وبِّسْمِ)، وتُحفظ نصًا للسورة.
    """
    # المطابقة على الصورة المطبَّعة (بسم الله الرحمن الرحيم) لأن الملف يكتب
    # البسملة بصورتين إملائيتين (بِسْمِ / بِّسْمِ)، والقطع بعدها **بالمواضع**
    # فتُحفظ بايتات كل سورة كما وردت بلا توحيد ولا تعديل.
    canonical_norm = normalize_arabic_search(ayahs[(1, 1)])
    basmala_word_count = len(tokenize_ayah(ayahs[(1, 1)]))

    basmala_by_surah: dict[int, str] = {}
    separated: list[int] = []
    for surah in range(2, EXPECTED_SURAHS + 1):
        text = ayahs[(surah, 1)]
        tokens = tokenize_ayah(text)
        if len(tokens) <= basmala_word_count:
            if surah != 9:
                raise SystemExit(f"سورة {surah}: الآية الأولى أقصر من البسملة")
            continue
        prefix = text[: tokens[basmala_word_count - 1][1]]
        if normalize_arabic_search(prefix) != canonical_norm:
            if surah != 9:
                raise SystemExit(
                    f"سورة {surah}: الآية الأولى لا تبدأ ببسملة — "
                    "توقف البناء بدل التخمين"
                )
            continue
        remainder = text[tokens[basmala_word_count][0] :]
        if not remainder.strip():
            raise SystemExit(f"سورة {surah}: لا يبقى نص بعد فصل البسملة")
        ayahs[(surah, 1)] = remainder
        basmala_by_surah[surah] = prefix
        separated.append(surah)

    if len(separated) != EXPECTED_SURAHS - 2:  # عدا الفاتحة وبراءة
        raise SystemExit(
            f"عدد السور المفصولة {len(separated)} ≠ {EXPECTED_SURAHS - 2}"
        )
    if 9 in basmala_by_surah:
        raise SystemExit("سورة براءة لا بسملة فيها")
    return basmala_by_surah, separated


def parse_tanzil_metadata() -> list[dict]:
    root = ET.fromstring(META_FILE.read_text(encoding="utf-8"))
    surahs = []
    for sura in root.iter("sura"):
        surahs.append(
            {
                "number": int(sura.attrib["index"]),
                "arabic_name": sura.attrib["name"],
                "ayah_count": int(sura.attrib["ayas"]),
                "revelation_type": sura.attrib.get("type", ""),
            }
        )
    return surahs


def parse_morphology() -> tuple[dict[str, dict], dict[tuple[int, int], int]]:
    """يعيد: جذور {مفتاح: {display, occurrences}} وعدد كلمات كل آية وفق المدونة."""
    roots: dict[str, dict] = {}
    words_per_ayah: dict[tuple[int, int], int] = {}
    for line in MORPH_FILE.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or line.startswith("LOCATION"):
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        location, _form, _tag, features = parts
        loc = location.strip("()").split(":")
        surah, ayah, word = int(loc[0]), int(loc[1]), int(loc[2])
        key = (surah, ayah)
        words_per_ayah[key] = max(words_per_ayah.get(key, 0), word)
        root_bw = None
        for feature in features.split("|"):
            if feature.startswith("ROOT:"):
                root_bw = feature[5:]
                break
        if not root_bw:
            continue
        root_ar = to_arabic(root_bw)
        normalized = normalize_root_input(root_ar)
        if not normalized:
            raise ValueError(f"جذر فارغ بعد التطبيع: {root_bw!r} في {location}")
        entry = roots.setdefault(
            normalized,
            {"display": " ".join(normalized), "occurrences": []},
        )
        occ = (surah, ayah, word)
        if not entry["occurrences"] or entry["occurrences"][-1] != occ:
            entry["occurrences"].append(occ)
    return roots, words_per_ayah


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for path in (TEXT_FILE, META_FILE, MORPH_FILE):
        if not path.exists():
            raise SystemExit(f"ملف مصدر مفقود: {path}")

    ayahs = parse_tanzil_text()
    surahs = parse_tanzil_metadata()

    # التحقق البنيوي — نص تنزيل
    surah_numbers = sorted({s for s, _ in ayahs})
    if len(surah_numbers) != EXPECTED_SURAHS:
        raise SystemExit(f"عدد السور {len(surah_numbers)} ≠ {EXPECTED_SURAHS}")
    if len(ayahs) != EXPECTED_AYAHS:
        raise SystemExit(f"عدد الآيات {len(ayahs)} ≠ {EXPECTED_AYAHS}")

    # التحقق المتقاطع: البيانات الوصفية مقابل النص
    if len(surahs) != EXPECTED_SURAHS:
        raise SystemExit("عدد السور في البيانات الوصفية غير صحيح")
    for meta in surahs:
        number, count = meta["number"], meta["ayah_count"]
        text_count = sum(1 for (s, _) in ayahs if s == number)
        if text_count != count:
            raise SystemExit(
                f"سورة {number}: عدد الآيات في النص {text_count} ≠ الوصفية {count}"
            )
        for i in range(1, count + 1):
            if (number, i) not in ayahs:
                raise SystemExit(f"آية مفقودة: {number}:{i}")

    # فصل البسملة المدمجة — بعد التحقق من العدد وقبل الترميز والمحاذاة
    basmala_by_surah, separated = separate_basmala(ayahs)
    for meta in surahs:
        meta["basmala"] = basmala_by_surah.get(meta["number"])

    roots, words_per_ayah = parse_morphology()

    # التحقق المتقاطع: المدونة القرآنية مقابل النص
    morph_ayahs = set(words_per_ayah)
    text_ayahs = set(ayahs)
    if morph_ayahs != text_ayahs:
        missing = len(text_ayahs - morph_ayahs)
        extra = len(morph_ayahs - text_ayahs)
        raise SystemExit(f"عدم تطابق الآيات: ناقص {missing}، زائد {extra}")

    # محاذاة الكلمات: تمييز آمن فقط حيث يتطابق العد
    safe_highlight = {
        key
        for key, morph_words in words_per_ayah.items()
        if morph_words == count_word_tokens(ayahs[key])
    }
    alignment_ratio = len(safe_highlight) / len(ayahs)

    bundle = {
        "meta": {
            "version_code": "tanzil-uthmani-qac04",
            "title": "نص تنزيل العثماني + جذور المدونة القرآنية",
            "riwayah": "حفص عن عاصم",
            "script_type": "عثماني",
            "counting_system": "الكوفي",
            "review_status": "imported",
            "confidence": "machine_only",
            "notice": "بيانات مستوردة من مصادر خارجية موثقة، لم تخضع بعد لمراجعة المنصة المزدوجة.",
            "basmala_policy": {
                "mode": "separated",
                "description": (
                    "ملف المصدر يدمج البسملة في الآية الأولى من كل سورة عدا "
                    "الفاتحة وبراءة؛ فُصلت نقلًا حرفيًا وحُفظت نصًا للسورة "
                    "ليطابق العرض العد الكوفي."
                ),
                "separated_surahs": len(separated),
                "excluded": {"1": "البسملة آية مستقلة", "9": "لا بسملة"},
            },
            "sources": [
                {
                    "name": "Tanzil Project",
                    "url": "https://tanzil.net",
                    "files": {
                        "quran-uthmani.txt": sha256_file(TEXT_FILE),
                        "quran-data.xml": sha256_file(META_FILE),
                    },
                    "license": "Tanzil terms: النص دون تعديل مع الإسناد",
                },
                {
                    "name": "Quranic Arabic Corpus (Kais Dukes, University of Leeds)",
                    "url": "https://corpus.quran.com",
                    "files": {
                        "quranic-corpus-morphology-0.4.txt": sha256_file(MORPH_FILE),
                    },
                    "license": "GNU GPL — الإسناد ورابط المصدر وعدم تعديل الملف",
                },
            ],
            "counts": {
                "surahs": len(surahs),
                "ayahs": len(ayahs),
                "roots": len(roots),
                "word_alignment_ratio": round(alignment_ratio, 6),
            },
        },
        "surahs": surahs,
        "ayahs": [[s, a, text] for (s, a), text in sorted(ayahs.items())],
        "safe_highlight": sorted([s, a] for (s, a) in safe_highlight),
        "roots": roots,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    with gzip.open(OUT_PATH, "wt", encoding="utf-8") as f:
        f.write(payload)

    print("تم بناء الحزمة:", OUT_PATH)
    print(f"  السور: {len(surahs)} | الآيات: {len(ayahs)} | الجذور: {len(roots)}")
    print(f"  محاذاة الكلمات الآمنة للتمييز: {alignment_ratio:.2%}")
    print(f"  الحجم: {OUT_PATH.stat().st_size:,} بايت")
    print("  بصمة الحزمة:", hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()[:32])


if __name__ == "__main__":
    main()
