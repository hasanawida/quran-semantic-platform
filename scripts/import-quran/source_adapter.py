"""إطار محوّلات المصادر الصرفية — ليصير إدخال شاهد ثانٍ عملًا صغيرًا.

المشكلة التي يحلّها: كل ما تحتاجه المنصة من مصدر صرفي جديد هو حزمة
بالبنية القياسية. بدل أن يُكتب محوّل كامل من الصفر لكل مصدر، يُكتب
**دالة تفكيك سطر واحدة** ويتولى الإطار الباقي: التحقق البنيوي، والمقابلة
مع نص الإصدار، وحساب البصمات، والكتابة الحتمية.

**الضوابط مفروضة في الإطار لا في المحوّل:**

  1. **لا حزمة بلا رخصة معلنة** — `license` حقل إلزامي يرفض الفراغ.
  2. **لا حزمة بلا بصمة ملف مصدري** — تُحسب هنا لا تُمرَّر.
  3. **مجموعة الآيات يجب أن تطابق نص الإصدار تمامًا** — لا زيادة ولا نقص.
  4. **تسلسل الكلمات والمقاطع بلا فجوات** — الفجوة خلل لا يُمرَّر.
  5. **كل جذر يعطي مفتاحًا قانونيًا غير فارغ** — وإلا توقف البناء.
  6. **التصريح بالجذور يطابق البيانات** — مصدر يُعلن أنه يشهد على
     الجذور ولا يُنتجها (أو العكس) يوقف البناء لا يمرّ بتحذير.
  7. **البناء حتمي** — نفس المدخلات تعطي نفس البايتات (mtime=0).

المحوّل يقدّم: قارئًا يعطي `SourceSegment` لكل مقطع، وبيانات وصفية.
ما لا يعرفه المصدر يُترك `None` — لا يُخمَّن ولا يُملأ بقيمة افتراضية.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
from app.utils.arabic import normalize_root_input, tokenize_ayah  # noqa: E402

EXPECTED_SURAHS = 114
EXPECTED_AYAHS = 6236


@dataclass(frozen=True, slots=True)
class SourceSegment:
    """مقطع صرفي واحد كما يقرؤه المحوّل من مصدره.

    `features` تُحفظ **حرفيًا كما وردت** ولا تُعاد صياغتها: كثير من
    الرخص تشترط عدم تعديل الملف، والفهرسة تُشتق منها لاحقًا في التطبيق."""

    surah: int
    ayah: int
    word: int
    segment: int
    form: str
    tag: str
    features: str
    pos: str | None = None
    lemma: str | None = None
    lemma_index: int | None = None
    root: str | None = None


@dataclass(frozen=True, slots=True)
class SourceMeta:
    """بطاقة المصدر. كل حقل هنا يظهر في بيان الأصول العام."""

    source_code: str
    name: str
    url: str
    source_version: str
    license: str
    notice: str
    provides_roots: bool
    """أيشهد هذا المصدر على **الجذور** أم على التقطيع والوسم فقط؟

    لا قيمة افتراضية لهذا الحقل عمدًا: كاتب المحوّل يُلزَم بالإجابة.
    وسببه واقعة بعينها — أقوى المرشحين لشاهد ثانٍ (MASAQ) مدونة بشرية
    كاملة التغطية **بلا حقل جذر**. إدخالها بلا هذا التصريح يجعل الواجهة
    توهم باتفاق على الجذور لا وجود له."""


class AdapterError(SystemExit):
    """خطأ يوقف البناء. الوقوف أسلم من إنتاج حزمة مشكوك فيها."""


def _load_text_ayahs(text_bundle: Path) -> dict[tuple[int, int], str]:
    with gzip.open(text_bundle, "rt", encoding="utf-8") as handle:
        bundle = json.load(handle)
    return {(s, a): t for s, a, t in bundle["ayahs"]}


def _validate_meta(meta: SourceMeta) -> None:
    for field in ("source_code", "name", "url", "source_version", "license"):
        if not str(getattr(meta, field, "")).strip():
            raise AdapterError(
                f"بطاقة المصدر ناقصة: «{field}» مطلوب. "
                "لا تُبنى حزمة بلا رخصة معلنة ولا مصدر معروف."
            )


def _validate_structure(
    segments: list[SourceSegment], texts: dict[tuple[int, int], str]
) -> dict[tuple[int, int], int]:
    by_word: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    words_per_ayah: dict[tuple[int, int], set[int]] = defaultdict(set)

    for segment in segments:
        by_word[(segment.surah, segment.ayah, segment.word)].append(segment.segment)
        words_per_ayah[(segment.surah, segment.ayah)].add(segment.word)

    for position, numbers in by_word.items():
        if sorted(numbers) != list(range(1, len(numbers) + 1)):
            raise AdapterError(
                f"تسلسل مقاطع غير صحيح في {position[0]}:{position[1]}:{position[2]}"
            )

    counts: dict[tuple[int, int], int] = {}
    for key, words in words_per_ayah.items():
        if words != set(range(1, len(words) + 1)):
            raise AdapterError(f"تسلسل كلمات غير صحيح في {key[0]}:{key[1]}")
        counts[key] = len(words)

    missing = set(texts) - set(counts)
    extra = set(counts) - set(texts)
    if missing or extra:
        raise AdapterError(
            f"عدم تطابق الآيات مع نص الإصدار: ناقص {len(missing)}، زائد {len(extra)}"
        )
    if len({s for s, _ in counts}) != EXPECTED_SURAHS:
        raise AdapterError("عدد السور لا يطابق المصحف")
    if len(counts) != EXPECTED_AYAHS:
        raise AdapterError(f"عدد الآيات {len(counts)} ≠ {EXPECTED_AYAHS}")
    return counts


def build_bundle(
    *,
    meta: SourceMeta,
    reader: Callable[[], Iterable[SourceSegment]],
    source_files: list[Path],
    out_path: Path,
    text_bundle: Path | None = None,
) -> dict:
    """يبني حزمة مصدر صرفي بالبنية القياسية بعد التحقق الكامل.

    يُرجع تقريرًا بالأعداد ونسبة المحاذاة مع نص الإصدار."""
    _validate_meta(meta)
    for path in source_files:
        if not path.exists():
            raise AdapterError(f"ملف مصدر مفقود: {path}")

    text_bundle = text_bundle or (
        REPO_ROOT / "apps" / "api" / "data" / "quran_bundle.json.gz"
    )
    texts = _load_text_ayahs(text_bundle)

    segments = list(reader())
    if not segments:
        raise AdapterError("المحوّل لم يُنتج أي مقطع")

    # تناقض التصريح يُفحص **قبل** التغطية: خطأٌ في وصف ما يشهد به المصدر
    # أعمق من نقص في تغطيته، ولو تأخّر لحجبته رسالةُ التغطية.
    has_root = any(segment.root for segment in segments)
    if meta.provides_roots and not has_root:
        raise AdapterError(
            "المصدر أُعلن شاهدًا على الجذور ولم يُنتج جذرًا واحدًا. "
            "إما أن قراءة حقل الجذر فاشلة، وإما أن الإعلان خاطئ."
        )
    if not meta.provides_roots and has_root:
        raise AdapterError(
            "المصدر أُعلن بلا جذور ثم أنتج جذورًا. التصريح يجب أن يطابق "
            "البيانات، وإلا خُدع من يقرأ بيان الأصول."
        )

    words_per_ayah = _validate_structure(segments, texts)

    rows = []
    roots: set[str] = set()
    for segment in sorted(
        segments, key=lambda s: (s.surah, s.ayah, s.word, s.segment)
    ):
        root_key = None
        if segment.root:
            root_key = normalize_root_input(segment.root)
            if not root_key:
                raise AdapterError(
                    f"جذر يعطي مفتاحًا فارغًا: {segment.root!r} في "
                    f"{segment.surah}:{segment.ayah}:{segment.word}"
                )
            roots.add(root_key)
        rows.append(
            [
                segment.surah,
                segment.ayah,
                segment.word,
                segment.segment,
                segment.form,
                segment.tag,
                segment.features,
                segment.pos,
                segment.lemma,
                segment.lemma_index,
                segment.root,
                root_key,
            ]
        )

    aligned = sum(
        1
        for key, count in words_per_ayah.items()
        if count == len(tokenize_ayah(texts[key]))
    )

    bundle = {
        "meta": {
            "source_code": meta.source_code,
            "name": meta.name,
            "url": meta.url,
            "source_version": meta.source_version,
            "license": meta.license,
            "review_status": "imported",
            "confidence": "machine_only",
            "notice": meta.notice,
            # يُنقل إلى بيان الأصول: شاهدٌ على الجذور أم على الوسم فقط.
            "provides_roots": meta.provides_roots,
            "witnesses": (
                ["morphology", "roots"] if meta.provides_roots else ["morphology"]
            ),
            "file_sha256": hashlib.sha256(
                b"".join(path.read_bytes() for path in sorted(source_files))
            ).hexdigest(),
            "counts": {
                "segments": len(rows),
                "words": sum(words_per_ayah.values()),
                "ayahs": len(words_per_ayah),
                "roots": len(roots),
            },
        },
        "segments": rows,
        "source_words_per_ayah": [
            [s, a, words_per_ayah[(s, a)]] for (s, a) in sorted(words_per_ayah)
        ],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    # mtime=0 حتى يكون الملف متطابقًا بايتيًا عند إعادة البناء
    with gzip.GzipFile(out_path, "wb", mtime=0) as handle:
        handle.write(payload.encode("utf-8"))

    return {
        "out_path": str(out_path),
        "segments": len(rows),
        "words": sum(words_per_ayah.values()),
        "roots": len(roots),
        "aligned_ayahs": aligned,
        "alignment_ratio": round(aligned / len(words_per_ayah), 6),
        "sha256": hashlib.sha256(out_path.read_bytes()).hexdigest(),
    }
