#!/usr/bin/env python
"""يولّد شجرة البيانات الثابتة للموقع العام من الحزمتين الموثقتين.

**الخطوط الحمراء محروسة في هذا الملف نفسه:**

1. النص القرآني يُنسخ **حرفيًا** من `quran_bundle.json.gz` سلسلةً كما هي.
   لا يُبنى من كلماته، ولا يُقصّ، ولا يُطبَّع، ولا يمرّ على أي دالة.
2. التطبيع للبحث فقط: مخرجه ملف منفصل (`norm.json`) لا يُعرض قط، ويُحسب
   بـ`normalize_arabic_search` نفسها المستعملة في البذر — مصدر حقيقة واحد.
3. كل مخرَج يحمل مصدره وحالة مراجعته وبصمته: `manifest.json` يحمل بصمة
   كل ملف مُخرَج وبصمات الملفات المصدرية كما وردت في `meta` الحزمة،
   وتاريخ اللقطة. و`meta.json` و`provenance.json` يُقرآن في كل شاشة.

التشغيل:
    apps/api/.venv/Scripts/python.exe scripts/export-static/build_data.py
"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "apps" / "api"))

import app.utils.arabic as ar  # noqa: E402
from app.content.methodology import methodology_payload  # noqa: E402
from app.utils.arabic import (  # noqa: E402
    normalize_arabic_search,
    normalize_root_input,
    normalize_search_skeleton,
    normalize_surah_name,
    tokenize_ayah,
)
from app.utils.morphology_tags import (  # noqa: E402
    FEATURE_LABELS,
    FEATURE_TITLES,
    POS_LABELS_AR,
    parse_features,
)

DATA = REPO / "apps" / "api" / "data"
OUT = REPO / "apps" / "web" / "public" / "data" / "v1"

# سقف الحجم الخام لشجرة البيانات. تجاوزه خطأ بناء لا مفاجأة إنتاج:
# المقيس اليوم 13,796,442 بايتًا في 240 ملفًا.
RAW_BUDGET = 30 * 1024 * 1024

files: dict[str, str] = {}


def write(name: str, payload) -> None:
    """يكتب ملفًا ويسجّل بصمته. `.json` حصرًا وخارج `apps/web/app`."""
    assert name.endswith(".json"), name
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    path.write_bytes(blob)
    files[name] = hashlib.sha256(blob).hexdigest()


def load(name: str) -> tuple[dict, str]:
    path = DATA / name
    if not path.exists():
        raise SystemExit(f"الحزمة غير موجودة: {path}")
    raw = path.read_bytes()
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle), hashlib.sha256(raw).hexdigest()


def codepoints(pattern) -> list[int]:
    """يستخرج نطاق محارف من تعبير نمطي — فلا يُكتب جدول عربي يدويًا."""
    return [cp for cp in range(0x0600, 0x0900) if pattern.fullmatch(chr(cp))]


def main() -> None:
    quran, quran_sha = load("quran_bundle.json.gz")
    morph, morph_sha = load("morphology_qac04.json.gz")
    qmeta, mmeta = quran["meta"], morph["meta"]

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # ---------- 1) ترتيب الآيات القانوني ----------
    ayahs = quran["ayahs"]  # [[سورة، آية، نص]، …] بترتيب المصحف
    surahs = quran["surahs"]
    index = {(s, a): i for i, (s, a, _t) in enumerate(ayahs)}

    assert len(ayahs) == qmeta["counts"]["ayahs"] == 6236, "عدد الآيات"
    assert len(surahs) == qmeta["counts"]["surahs"] == 114, "عدد السور"
    assert sum(s["ayah_count"] for s in surahs) == len(ayahs), "مجموع عدّ السور"

    offsets: dict[int, int] = {}
    cursor = 0
    for surah in surahs:
        offsets[surah["number"]] = cursor
        for step in range(surah["ayah_count"]):
            got = ayahs[cursor + step]
            assert got[0] == surah["number"] and got[1] == step + 1, (
                f"ترتيب الآيات مكسور عند {got[0]}:{got[1]}"
            )
        cursor += surah["ayah_count"]
    assert cursor == len(ayahs)

    # ---------- 2) فهرس السور (مع مفتاح اسم مطبَّع محسوبًا هنا) ----------
    write(
        "surahs.json",
        {
            "offsets": [offsets[s["number"]] for s in surahs],
            "surahs": [
                {
                    "n": s["number"],
                    "name": s["arabic_name"],
                    "rev": s["revelation_type"],
                    "count": s["ayah_count"],
                    # البسملة بيان للسورة لا آية — تُنسخ حرفيًا كما في الحزمة
                    "basmala": s.get("basmala"),
                    # مفتاح مطابقة الاسم — للبحث فقط، لا يُعرض أبدًا.
                    # يُحسب هنا بايثونًا حفظًا للقرار المعلن في
                    # services/quran.py:42 (تنفيذ واحد لتطبيع الأسماء).
                    "key": normalize_surah_name(s["arabic_name"]),
                }
                for s in surahs
            ],
        },
    )

    # ---------- 3) نص المصحف: ملف لكل سورة، منسوخًا حرفيًا ----------
    for surah in surahs:
        start = offsets[surah["number"]]
        chunk = ayahs[start : start + surah["ayah_count"]]
        # `text` هي السلسلة كما وردت في الحزمة — لا تمرّ على أي معالجة
        write(f"text/s{surah['number']}.json", [text for _s, _a, text in chunk])

    # ---------- 4) مفاتيح البحث: تُحسب هنا ولا تُحسب في المتصفح قط ----------
    norms = [normalize_arabic_search(text) for _s, _a, text in ayahs]
    write("norm.json", norms)

    # **عقد التمييز**: تقسيم السطر المطبَّع على الفراغ يوافق ترميز المنصة
    # كلمةً بكلمة. مقيس: صفر اختلاف على 6236 آية و77,433 رمزًا. لولاه
    # لَوقع التمييز على كلمة غير التي طابقت — وهو فشل صامت.
    for position, (_s, _a, text) in enumerate(ayahs):
        tokens = tokenize_ayah(text)
        parts = [part for part in norms[position].split(" ") if part]
        assert len(parts) == len(tokens), f"محاذاة الكلمات في {_s}:{_a}"
        for (_st, _en, word), part in zip(tokens, parts):
            assert normalize_arabic_search(word) == part, f"كلمة في {_s}:{_a}"

    # ---------- 5) الجذور: مراجع لا نصوص ----------
    roots: dict[str, dict] = {}
    for key, entry in quran["roots"].items():
        grouped: dict[int, set[int]] = {}
        for surah_number, ayah_number, word in entry["occurrences"]:
            position = index.get((surah_number, ayah_number))
            assert position is not None, f"موضع خارج المصحف: {key}"
            grouped.setdefault(position, set()).add(word)
        roots[key] = {
            "d": entry["display"],
            # [فهرس الآية، [أرقام الكلمات]] — والنص يأتي من ملف السورة
            "o": [[i, sorted(w)] for i, w in sorted(grouped.items())],
        }
    assert len(roots) == qmeta["counts"]["roots"] == 1642
    write("roots.json", {"roots": roots})

    # ---------- 5-ب) هيكل المواد المعجمية: موضعٌ بلا متن ----------
    # **قرارٌ مقصود:** تُفتح لكل جذرٍ قرآنيّ **مادةٌ معجمية** بموضعها
    # البنيوي `lexicon_entry(root)` — **ولا يُدخَل متنُ أيّ معجم**.
    #
    # لماذا: فحصُ مصادر لسان العرب (docs/audits/LISAN_AL_ARAB_SOURCING.md)
    # انتهى إلى أن كل النسخ الرقمية المتداولة **نصٌّ واحد من طبعةٍ لم
    # يُسمِّها أحد**. و§10 تشترط «الكتاب + الطبعة + الملف + الترخيص +
    # البصمة»، فلا يجتازها شيء منها.
    #
    # والمواد **تُشتقّ من جذورنا نحن** لا من قائمةٍ خارجية: عندنا ١٦٤٢
    # جذرًا من مصدرٍ مرخَّصٍ لنا أصلًا، فلا مصدر جديد ولا سؤال حقوقيّ.
    # ولذلك لا يُكتب هنا سجلٌّ بـ١٦٤٢ صفًّا متطابقًا — يُكتب **السجلّ
    # والسياسة** وحدهما، وتُشتقّ المادة من الجذر في العرض.
    # **حُذف معجم لِين بقرار المالك (2026-07-29):** كان الشاهد الوحيد
    # المُدخَل، لكنه إنجليزيّ — ومنصةٌ عربية لا يسدّ فيها الإنجليزيُّ
    # مسدَّ المعنى العربي. والبديل العربي غير موجود بعد (انظر أدناه).
    write(
        "lexicon.json",
        {
            "state": "no_text",
            "scheme": "lexicon_entry",
            "entry_count": len(roots),
            "with_text": [],
            "lane": None,
            "reason": (
                "المواد مفتوحةٌ بمواضعها، ومتونها غير مُدخَلة. ولم يجتز "
                "أيُّ معجمٍ عربيٍّ رقميّ شرطَ «الكتاب + الطبعة + الملف + "
                "الترخيص + البصمة»: المتداول منها نصٌّ واحد من طبعةٍ لم "
                "يُسمِّها أحد. ومصوَّرةُ مفردات الراغب (١٣٢٤هـ) حرّةٌ فعلًا، "
                "لكن طبقة نصِّها المستخرَجة آليًّا غيرُ صالحة — فإدخالها "
                "نسخٌ يدويّ لا استيراد. ولا يُسدّ الفراغ بمتنٍ مجهول الطبعة "
                "ولا بترجمةٍ آلية."
            ),
            "audit": "docs/audits/LISAN_AL_ARAB_SOURCING.md",
            # سجلّ المصادر بحقيقة حالها — مقروءًا من مواقع أصحابها
            "sources": [
                {
                    "name": "معجم لِين — رقمنة Perseus بصيغة TEI",
                    "url": (
                        "https://www.perseus.tufts.edu/hopper/opensource/"
                        "downloads/texts/hopper-texts-Arabic.tar.gz"
                    ),
                    "licence": (
                        "إتاحة حرّة بثلاثة شروط منصوصة داخل الملف نفسه. "
                        "والطبعة مسمّاة: London: Williams and Norgate, 1863."
                    ),
                    "status": "withdrawn",
                    "note": (
                        "أُدخل ثم سُحب بقرار المالك: اجتاز §10 كاملًا "
                        "وغطّى ١٢٩٦ جذرًا بصفحاتٍ حقيقية، لكن تعريفاته "
                        "إنجليزية — ومنصةٌ عربية لا يقوم فيها الشاهد "
                        "الإنجليزي مقامَ المعنى العربي. وهو باقٍ في تاريخ "
                        "المستودع إن أُريد رجوعه."
                    ),
                },
                {
                    "name": "لسان العرب — ويكي مصدر",
                    "url": "https://ar.wikisource.org/wiki/لسان_العرب",
                    "licence": "CC BY-SA 4.0 — سليمة ومتحقَّق منها",
                    "status": "blocked",
                    "note": (
                        "الرخصة ليست المشكلة: الطبعة غير مذكورة في أيّ "
                        "موضع، والترتيب ليس ترتيب ابن منظور، وأبواب "
                        "د ذ ز ج خ مفقودة، والتغطية ٦٧٫٥٪."
                    ),
                },
                {
                    "name": "لسان العرب — مجموعات GitHub وHugging Face",
                    "url": "https://huggingface.co/datasets/enver/lisan_al_alab",
                    "licence": "معدومة أو لا تغطّي البيانات",
                    "status": "blocked",
                    "note": (
                        "نصٌّ واحد تنتشر نسخُه ببصمة «@<الجذر>:» و«<ص:NNN>». "
                        "وأحدها يصرّح بنفسه بأنه من المكتبة الشاملة."
                    ),
                },
                {
                    "name": (
                        "OpenITI — المفردات للراغب · غريب القرآن لابن قتيبة · "
                        "مقاييس اللغة لابن فارس · عمدة الحفاظ للسمين"
                    ),
                    "url": "https://openiti.org/documentation/",
                    "licence": (
                        "لا رخصة معلَنة: المستودعات الأربعة `license: null`، "
                        "وتوثيق OpenITI يقول «can be used free of charge, but "
                        "users pledge to help develop the corpus» ولا يسمّي "
                        "رخصةً، ويصف نفسه «a work in progress»."
                    ),
                    "status": "blocked",
                    "note": (
                        "الأربعة كلها طبعاتٌ محقَّقة معاصرة، وترويساتها "
                        "تقولها بنفسها: مقاييس اللغة — عبد السلام هارون "
                        "(ت١٩٨٨)، دار الجيل، سنة ١٤٢٠هـ/١٩٩٩م؛ والمفردات — "
                        "كيلاني، دار المعرفة؛ وغريب القرآن — أحمد صقر، دار "
                        "الكتب العلمية — وترويسته تقول «لعلها مصورة عن "
                        "الطبعة المصرية»، أي إن OpenITI نفسها لا تجزم بالطبعة. "
                        "ومصادرها الرقمية الشاملة والجامع الكبير. وOpenITI "
                        "مشروعٌ علميّ محترم، لكنه لا يملك أن يمنح حقوقًا في "
                        "تحقيقٍ ليس له — ولا طبعةَ قبل ١٩٢٩ لأيٍّ من الثلاثة."
                    ),
                },
                {
                    "name": (
                        "مفردات الراغب — المطبعة الميمنية ١٣٢٤هـ [١٩٠٧م] · "
                        "مصوَّرة مكتبة الإسكندرية"
                    ),
                    "url": "https://archive.org/details/AAlexandrina-152403",
                    "licence": (
                        "ملكية عامة — نصًّا وترقيمًا معًا (طُبع قبل ١٩٢٩)، "
                        "والمصوَّرة الأمينة لعملٍ حرٍّ لا تُنشئ حقًّا جديدًا."
                    ),
                    "status": "blocked_by_quality",
                    "note": (
                        "المرشَّح الأقرب، والعائق ليس حقوقيًّا بل تقنيّ. "
                        "المصوَّرة موجودة وحرّة، وفيها طبقة نصٍّ مستخرَجة "
                        "آليًّا (‏١٫٣٨ م.ب) — لكنها مدمَّرة: ثلثُها حروفٌ "
                        "لاتينية مشوَّشة، و«باب الراء وما يتصل بها» تخرج "
                        "«باب الژایوناتتصل». فليست نصًّا يُراجَع بل نصًّا "
                        "يُعاد كتابته، وذلك نسخٌ يدويّ لأكثر من خمسمئة صفحة "
                        "من نصٍّ دينيّ لا استيراد. والمخرج الوحيد تعرّفٌ "
                        "ضوئيّ حديث على الصور ثم مراجعة بشرية (§24٫6)."
                    ),
                },
            ],
        },
    )

    # ---------- 6) الصرف ----------
    segments = morph["segments"]
    # سلسلة السمات تحدّد وحدها كل ما عداها — مقيس: 12,405 سلسلة مميزة
    # وصفر تعارض في tag/pos/lemma/lemma_index/root_ar/root_key.
    by_features: dict[str, tuple] = {}
    for seg in segments:
        value = (seg[5], seg[7], seg[8], seg[9], seg[10], seg[11])
        existing = by_features.setdefault(seg[6], value)
        assert existing == value, f"سمات غير دالّة: {seg[6]!r}"

    feature_list = sorted(by_features)
    feature_index = {f: i for i, f in enumerate(feature_list)}

    # القاموس: السلسلة **حرفيًا كما وردت** (شرط رخصة المدونة) ثم
    # الأبعاد المشتقة منها بـparse_features — فهرسة فوقها لا تعديل فيها.
    dims_keys = (
        "aspect", "verb_form", "voice", "mood", "person", "gender",
        "grammatical_number", "case_marking", "definiteness", "nominal_form",
    )
    write(
        "morph/dims.json",
        [
            [f, *by_features[f], *(parse_features(f)[k] for k in dims_keys)]
            for f in feature_list
        ],
    )

    resolved: list[list] = [[] for _ in ayahs]
    indexed: list[list] = [[] for _ in ayahs]
    for seg in segments:
        surah_number, ayah_number, word, number = seg[0], seg[1], seg[2], seg[3]
        position = index[(surah_number, ayah_number)]
        # [كلمة، مقطع، وسم، قسم، سمات حرفية، أصل، رقم الأصل، جذر المصدر]
        resolved[position].append(
            [word, number, seg[5], seg[7], seg[6], seg[8], seg[9], seg[10]]
        )
        indexed[position].append((word, number, feature_index[seg[6]]))

    stream: list[str] = []
    for entries in indexed:
        words: dict[int, list[int]] = {}
        for word, _number, feature in sorted(entries):
            words.setdefault(word, []).append(feature)
        stream.append(
            "|".join(",".join(str(f) for f in words[w]) for w in sorted(words))
        )
    write("morph/all.json", stream)

    for surah in surahs:
        start = offsets[surah["number"]]
        write(
            f"morph/s{surah['number']}.json",
            [sorted(rows) for rows in resolved[start : start + surah["ayah_count"]]],
        )

    # الشكلان يصفان المدونة نفسها — يُتحقَّق لا يُفترض
    for position, entries in enumerate(indexed):
        rebuilt: dict[int, list[int]] = {}
        for word, _number, feature in sorted(entries):
            rebuilt.setdefault(word, []).append(feature)
        assert stream[position] == "|".join(
            ",".join(str(f) for f in rebuilt[w]) for w in sorted(rebuilt)
        )
        assert len(entries) == len(resolved[position])

    # ---------- 6-ب) فهرس الكلمات: صورةٌ مطبَّعة ← مواضعها وتحليلها ----------
    # **لماذا فهرسٌ مستقل ولا يكفي `norm.json`:** البحث في نص الآيات يجد
    # الآياتِ التي فيها الكلمة، ولا يجمع للكلمة نفسها جذرَها ولمّتها وكلَّ
    # مواضعها. وجمعُها وقت العرض يلزمه تحميل ملفّ صرفِ كل سورةٍ ورد فيها
    # اللفظ — نحو ثلاثين ملفًّا للكلمة الشائعة. فيُحسب هنا مرةً واحدة.
    #
    # **والخط الأحمر قائم:** المفهرَس هو الصورة **المطبَّعة** (مفتاح بحث
    # لا نصّ عرض)، ويُخزَّن مع كل موضعٍ فهرسُ الآية ورقمُ الكلمة — ونصُّ
    # العرض يأتي من ملف السورة بمواضع الحروف كما في بقية الشاشات.
    #
    # ويُشرَّح بالحرف الأول ليكون تحميل البحث الواحد عشرات الكيلوبايتات
    # لا ميغابايتًا ونصفًا.
    # **ولا يُنسب تحليلٌ إلى كلمةٍ في آيةٍ لم يحاذِها المصدر.** ترقيمُ
    # المدونة للكلمات يخالف تقطيعنا في أربع آيات، فرقمُ الكلمة يزيح
    # فيها — ولو نُسب التحليل على علّاته لظهر «ٱللَّه» من جذر «سمع»
    # و«مِن» من جذر «علم». والموضع نفسه صحيح (الكلمة هناك فعلًا)،
    # فيبقى؛ ويسقط التحليل وحده ويُعلن سقوطُه.
    source_words = {(s, a): c for s, a, c in morph["source_words_per_ayah"]}
    linked = {
        (s, a): source_words.get((s, a)) == len(tokenize_ayah(text))
        for s, a, text in ayahs
    }

    seg_by_word: dict[tuple[int, int, int], list] = {}
    for seg in segments:
        seg_by_word.setdefault((seg[0], seg[1], seg[2]), []).append(seg)

    shards: dict[str, dict] = {}
    word_total = 0
    unlinked_words = 0
    for position, (surah_number, ayah_number, text) in enumerate(ayahs):
        aligned_here = linked[(surah_number, ayah_number)]
        for order, (_st, _en, word) in enumerate(tokenize_ayah(text), start=1):
            form = normalize_arabic_search(word)
            if not form:
                continue
            word_total += 1
            shard = shards.setdefault(
                form[0] if form[0].isalpha() else "_",
                {"roots": [], "lemmas": [], "forms": {}},
            )
            entry = shard["forms"].setdefault(form, {"n": 0, "a": {}, "o": []})
            entry["n"] += 1
            entry["o"] += [position, order]

            # الجذر واللمّة من المدونة بموضعهما، لا باستنتاج. وكلمةٌ لم
            # يحاذِها المصدر تبقى بلا تحليل — يُعلن ولا يُخمَّن.
            if not aligned_here:
                unlinked_words += 1
                continue
            for seg in seg_by_word.get((surah_number, ayah_number, order), ()):
                root_ar, lemma = seg[10], seg[8]
                if not root_ar and not lemma:
                    continue
                for table, value in (("roots", root_ar), ("lemmas", lemma)):
                    if value and value not in shard[table]:
                        shard[table].append(value)
                key = "{},{}".format(
                    shard["roots"].index(root_ar) if root_ar else -1,
                    shard["lemmas"].index(lemma) if lemma else -1,
                )
                entry["a"][key] = entry["a"].get(key, 0) + 1

    assert word_total == 77433, word_total
    assert sum(len(s["forms"]) for s in shards.values()) == 14691
    # مقيسٌ لا مقدَّر: أربع آيات غير محاذية، وكلماتها بلا تحليل
    assert sum(1 for v in linked.values() if not v) == 4
    assert unlinked_words == 50, unlinked_words

    # عقدٌ يُثبَت لا يُدَّعى: عدد المواضع = العدد المعلن، وكل موضعٍ يشير
    # إلى آيةٍ موجودة وإلى كلمةٍ داخل حدودها.
    for shard in shards.values():
        for form, entry in shard["forms"].items():
            assert len(entry["o"]) == entry["n"] * 2, form
            for i in range(0, len(entry["o"]), 2):
                at, order = entry["o"][i], entry["o"][i + 1]
                assert 0 <= at < len(ayahs), form
                assert 1 <= order <= len(tokenize_ayah(ayahs[at][2])), form

    for key, shard in shards.items():
        write(
            f"words/{ord(key):04x}.json",
            {
                "roots": shard["roots"],
                "lemmas": shard["lemmas"],
                # صورة: [عدد، {«جذر,لمّة»: عدد}، [فهرس آية، رقم كلمة، …]]
                "forms": {
                    form: [e["n"], e["a"], e["o"]]
                    for form, e in sorted(shard["forms"].items())
                },
            },
        )

    # ---------- 7) محاذاة المصدر بالنص (is_linked_to_token) ----------
    source_words = {(s, a): c for s, a, c in morph["source_words_per_ayah"]}
    aligned = [
        1 if source_words.get((s, a)) == len(tokenize_ayah(text)) else 0
        for s, a, text in ayahs
    ]
    write("aligned.json", aligned)

    # ---------- 8) مواصفة التطبيع — مولَّدة من arabic.py لا مكتوبة ----------
    write(
        "normspec.json",
        {
            "drop": codepoints(ar.DIACRITICS),
            "combiningHamza": codepoints(ar.COMBINING_HAMZA),
            "combiningHamzaTo": "ئ",
            "combiningHamzaRootTo": "ا",
            "wawDaggerAlef": ["وٰ", "ا", "ا"],
            "searchMap": {chr(k): v for k, v in ar.SEARCH_MAP.items()},
            "taMarbutaToHa": {"ة": "ه"},
            "skeletonDrop": ["ا", "ء"],
            "minSkeleton": 3,
            "definiteArticle": "ال",
            "rootHamzaMap": {chr(k): v for k, v in ar.ROOT_HAMZA_MAP.items()},
            "rootLetterMap": {chr(k): v for k, v in ar.ROOT_LETTER_MAP.items()},
            "rootKeep": [0x0621, 0x064A],
            "wordLetter": [[0x0621, 0x064A], [0x0671, 0x0671]],
        },
    )

    # ملف تحقق يقرؤه اختبار CI: كل الكلمات المميزة وكل الآيات وكل المحارف
    words = sorted({w for _s, _a, t in ayahs for _st, _en, w in tokenize_ayah(t)})
    chars = sorted({c for _s, _a, t in ayahs for c in t})
    cases = (
        [t for _s, _a, t in ayahs]
        + words
        + chars
        + [a + b for a in chars[:40] for b in chars[:40]]
        + [
            "الصلوٰة",
            "الربوٰا",
            "شيـٔا",
            "سبإ", "%_/", "  ",
        ]
    )
    write(
        "normgold.json",
        [
            [
                c,
                normalize_arabic_search(c),
                normalize_search_skeleton(c),
                normalize_surah_name(c),
                normalize_root_input(c),
            ]
            for c in cases
        ],
    )
    write(
        "tokengold.json",
        [[t, [[s, e] for s, e, _w in tokenize_ayah(t)]] for _s, _a, t in ayahs],
    )

    # ---------- 9) تسميات وأبعاد البحث الصرفي ----------
    dimensions = [
        {
            "key": "pos",
            "title": FEATURE_TITLES["pos"],
            "values": [
                {"value": k, "label": v} for k, v in sorted(POS_LABELS_AR.items())
            ],
        }
    ] + [
        {
            "key": key,
            "title": FEATURE_TITLES.get(key, key),
            "values": [
                {"value": value, "label": label}
                for value, label in values.items()
            ],
        }
        for key, values in FEATURE_LABELS.items()
    ]
    write(
        "morph/labels.json",
        {
            "posLabels": POS_LABELS_AR,
            "featureLabels": FEATURE_LABELS,
            "featureTitles": FEATURE_TITLES,
            "dimensions": dimensions,
        },
    )

    # ---------- 10) المصدر وحالة المراجعة والبصمة ----------
    snapshot = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    write(
        "meta.json",
        {
            "api_version": "static-v1",
            "data_release": qmeta["version_code"],
            "review_status": qmeta["review_status"],
            "confidence": qmeta["confidence"],
            "counts": qmeta["counts"],
            "snapshot_at": snapshot,
            "warning": qmeta["notice"],
        },
    )
    write(
        "provenance.json",
        {
            "text_version": {
                "version_code": qmeta["version_code"],
                "title": qmeta["title"],
                "riwayah": qmeta["riwayah"],
                "script_type": qmeta["script_type"],
                "counting_system": qmeta["counting_system"],
                "source_name": qmeta["sources"][0]["name"],
                "source_reference": qmeta["sources"][0]["url"],
                "sha256": quran_sha,
                "status": qmeta["review_status"],
                "is_validated": False,
                "double_approved": False,
            },
            "counts": qmeta["counts"],
            "occurrences_by_derivation": {
                "bundle_import": sum(len(e["o"]) for e in roots.values())
            },
            "morphology_sources": [
                {
                    "code": mmeta["source_code"],
                    "name": mmeta["name"],
                    "url": mmeta["url"],
                    "version": mmeta["source_version"],
                    "license": mmeta["license"],
                    "file_sha256": mmeta["file_sha256"],
                    "status": mmeta["review_status"],
                    "enabled": True,
                }
            ],
            "basmala_policy": qmeta["basmala_policy"],
            "sources": qmeta["sources"],
            "snapshot_at": snapshot,
            "notice": (
                "لقطة ثابتة "
                "من الحزمتين "
                "الموثقتين "
                f"بتاريخ {snapshot}. "
                + mmeta["notice"]
            ),
        },
    )
    write("methodology.json", methodology_payload())

    # ---------- 11) البيان: بصمة كل ملف وكل مصدر ----------
    total = sum((OUT / n).stat().st_size for n in files)
    if total > RAW_BUDGET:
        raise SystemExit(
            f"شجرة البيانات "
            f"{total} بايتًا > {RAW_BUDGET}"
        )
    manifest = {
        "schema": "qsp-static-data/v1",
        "built_at": snapshot,
        "data_release": qmeta["version_code"],
        "review_status": qmeta["review_status"],
        "sources": {
            "quran_bundle.json.gz": quran_sha,
            "morphology_qac04.json.gz": morph_sha,
            "declared_in_bundle": {
                **qmeta["sources"][0]["files"],
                **qmeta["sources"][1]["files"],
            },
        },
        "bytes_raw": total,
        "file_count": len(files),
        "files": dict(sorted(files.items())),
    }
    (OUT / "manifest.json").write_bytes(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )

    print(f"ملفات: {len(files) + 1}  خام: {total:,}")


if __name__ == "__main__":
    main()
