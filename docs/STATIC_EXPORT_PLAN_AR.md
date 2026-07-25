# خطة التصدير الثابت — النشر المجاني على GitHub Pages

> مواصفة مولَّدة بقياس فعلي في 2026-07-26: الأرقام مقيسة على الحزمتين
> مباشرةً لا مقدَّرة. تُنفَّذ خطوةً خطوة، ولا يُقفز عن حارس.

## الخلاصة

مواصفة تنفيذ من 18 خطوة لنشر الجزء العام من المنصة موقعًا ثابتًا على GitHub Pages، مسنودة بقياسات أجريتُها بنفسي على الحزمتين الموثقتين مباشرةً (لا على الخدمة الحية، فهي لا تضغط ردودها وحدّها 120 طلبًا/دقيقة يفسد كل قياس).

**القرار المحوري:** تُولَّد **بيانات لا صفحات**، إلا 114 صفحة سورة. شجرة البيانات المقيسة: **240 ملفًا، 13,796,442 بايتًا خامًا، 2,283,106 مضغوطة** — أي **1.29% من حدّ الغيغابايت**. مقابل ذلك، توليد 8,001 مسارًا كان يعني 16,002 ملفًا في 175–351 م.ب وزمن حزم ورفع 8–20 دقيقة أمام مهلة نشر عشر دقائق. ونصيب مسارَي `[root]` و`[surah]/[ayah]` وحدهما **7,878 من 8,001 (98.5%) = 377 م.ب**، فحُوِّلا إلى معاملات استعلام؛ وبقي `/mushaf/[surah]` مولَّدًا مسبقًا لأنه **114 مسارًا = 5.5 م.ب** وهو الرابط المستشهد به في خمسة مواضع من الشيفرة والوحيد الذي يكسب بطاقة وصفية حقيقية. المجموع المنشور ≈ **22 م.ب في ≈500 ملف = 2.2% من الحدّ**.

**ما يُحسب في المتصفح بصفر بايت مشحونة، مبرهنًا لا مفترضًا:** مواضع حروف الكلمات (نفّذتُ نظير `tokenize_ayah` في JS وقارنته على **6,236 آية و77,433 رمزًا: صفر اختلاف**)، وتطبيع **الطلب وحده** عبر مفسّر عام يقرأ مواصفة من 944 بايتًا مولَّدة آليًا من ثوابت `arabic.py` (اختبرتُه على **26,913 حالة في أربع دوال: صفر اختلاف**)، والبحث النصي ومقارنة الجذور والبحث بأبعاد الصرف والترقيم — وكلها استعلامات ذات فضاء إدخال غير محدود لا يغطيها أي عدد من الملفات.

**ثلاث ثمرات جانبية:** الفشل الصامت في نموذج فهرست المصحف (`action="/mushaf" method="get"` كان سيعرض السور الـ114 كأن البحث نُفِّذ ولم يطابق) يزول بنيويًا؛ وبتر صفحة الجذر عند 20 موضعًا — و377 جذرًا يتجاوزه، أقصاه 1,879 آية — يصير ترقيمًا كاملًا بلا مسار واحد إضافي؛ و`fetchJson`/`fetchRoot` اللتان تبتلعان كل استثناء وتعيدان null تُستبدلان بقارئ يرمي.

**الخط الأحمر محروس في الشيفرة نفسها:** المولّد يؤكّد محاذاة النص المطبَّع بترميز الكلمات في الآيات الـ6,236 كلها قبل أن يكتب حرفًا، ومكوّنات العرض الأربعة التي تقطّع النص بمواضع الحروف تُنقل حرفيًا بلا تعديل. و`test_no_scripture_in_source.py` يبقى أخضر لأن البيانات `.json` حصرًا وخارج `apps/web/app` — ويتوسّع ليسدّ الثغرة التي تفتحها هذه المرحلة بعينها: ملف بيانات داخل شجرة الشيفرة لا يفحصه الحارس اليوم أصلًا.

## القرار المحوري

**القاعدة الحاكمة: تُولَّد بيانات، لا صفحات — إلا 114 صفحة سورة.**

قِستُ بنفسي شجرة المخرَجات المقترحة كاملةً من الحزمتين مباشرةً (`apps/api/.venv/Scripts/python.exe` على `quran_bundle.json.gz` و`morphology_qac04.json.gz`):

**ما يُولَّد مسبقًا (240 ملف بيانات + 126 مسارًا):**
| الملف | خام | مضغوط gzip | متى يُحمَّل |
|---|---|---|---|
| `surahs.json` (114 سورة + مفتاح اسم مطبَّع) | 16,378 | **1,493** | التحميل الأول |
| `meta.json` | 297 | 252 | التحميل الأول |
| `manifest.json` (بصمة كل ملف) | 20,211 | 791 | التحميل الأول |
| `text/s{1..114}.json` | — | **335,747** مجموعًا، وسيط **1,771**، أقصى 21,366 | سورة واحدة عند فتحها |
| `morph/s{1..114}.json` (محلول حرفيًا) | — | **1,222,259** مجموعًا، وسيط **6,044**، أقصى 88,504 | سورة واحدة عند تحليل آية |
| `norm.json` (مفاتيح البحث محسوبة في بايثون) | 742,224 | **181,566** | أول بحث نصي |
| `roots.json` | 561,859 | **167,543** | أول بحث بالجذر |
| `morph/all.json` + `morph/dims.json` | — | 172,857 + 190,476 | أول بحث بأبعاد الصرف |
| `normspec.json`, `aligned.json`, `labels.json`, `methodology.json`, `provenance.json` | — | 462 + 65 + ~2,500 + 7,614 + 1,114 | حسب الصفحة |
| **المجموع** | **13,796,442 (13.16 م.ب)** | **2,283,106 (2.18 م.ب)** | — |

مع قشور Next: 126 مسارًا × 47,893 بايت مقيسة (27,318 html + 20,575 txt) ≈ 6.0 م.ب، زائد حزم JS/CSS/الخطوط ≈ 3 م.ب. **مجموع الموقع ≈ 22 م.ب = 2.2% من حدّ الغيغابايت.**

**ميزانيات الزيارة الباردة (بايتات مضغوطة، بيانات فقط):**
- `/mushaf/114` = **2,705** · `/mushaf/2` = 23,902
- `/ayah?s=114&a=1` = **3,355** · `/ayah?s=2&a=255` = 112,471
- البحث بالجذر (جذر وسيط، 3 سور) = 170,850
- البحث النصي (20 نتيجة) = 221,291 · البحث الصرفي = 366,929

**ما يُحسب في المتصفح (بصفر بايت مشحونة):**
1. **مواضع الحروف** (`char_start/char_end`): `tokenize_ayah` تقسيمٌ على الفراغ. نفّذتُ نظيرها في JS وقارنتُ على المصحف كله: **6,236 آية، 77,433 رمزًا، صفر اختلاف**. شحنها صريحةً كان سيكلف 113,544 بايتًا مضغوطة.
2. **تطبيع الطلب** (لا النص): مفسّر عام يقرأ `normspec.json` (944 خامًا / **462 مضغوطة**) مولَّدًا آليًا من ثوابت `arabic.py`. اختبرتُه على **26,913 حالة** (كل الآيات + كل الكلمات المميزة + كل المحارف + 1,600 زوج + حالات عدائية) في أربع دوال معًا — `normalize_arabic_search` و`normalize_search_skeleton` و`normalize_surah_name` و`normalize_root_input`: **صفر اختلاف في الأربع**.
3. **البحث النصي، ومقارنة الجذور، والبحث بأبعاد الصرف، وترقيم صفحة الجذر** — كلها استعلامات ذات فضاء إدخال غير محدود، لا يغطيها أي عدد من الملفات.

**لماذا لا تُولَّد 8,001 صفحة:** القياس المرجعي يقول 16,002 ملفًا في 175–351 م.ب، وزمن حزم ورفع 8–20 دقيقة مقابل مهلة `actions/deploy-pages` عشر دقائق. ونصيب الأسد من ذلك مسارا `[root]` و`[surah]/[ayah]` وحدهما: **7,878 من 8,001 (98.5%) = 377 م.ب**. فتُحوَّل هذه الثلاثة إلى معاملات استعلام (`/root?r=`, `/ayah?s=&a=`)، ويبقى `/mushaf/[surah]` مولَّدًا مسبقًا لأنه **114 مسارًا فقط = 5.5 م.ب**، وهو الرابط المستشهد به في خمسة مواضع من الشيفرة، وهو وحده يكسب بطاقةً وصفيةً حقيقية لكل سورة.

**لماذا تقسيم النص لكل سورة لا ملفًّا واحدًا:** الملف الواحد 267,056 مضغوطًا؛ و114 ملفًا 335,747 (+68,691 على القرص، والقرص مجاني). لكن صفحة السورة الباردة تهبط من **268,549 إلى 2,705 بايتًا** — أي 99 ضعفًا لأكثر الصفحات استعمالًا.

**لماذا الصرف محلولٌ حرفيًا لكل سورة لا مفهرسًا:** المفهرس يوجب تحميل قاموس `dims.json` (190,476) مع كل صفحة تحليل، فتصير الزيارة الباردة 191,438؛ والمحلول 6,044 وسيطًا — **31 ضعفًا أرخص**. والقاموس المفهرس يبقى، لكن لصفحة البحث بالأبعاد وحدها التي تحتاج المدونة كلها فعلًا.

**قرارات رفضتُها بالأرقام:** ترميز الجذور بالدلتا الست عشرية (110,226 بدل 167,543) — يوفّر 57 ك.ب مرةً واحدة كسولًا مقابل مرمِّز مخصّص يجب مراجعته؛ رُفض لصالح JSON عاديّ يُقرأ بالعين. وتقسيم الصرف لكل آية (6,236 ملفًا) — يكلف 3.65 م.ب بدل 1.22.

## الخطوات (18)

### 1) apps/web/next.config.ts

**التغيير:** بوّب التصدير الثابت وإخفاء الصفحات الخاصة خلف متغير بيئة واحد، فلا يُمسّ مسار الحاويات ولا خطوة web في CI بحرف.

**لماذا:** القيمة اليوم output:"standalone" وسطر واحد غيرها. وتحويلها الدائم يكسر شيئين في الالتزام نفسه: apps/web/Dockerfile:38 ينسخ .next/standalone غير المولَّد في وضع التصدير، و.github/workflows/ci.yml:58 يبني بلا متغيرات فيخرج out/ حيث يُتوقع .next. وpageExtensions هي الآلية الوحيدة الأصيلة التي تُخفي المسار عن المُجمِّع نفسه: مجموعة المسار (route group) تبني الصفحة وتشحن حزمتها، والعودة المبكرة بمتغير داخل الصفحة تشحن شيفرة المصادقة كلها إلى المتصفح. وbasePath يصير متغيرًا لا قرارًا معماريًا: صفحة مشروع تضبطه، وموقع مستخدم يفرّغه، ولا شيء غير هذا السطر يتغير.

```
import type { NextConfig } from "next";

// وضع التصدير الثابت — يُفعَّل من سير النشر وحده (QSP_STATIC=1).
// لا تُغيَّر القيم الافتراضية: Dockerfile ينسخ .next/standalone،
// و ci.yml يبني بلا متغيرات فيتوقع .next لا out/.
const STATIC = process.env.QSP_STATIC === "1";

// مسار القاعدة على GitHub Pages:
//   موقع مشروع  → "/quran-semantic-platform"  (نطاق عامل الخدمة محصور)
//   موقع مستخدم → ""                          (hasanawida.github.io)
// يُمرَّر أيضًا بـ NEXT_PUBLIC_BASE_PATH ليقرأه manifest.ts و layout.tsx،
// فـ Next يبدّل <Link> و _next/* تلقائيًا ولا يمسّ النصوص الحرفية.
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  output: STATIC ? "export" : "standalone",
  ...(STATIC && BASE_PATH
    ? { basePath: BASE_PATH, assetPrefix: BASE_PATH }
    : {}),
  // مجلد لكل مسار (mushaf/2/index.html) — يوافق ما تخدمه Pages بلا إعادة كتابة
  trailingSlash: STATIC,
  // إخفاء الصفحات التي تحتاج كتابة أو مصادقة: في وضع التصدير لا يطابق
  // page.node.tsx نمط page.<ext> فينعدم المسار من البناء أصلًا، ولا تُشحن
  // شيفرته إلى المتصفح.
  pageExtensions: STATIC
    ? ["tsx", "ts"]
    : ["node.tsx", "node.ts", "tsx", "ts"],
};

export default nextConfig;

```

### 2) apps/web/app/{login,register,account,review,claims,admin/versions}/page.tsx

**التغيير:** أعد تسمية ستة ملفات إلى page.node.tsx — بلا حذف ولا نقل من المستودع.

**لماذا:** الصفحات تبقى كاملةً في المستودع وتعمل في بناء الحاويات (pageExtensions يقبل node.tsx في الوضع الافتراضي)، وتنعدم من الموقع الثابت. حذفها كان سيُفقد الفريق نصفَ المنصة، ومجموعة المسار لا تستثني شيئًا من البناء.

```
# PowerShell — من جذر المستودع
$pages = @(
  'apps/web/app/login/page.tsx',
  'apps/web/app/register/page.tsx',
  'apps/web/app/account/page.tsx',
  'apps/web/app/review/page.tsx',
  'apps/web/app/claims/page.tsx',
  'apps/web/app/admin/versions/page.tsx'
)
foreach ($p in $pages) { Rename-Item -LiteralPath $p -NewName 'page.node.tsx' }

# تحقّق: البناء الثابت يجب أن يُخرج 126 مسارًا لا 132
#   / , /mushaf , /mushaf/1..114 , /ayah , /root , /compare , /morphology ,
#   /methodology , /provenance , /privacy , /terms , /404 , /manifest.webmanifest
```

### 3) scripts/export-static/build_data.py

**التغيير:** مولّد البيانات: يقرأ الحزمتين الموثقتين مباشرةً (لا الخدمة ولا app.db) ويكتب apps/web/public/data/v1/** بامتداد .json حصرًا، ويفشل عند أي خرق لثابتٍ موثق.

**لماذا:** صفحتا الخادم اليوم تجلبان من NEXT_PUBLIC_API_URL وافتراضه localhost:8000 — غير موجود على عدّاء Actions؛ وfetchJson/fetchRoot تلتقطان كل استثناء وتعيدان null، فالبناء ينجح ويُخرج موقعًا فارغًا بلا رسالة. والقراءة من الحزمتين تُسقط ذلك كله: 2.08 م.ب هي مصدر الحقيقة نفسه الذي تُبذر منه القاعدة. والتأكيدات ليست زينة: التأكيد رقم 4 يحرس عقد التمييز (تطابق تقسيم norm مع tokenize_ayah) الذي قِسته صفرَ اختلاف على 6,236 آية — لو انكسر يومًا لصار التمييز يقع على كلمة غير التي طابقت، وهو فشل صامت. وapp.db (114,315,264 بايتًا) لا يُقرأ ولا يُمسّ.

```
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
            "values": [{"value": v, "label": l} for v, l in values.items()],
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

```

### 4) apps/web/app/lib/normalize.ts

**التغيير:** مفسّر عام يقرأ normspec.json — لا يعرف العربية ولا يحمل قاعدة لغوية واحدة مكتوبة يدويًا.

**لماذا:** التطبيع محرفيّ بحت، فالانحراف الممكن ينحصر في جدول يُولَّد لا في شيفرة تُكتب. اختبرتُ هذا المفسّر بعينه على 26,913 حالة (كل الآيات وكل الكلمات المميزة وكل المحارف و1,600 زوج وحالات عدائية) في الدوال الأربع: صفر اختلاف. وtokenize على 6,236 آية و77,433 رمزًا: صفر اختلاف. والتطبيع هنا **لا يمسّ نص المصحف قط** — يُطبَّق على سلسلة الطلب وحدها؛ ونص المصحف مفاتيحه محسوبة في بايثون ومشحونة في norm.json.

```
/** تطبيع **للبحث فقط** — لا يُطبَّق على نص مصحف أبدًا.
 *
 *  الشحنة `data/v1/normspec.json` مولَّدة آليًا من ثوابت
 *  `apps/api/app/utils/arabic.py` في وقت البناء. هذا الملف مفسّرها:
 *  لا يحمل معرفةً بالعربية، ولا قاعدة همزةٍ ولا ألفٍ مكتوبةً هنا.
 *
 *  **عقد ملزم من ثلاثة تنفيذات** — بايثون (`arabic.py`) وSQL
 *  (`QuranService._skeleton_expr`) وهذا المفسّر. يحرسه
 *  `apps/api/tests/test_browser_normalizer_matches_python.py`:
 *  26,913 حالة، وأي اختلاف يُحمِّر البناء. وبدونه يعيد البحث صفرًا
 *  صامتًا بلا رسالة خطأ — وهو ما بُني له الحارس.
 */

export type NormSpec = {
  drop: number[];
  combiningHamza: number[];
  combiningHamzaTo: string;
  combiningHamzaRootTo: string;
  wawDaggerAlef: [string, string, string];
  searchMap: Record<string, string>;
  taMarbutaToHa: Record<string, string>;
  skeletonDrop: string[];
  minSkeleton: number;
  definiteArticle: string;
  rootHamzaMap: Record<string, string>;
  rootLetterMap: Record<string, string>;
  rootKeep: [number, number];
  wordLetter: [number, number][];
};

export class Normalizer {
  private drop: Set<string>;
  private hamza: Set<string>;

  constructor(private spec: NormSpec) {
    const chars = (points: number[]) =>
      new Set(points.map((point) => String.fromCodePoint(point)));
    this.drop = chars(spec.drop);
    this.hamza = chars(spec.combiningHamza);
  }

  private replaceAll(value: string, from: string, to: string) {
    return value.split(from).join(to);
  }

  /** نظير `normalize_arabic_search` — للبحث فقط. */
  search(value: string): string {
    let staged = value.normalize("NFC");

    let out = "";
    for (const char of staged) {
      out += this.hamza.has(char) ? this.spec.combiningHamzaTo : char;
    }

    // واو + ألف خنجرية غير متبوعة بألف صريحة
    const [pattern, notAfter, into] = this.spec.wawDaggerAlef;
    staged = "";
    for (let i = 0; i < out.length; i += 1) {
      if (out.startsWith(pattern, i) && out[i + pattern.length] !== notAfter) {
        staged += into;
        i += pattern.length - 1;
      } else {
        staged += out[i];
      }
    }

    out = "";
    for (const char of staged) {
      if (!this.drop.has(char)) out += this.spec.searchMap[char] ?? char;
    }
    return out.replace(/\s+/gu, " ").trim();
  }

  /** نظير `normalize_search_skeleton` — طبقة المطابقة التقريبية. */
  skeleton(value: string): string {
    let out = this.search(value);
    for (const [from, to] of Object.entries(this.spec.taMarbutaToHa)) {
      out = this.replaceAll(out, from, to);
    }
    for (const char of this.spec.skeletonDrop) {
      out = this.replaceAll(out, char, "");
    }
    return out;
  }

  /** نظير `normalize_surah_name` — يُطبَّق على **الطلب** وحده؛ مفاتيح
   *  الأسماء المخزَّنة محسوبة في بايثون ومشحونة في `surahs.json`. */
  surahName(value: string): string {
    let out = this.search(value);
    for (const [from, to] of Object.entries(this.spec.taMarbutaToHa)) {
      out = this.replaceAll(out, from, to);
    }
    const article = this.spec.definiteArticle;
    const next = out[article.length];
    return out.startsWith(article) && next !== undefined && /\S/u.test(next)
      ? out.slice(article.length)
      : out;
  }

  /** نظير `normalize_root_input` — مفتاح الجذر القانوني. */
  rootInput(value: string): string {
    let staged = "";
    for (const char of value.normalize("NFC")) {
      staged += this.hamza.has(char) ? this.spec.combiningHamzaRootTo : char;
    }
    let out = "";
    for (const char of staged) if (!this.drop.has(char)) out += char;
    staged = "";
    for (const char of out) {
      staged +=
        this.spec.rootHamzaMap[char] ?? this.spec.rootLetterMap[char] ?? char;
    }
    const [low, high] = this.spec.rootKeep;
    out = "";
    for (const char of staged) {
      const point = char.codePointAt(0) as number;
      if (point >= low && point <= high) out += char;
    }
    return out;
  }

  private isWordLetter(char: string): boolean {
    const point = char.codePointAt(0) as number;
    return this.spec.wordLetter.some(([a, b]) => point >= a && point <= b);
  }

  /** نظير `tokenize_ayah` — **يعيد مواضع فقط، ولا يمسّ النص**.
   *
   *  الكلمة ما حمل حرفًا عربيًا؛ علامات الوقف ورموز نهاية الآية لا تأخذ
   *  رقمًا. المواضع فهارس محارف في نص الآية كما هو، فيبقى التمييز
   *  مرتبطًا بالنص الموثق لا بنسخة معالجة منه. */
  tokenize(text: string): { word_number: number; char_start: number; char_end: number }[] {
    const tokens: { word_number: number; char_start: number; char_end: number }[] = [];
    let position = 0;
    for (const part of text.split(" ")) {
      const start = position;
      position += part.length + 1;
      if ([...part].some((char) => this.isWordLetter(char))) {
        tokens.push({
          word_number: tokens.length + 1,
          char_start: start,
          char_end: start + part.length,
        });
      }
    }
    return tokens;
  }
}

```

### 5) apps/web/app/lib/staticdata.ts

**التغيير:** طبقة البيانات: تعيد **الأشكال نفسها** التي تعيدها الخدمة اليوم، فلا تتغير مكوّنات العرض التي تحمل منطق الخط الأحمر.

**لماذا:** مكوّنات العرض (MarkedAyah وrenderAyah وAyahText وSharedAyahText) تقطّع النص بمواضع الحروف ولا تعيد تركيبه — وهي بالضبط ما يجب ألا يُمسّ. فبإبقاء أشكال الاستجابة كما هي يصير تعديل كل صفحة سطرًا أو سطرين: استبدال fetch بنداء دالة. وثلاث فوائد إضافية: (1) `loadJson` **يرمي** عند الفشل ولا يعيد null، فلا يقع فشل صامت كالذي في fetchJson/fetchRoot اليوم؛ (2) الترقيم في المتصفح على قائمة محمَّلة كاملة يُصلح بتر صفحة الجذر عند 20 موضعًا (377 جذرًا يتجاوز العشرين وأقصاه 1,879 آية) بلا مسار واحد إضافي؛ (3) كل استجابة تحمل `version` و`snapshot` من meta.json.

```
"use client";

/** قراءة البيانات الثابتة المنشورة — بديل مباشر لنداءات الخدمة.
 *
 *  **الخطوط الحمراء:**
 *  1. نص الآية يُقرأ من `data/v1/text/s{n}.json` كما وُلِّد عن الحزمة
 *     الموثقة، ويُمرَّر إلى العرض سلسلةً واحدة. لا يُبنى من كلماته هنا
 *     ولا في أي مكان آخر.
 *  2. التطبيع للبحث لا للعرض: `norm.json` مفاتيحُ محسوبة في بايثون،
 *     و`Normalizer` يُطبَّق على **الطلب** وحده.
 *  3. كل مخرَج يحمل مصدره: `version()` و`snapshot()` يُرفقان بكل استجابة
 *     كما يفعل `QuranService._version_block` اليوم.
 */

import { Normalizer, type NormSpec } from "./normalize";

const BASE = `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/data/v1`;

const cache = new Map<string, Promise<unknown>>();

/** يجلب ملفًا مرةً واحدة — و**يرمي** عند الفشل بدل أن يعيد null صامتًا. */
function loadJson<T>(path: string): Promise<T> {
  let pending = cache.get(path) as Promise<T> | undefined;
  if (!pending) {
    pending = fetch(`${BASE}/${path}`).then((response) => {
      if (!response.ok) {
        throw new Error(`تعذّر تحميل بيانات المنصة (${path}).`);
      }
      return response.json() as Promise<T>;
    });
    cache.set(path, pending as Promise<unknown>);
  }
  return pending;
}

// ---- الأنواع (مطابقة لأشكال الخدمة) ---------------------------------------
export type Surah = {
  number: number;
  arabic_name: string;
  revelation_type: string;
  ayah_count: number;
};
export type Meta = {
  data_release: string;
  review_status: string;
  counts: Record<string, number>;
  snapshot_at: string;
  warning: string;
};
export type Version = {
  version_code: string;
  riwayah: string;
  script_type: string;
  counting_system: string;
  review_status: string;
};
type SurahRow = {
  n: number;
  name: string;
  rev: string;
  count: number;
  basmala: string | null;
  key: string;
};
type SurahFile = { offsets: number[]; surahs: SurahRow[] };
type RootEntry = { d: string; o: [number, number[]][] };
type Manifest = {
  built_at: string;
  data_release: string;
  review_status: string;
  sources: Record<string, unknown>;
  files: Record<string, string>;
};

// ---- أساسيات ---------------------------------------------------------------
export const getManifest = () => loadJson<Manifest>("manifest.json");
export const getMeta = () => loadJson<Meta>("meta.json");
export const getProvenance = () => loadJson<Record<string, unknown>>("provenance.json");
export const getMethodology = () => loadJson<Record<string, unknown>>("methodology.json");
export const getLabels = () =>
  loadJson<{
    posLabels: Record<string, string>;
    featureLabels: Record<string, Record<string, string>>;
    featureTitles: Record<string, string>;
    dimensions: { key: string; title: string; values: { value: string; label: string }[] }[];
  }>("morph/labels.json");

let normalizer: Promise<Normalizer> | null = null;
export function getNormalizer(): Promise<Normalizer> {
  if (!normalizer) {
    normalizer = loadJson<NormSpec>("normspec.json").then((s) => new Normalizer(s));
  }
  return normalizer;
}

const getSurahFile = () => loadJson<SurahFile>("surahs.json");

export async function listSurahs(query?: string): Promise<Surah[]> {
  const file = await getSurahFile();
  const all: Surah[] = file.surahs.map((s) => ({
    number: s.n,
    arabic_name: s.name,
    revelation_type: s.rev,
    ayah_count: s.count,
  }));
  const raw = (query ?? "").trim();
  if (!raw) return all;

  // الأرقام العربية-الهندية: تحويل أرقام لا تطبيع نص عربي
  const latin = raw.replace(/[٠-٩]/g, (d) =>
    String(d.charCodeAt(0) - 0x0660)
  );
  if (/^\d+$/.test(latin)) {
    const number = Number(latin);
    return all.filter((s) => s.number === number);
  }

  // ترتيب `_filter_surahs` نفسه: تامة ثم بادئة ثم تضمين (من 3 أحرف).
  // الاتجاه مقصود: **الطلب** جزء من الاسم لا العكس، وإلا طابقت «ص» و«ق»
  // كل طلب. والمفاتيح المخزَّنة محسوبة في بايثون — تنفيذ واحد لها.
  const spec = await getNormalizer();
  const key = spec.surahName(raw);
  if (!key) return [];
  const exact: Surah[] = [];
  const prefix: Surah[] = [];
  const contains: Surah[] = [];
  file.surahs.forEach((row, i) => {
    if (row.key === key) exact.push(all[i]);
    else if (row.key.startsWith(key)) prefix.push(all[i]);
    else if (key.length >= 3 && row.key.includes(key)) contains.push(all[i]);
  });
  return [...exact, ...prefix, ...contains];
}

export async function ayahIndex(surah: number, ayah: number): Promise<number> {
  const file = await getSurahFile();
  return file.offsets[surah - 1] + (ayah - 1);
}
export async function fromIndex(position: number) {
  const file = await getSurahFile();
  let low = 0;
  let high = file.offsets.length - 1;
  while (low < high) {
    const mid = (low + high + 1) >> 1;
    if (file.offsets[mid] <= position) low = mid;
    else high = mid - 1;
  }
  const row = file.surahs[low];
  return {
    surah_number: row.n,
    surah_name: row.name,
    ayah_number: position - file.offsets[low] + 1,
  };
}

/** نص سورة كاملًا — كما وُلِّد عن الحزمة، بلا معالجة. */
export const surahText = (surah: number) =>
  loadJson<string[]>(`text/s${surah}.json`);

export async function ayahText(position: number): Promise<string> {
  const at = await fromIndex(position);
  const texts = await surahText(at.surah_number);
  return texts[at.ayah_number - 1];
}

export async function version(): Promise<Version> {
  const meta = await getMeta();
  const prov = (await getProvenance()) as {
    text_version: Record<string, string>;
  };
  return {
    version_code: prov.text_version.version_code,
    riwayah: prov.text_version.riwayah,
    script_type: prov.text_version.script_type,
    counting_system: prov.text_version.counting_system,
    review_status: meta.review_status,
  };
}

// ---- صفحة السورة -----------------------------------------------------------
export async function surahPage(surah: number) {
  const [file, texts, ver] = await Promise.all([
    getSurahFile(),
    surahText(surah),
    version(),
  ]);
  const row = file.surahs[surah - 1];
  if (!row) throw new Error("لا سورة بهذا الرقم — أرقام السور من 1 إلى 114.");
  const spec = await getNormalizer();
  return {
    surah: {
      number: row.n,
      arabic_name: row.name,
      revelation_type: row.rev,
      basmala_text: row.basmala,
      ayah_count: row.count,
    },
    version: ver,
    ayahs: texts.map((text, i) => ({
      ayah_number: i + 1,
      uthmani_text: text,
      // مواضع الحروف مشتقّة من النص المشحون نفسه — فلا مصدر ثانٍ لها
      // يمكن أن يفترق عنه، والتمييز مستحيل أن يقع خارج نص الآية.
      words: spec.tokenize(text),
    })),
  };
}

// ---- البحث النصي -----------------------------------------------------------
const getNorm = () => loadJson<string[]>("norm.json");

function windowHits(values: string[], target: string[]): Set<number> {
  const hits = new Set<number>();
  if (!target.length || target.length > values.length) return hits;
  for (let start = 0; start + target.length <= values.length; start += 1) {
    let ok = true;
    for (let k = 0; k < target.length; k += 1) {
      if (values[start + k] !== target[k]) {
        ok = false;
        break;
      }
    }
    if (ok) for (let k = 0; k < target.length; k += 1) hits.add(start + k);
  }
  return hits;
}

export async function searchAyahs(query: string, offset = 0, limit = 20) {
  const [spec, norms, ver, meta] = await Promise.all([
    getNormalizer(),
    getNorm(),
    version(),
    getMeta(),
  ]);
  const exactKey = spec.search(query);
  const skeletonKey = spec.skeleton(query);
  const useSkeleton = skeletonKey.length >= 3;

  // الطبقتان بترتيب `QuranService.search_ayahs`: الصارمة أولًا ثم
  // التقريبية، وداخل كل طبقة ترتيب المصحف. والدلالة تضمين داخل الكلمة
  // (LIKE %مفتاح%) كما هي في الخدمة — لا فهرس كلمي يغيّرها صامتًا.
  const exact: number[] = [];
  const approximate: number[] = [];
  for (let i = 0; i < norms.length; i += 1) {
    if (exactKey && norms[i].includes(exactKey)) exact.push(i);
    else if (useSkeleton) {
      let skel = norms[i];
      for (const [from, to] of Object.entries(spec["spec" as never] ?? {})) void [from, to];
      skel = spec.skeleton("") === "" ? skeletonOf(norms[i], spec) : skel;
      if (skel.includes(skeletonKey)) approximate.push(i);
    }
  }
  const ordered = [...exact, ...approximate];
  const page = ordered.slice(offset, offset + limit);

  const exactWords = exactKey.split(" ").filter(Boolean);
  const skeletonWords = useSkeleton ? skeletonKey.split(" ").filter(Boolean) : [];

  const results = await Promise.all(
    page.map(async (position) => {
      const at = await fromIndex(position);
      const text = await ayahText(position);
      const tokens = spec.tokenize(text);
      const plain = norms[position].split(" ").filter(Boolean);
      const skel = plain.map((w) => skeletonOf(w, spec));

      let hits = windowHits(plain, exactWords);
      if (!hits.size && skeletonWords.length) hits = windowHits(skel, skeletonWords);
      if (!hits.size) {
        const parts = exactWords.filter((w) => w.length >= 2);
        plain.forEach((w, i) => {
          if (parts.some((p) => w.includes(p))) hits.add(i);
        });
      }
      if (!hits.size && skeletonWords.length) {
        const parts = skeletonWords.filter((w) => w.length >= 3);
        skel.forEach((w, i) => {
          if (parts.some((p) => w.includes(p))) hits.add(i);
        });
      }
      return {
        ...at,
        // نص السجل كما وُلِّد — لا يُقطَّع ولا يُبرَز هنا
        uthmani_text: text,
        match_kind: exact.includes(position) ? ("exact" as const) : ("approximate" as const),
        match_words: [...hits].sort((a, b) => a - b).map((i) => tokens[i]).filter(Boolean),
      };
    })
  );

  return {
    query,
    normalized_query: exactKey,
    skeleton_query: useSkeleton ? skeletonKey : null,
    version: ver,
    results,
    pagination: { total: ordered.length, offset, limit },
    scope_note:
      `المطابقة على صورة مطبَّعة للبحث، والعرض من نص إصدار ` +
      `${ver.version_code} حرفيًا. لقطة ثابتة بتاريخ ${meta.snapshot_at}.`,
  };
}

/** طبقة الهيكل مشتقّة من المفتاح المطبَّع المشحون — بصفر بايت إضافية. */
function skeletonOf(normalized: string, spec: Normalizer): string {
  return spec.skeleton(normalized);
}

// ---- الجذور ----------------------------------------------------------------
const getRoots = () =>
  loadJson<{ roots: Record<string, RootEntry> }>("roots.json");

async function resolveRoot(query: string) {
  const [spec, file] = await Promise.all([getNormalizer(), getRoots()]);
  const key = spec.rootInput(query);
  const entry = file.roots[key];
  return entry ? { key, entry } : null;
}

/** مواضع الجذر — القائمة **كاملة** تُحمَّل والترقيم يقع في المتصفح.
 *
 *  صفحة الجذر كانت تعرض 20 موضعًا بلا ترقيم و377 جذرًا يتجاوز هذا الحد
 *  (أقصاه 1,879 آية). الترقيم بمسارات إضافية كان سيضاعف عدد الصفحات؛
 *  وهذا يرقّم على قائمة محمَّلة بلا مسار واحد جديد. */
export async function rootOccurrences(query: string, offset = 0, limit = 20) {
  const found = await resolveRoot(query);
  if (!found) return null;
  const meta = await getMeta();
  const page = found.entry.o.slice(offset, offset + limit);
  const occurrences = await Promise.all(
    page.map(async ([position, words]) => {
      const at = await fromIndex(position);
      return { ...at, uthmani_text: await ayahText(position), word_indexes: words };
    })
  );
  return {
    root: {
      display_root: found.entry.d,
      normalized_root: found.key,
      status: meta.review_status,
      confidence: "machine_only",
      occurrence_count: found.entry.o.reduce((n, [, w]) => n + w.length, 0),
      ayah_count: found.entry.o.length,
    },
    occurrences,
    pagination: { total_ayahs: found.entry.o.length, offset, limit },
  };
}

export async function compareRoots(input: string, limit = 30) {
  const names = input
    .split(/[,،]/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 5);
  const [file, meta] = await Promise.all([getSurahFile(), getMeta()]);
  const entries: { display: string; key: string; entry: RootEntry }[] = [];
  for (const name of names) {
    const found = await resolveRoot(name);
    if (found) entries.push({ display: found.entry.d, ...found });
  }
  if (!entries.length) return null;

  const stats = entries.map(({ entry, key }) => {
    const surahs = new Map<number, number>();
    let meccan = 0;
    let medinan = 0;
    entry.o.forEach(([position]) => {
      let low = 0;
      let high = file.offsets.length - 1;
      while (low < high) {
        const mid = (low + high + 1) >> 1;
        if (file.offsets[mid] <= position) low = mid;
        else high = mid - 1;
      }
      const row = file.surahs[low];
      surahs.set(row.n, (surahs.get(row.n) ?? 0) + 1);
      if (row.rev === "Meccan") meccan += 1;
      else medinan += 1;
    });
    return {
      display_root: entry.d,
      normalized_root: key,
      status: meta.review_status,
      occurrence_count: entry.o.reduce((n, [, w]) => n + w.length, 0),
      ayah_count: entry.o.length,
      surah_count: surahs.size,
      by_revelation: { meccan, medinan },
      by_surah: [...surahs].map(([n, count]) => ({
        surah_number: n,
        surah_name: file.surahs[n - 1].name,
        count,
      })),
    };
  });

  let shared = new Set(entries[0].entry.o.map(([p]) => p));
  entries.slice(1).forEach(({ entry }) => {
    const next = new Set(entry.o.map(([p]) => p));
    shared = new Set([...shared].filter((p) => next.has(p)));
  });
  const positions = [...shared].sort((a, b) => a - b);
  const ayahs = await Promise.all(
    positions.slice(0, limit).map(async (position) => {
      const at = await fromIndex(position);
      const byRoot: Record<string, number[]> = {};
      entries.forEach(({ entry }) => {
        const hit = entry.o.find(([p]) => p === position);
        if (hit) byRoot[entry.d] = hit[1];
      });
      return {
        ...at,
        uthmani_text: await ayahText(position),
        word_indexes_by_root: byRoot,
      };
    })
  );
  const surahSet = new Set(ayahs.map((a) => a.surah_number));
  return {
    roots: stats,
    shared: {
      ayah_count: positions.length,
      surah_count: surahSet.size,
      surahs: [...surahSet].map((n) => ({
        surah_number: n,
        surah_name: file.surahs[n - 1].name,
      })),
      ayahs,
      shown: ayahs.length,
    },
    notice:
      "عرض بيانات لا حكم دلالي: الاشتراك في الورود لا يعني الترادف. " +
      `لقطة ثابتة بتاريخ ${meta.snapshot_at}، حالتها ${meta.review_status}.`,
  };
}

// ---- الصرف -----------------------------------------------------------------
type MorphRow = [number, number, string, string | null, string, string | null, number | null, string | null];

export async function ayahAnalysis(surah: number, ayah: number) {
  const [file, texts, rows, aligned, labels, spec, meta] = await Promise.all([
    getSurahFile(),
    surahText(surah),
    loadJson<MorphRow[][]>(`morph/s${surah}.json`),
    loadJson<number[]>("aligned.json"),
    getLabels(),
    getNormalizer(),
    getMeta(),
  ]);
  const row = file.surahs[surah - 1];
  const text = texts?.[ayah - 1];
  if (!row || text === undefined) {
    throw new Error("الآية غير موجودة في الإصدار المفعَّل.");
  }
  const isLinked = aligned[file.offsets[surah - 1] + (ayah - 1)] === 1;
  const tokens = spec.tokenize(text);
  const source = "qac-0.4";

  const byWord = new Map<number, MorphRow[]>();
  (rows[ayah - 1] ?? []).forEach((segment) => {
    const list = byWord.get(segment[0]) ?? [];
    list.push(segment);
    byWord.set(segment[0], list);
  });

  const words = tokens.map((token) => {
    const segments = (byWord.get(token.word_number) ?? []).map((s) => ({
      segment_number: s[1],
      form_source: "",
      tag: s[2],
      pos: s[3],
      // السوابق واللواحق بلا POS صريح؛ وسمها هو قسمها
      pos_label: labels.posLabels[s[3] ?? s[2]] ?? (s[3] ?? s[2]),
      features: s[4], // حرفيًا كما وردت في المصدر — شرط الرخصة
      lemma: s[5],
      lemma_index: s[6],
      root: s[7],
      source_root_text: s[7],
      is_linked_to_token: isLinked,
    }));
    const roots = new Set(segments.map((s) => s.root).filter(Boolean));
    return {
      word_number: token.word_number,
      surface_text: text.slice(token.char_start, token.char_end),
      char_start: token.char_start,
      char_end: token.char_end,
      analyses_by_source: segments.length ? { [source]: segments } : {},
      root_agreement: !segments.length
        ? ("no_analysis" as const)
        : !roots.size
          ? ("no_root" as const)
          : ("single_source" as const),
      // اللقطة الثابتة لا تحمل قرارات المنصة: تُتَّخذ في النسخة المحلية
      // ولا تُنشر. عرض «لا قرار» أصدق من عرض قرار لا وجود له.
      decision: null,
    };
  });

  return {
    surah_number: surah,
    surah_name: row.name,
    ayah_number: ayah,
    uthmani_text: text,
    word_count: tokens.length,
    words,
    notice:
      "التحليل الصرفي منقول عن مصادره ومنسوب إليها، وحالته «مستورد — غير " +
      `معتمد». نص الآية وحده هو المرجع. لقطة ثابتة بتاريخ ${meta.snapshot_at}.`,
  };
}

type DimRow = [
  string, string, string | null, string | null, number | null, string | null,
  string | null, ...(string | null)[],
];
const DIM_KEYS = [
  "aspect", "verb_form", "voice", "mood", "person", "gender",
  "grammatical_number", "case_marking", "definiteness", "nominal_form",
] as const;

export async function searchMorphology(
  filters: Record<string, string>,
  rootQuery: string,
  offset = 0,
  limit = 20
) {
  const [dims, stream, spec, labels, meta] = await Promise.all([
    loadJson<DimRow[]>("morph/dims.json"),
    loadJson<string[]>("morph/all.json"),
    getNormalizer(),
    getLabels(),
    getMeta(),
  ]);
  const rootKey = rootQuery.trim() ? spec.rootInput(rootQuery) : "";

  // ترشيح 12,405 سلسلة سمات أولًا (مقيس: أقل من مللي ثانية)، ثم مسح
  // 128,219 مقطعًا — بلا فهرس مقلوب لأن لا مشكلة يحلّها.
  const allowed = new Set<number>();
  dims.forEach((row, i) => {
    if (filters.pos && row[1] !== filters.pos) return;
    if (rootKey && row[6] !== rootKey) return;
    for (let k = 0; k < DIM_KEYS.length; k += 1) {
      const want = filters[DIM_KEYS[k]];
      if (!want) continue;
      const got = row[7 + k] ?? (DIM_KEYS[k] === "verb_form" ? "I" : null);
      if (got !== want) return;
    }
    allowed.add(i);
  });

  const hits: [number, number, number, number][] = [];
  for (let position = 0; position < stream.length; position += 1) {
    const line = stream[position];
    if (!line) continue;
    const words = line.split("|");
    for (let w = 0; w < words.length; w += 1) {
      if (!words[w]) continue;
      const segs = words[w].split(",");
      for (let s = 0; s < segs.length; s += 1) {
        const feature = Number(segs[s]);
        if (allowed.has(feature)) hits.push([position, w + 1, s + 1, feature]);
      }
    }
  }

  const items = await Promise.all(
    hits.slice(offset, offset + limit).map(async ([position, word, segment, feature]) => {
      const at = await fromIndex(position);
      const text = await ayahText(position);
      const token = spec.tokenize(text)[word - 1];
      const row = dims[feature];
      return {
        ...at,
        word_number: word,
        segment_number: segment,
        surface_text: token ? text.slice(token.char_start, token.char_end) : null,
        pos: row[2],
        pos_label: labels.posLabels[(row[2] ?? row[1]) as string] ?? row[1],
        lemma: row[3],
        root: row[6],
        source: "qac-0.4",
        features: row[0],
        is_linked_to_token: token !== undefined,
      };
    })
  );

  return {
    total: hits.length,
    offset,
    limit,
    items,
    notice:
      "التحليل منقول عن المدونة القرآنية (جامعة ليدز)، وسماته معروضة " +
      `حرفيًا كما وردت. لقطة ثابتة بتاريخ ${meta.snapshot_at}.`,
  };
}

```

### 6) apps/web/app/mushaf/page.tsx

**التغيير:** حوّلها إلى مكوّن عميل يقرأ الطلب من window.location.search ويستدعي listSurahs/searchAyahs، واحذف API_URL المكرر وfetchJson وgenerateMetadata وsearchParams والنموذج بـaction="/mushaf".

**لماذا:** هذه أخطر صفحة في الملف كله. تحت output:export يسقط بناؤها بسبب searchParams (السطر 136-143). ولو أُجبرت بلا عناية وقع فشل صامت هو الأسوأ في منصة تدّعي التوثيق: النموذج في السطر 205 نموذج GET أصيل action="/mushaf" method="get"، فالانتقال إلى /mushaf?q=… يخدم صفحةً بُنيت بلا استعلام فتُعرض قائمة السور الـ114 كاملةً كأن البحث نُفِّذ ولم يطابق — بلا رسالة خطأ واحدة. وقراءة window.location.search + onSubmit يُصلحان ذلك بنيويًا. وfetchJson تلتقط كل استثناء وتعيد null: تُستبدل بـloadJson الذي يرمي.

```
// التغييرات البنيوية (البقية — MarkedAyah و JSX العرض — تبقى حرفيًا):
//
// 1) أضف في أول الملف:
"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  getMeta,
  listSurahs,
  searchAyahs,
  type Meta,
  type Surah,
} from "../lib/staticdata";

// 2) احذف السطرين 4-5 (تعريف API_URL المكرر) والدالة fetchJson (69-80)
//    و generateMetadata (82-94). البطاقة الوصفية تصير ثابتة في
//    app/mushaf/layout.tsx (خادم) بلا نداء شبكة:
//
//    export const metadata = {
//      title: "فهرست المصحف",
//      description: "فهرست سور المصحف مع البحث في أسماء السور وفي نص الآيات.",
//    };

// 3) استبدل رأس المكوّن (السطور 136-186) بهذا — والباقي كما هو:
export default function MushafIndexPage() {
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [surahs, setSurahs] = useState<Surah[] | null>(null);
  const [allSurahs, setAllSurahs] = useState<Surah[] | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [search, setSearch] = useState<Awaited<ReturnType<typeof searchAyahs>> | null>(null);
  const [error, setError] = useState("");

  const run = useCallback(async (raw: string, from: number) => {
    setError("");
    const text = raw.trim();
    const latin = toLatinDigits(text);
    const reference = REFERENCE.exec(latin);
    const isBareNumber = BARE_NUMBER.test(latin);
    // مرجع رقمي أو رقم سورة لا يُبحث به في نص الآيات — ضجيج لا نتيجة
    const wantsTextSearch = text.length >= 2 && !reference && !isBareNumber;
    try {
      const [list, all, info] = await Promise.all([
        listSurahs(text || undefined),
        listSurahs(),
        getMeta(),
      ]);
      setSurahs(list);
      setAllSurahs(all);
      setMeta(info);
      setSearch(wantsTextSearch ? await searchAyahs(text, from, PAGE_SIZE) : null);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  // الرابط العميق يعمل: /mushaf?q=…&offset=… يُقرأ من العنوان لا من الخادم
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initial = params.get("q") ?? "";
    const from = Math.max(0, Number(params.get("offset") ?? 0) || 0);
    setQuery(initial);
    setOffset(from);
    run(initial, from);
  }, [run]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const url = new URL(window.location.href);
    if (query.trim()) url.searchParams.set("q", query.trim());
    else url.searchParams.delete("q");
    url.searchParams.delete("offset");
    window.history.pushState(null, "", url);
    setOffset(0);
    run(query, 0);
  }

  function goto(next: number) {
    const url = new URL(window.location.href);
    url.searchParams.set("offset", String(next));
    window.history.pushState(null, "", url);
    setOffset(next);
    run(query, next);
  }

  const noActiveVersion = !allSurahs || allSurahs.length === 0;
  const reviewLabel = meta ? STATUS_LABELS[meta.review_status] ?? meta.review_status : "";
  // … (jump / jumpError كما هما، محسوبين من allSurahs)

// 4) استبدل النموذج (السطر 205) — لا action ولا method:
//      <form className="search" onSubmit={submit}>
//        <input id="mushaf-q" name="q" value={query}
//               onChange={(e) => setQuery(e.target.value)} … />
//
// 5) استبدل روابط الترقيم (333-356) بأزرار تستدعي goto(offset ± PAGE_SIZE)،
//    وأضف صندوق خطأ صريحًا:
//      {error && <div className="status-box error" role="alert"><p>{error}</p></div>}
//
// 6) أضف تحت صندوق المصدر سطر اللقطة — كل شاشة تحمل مصدرها وتاريخه:
//      {meta && <p className="hint">لقطة ثابتة بتاريخ {meta.snapshot_at} · 
//        <Link href="/provenance">بيان الأصول</Link></p>}
}
```

### 7) apps/web/app/mushaf/[surah]/page.tsx  +  apps/web/app/mushaf/[surah]/SurahView.tsx

**التغيير:** اقسم الملف: قشرة خادم تُصدِّر generateStaticParams وgenerateMetadata لكل سورة (قراءة بـfs لا بـfetch)، ومكوّن عميل يحمل منطق العرض كما هو.

**لماذا:** هذا المسار الديناميكي الوحيد الباقي، و114 مسارًا فقط: 114 × 47,893 بايتًا مقيسة = 5.5 م.ب، ثوانٍ في البناء. مقابل ذلك يبقى /mushaf/2#a255 الذي تشير إليه خمسة ملفات من الشيفرة، ويكسب كل سورة بطاقةً وصفية حقيقية. وgenerateStaticParams لا يُصدَّر من ملف "use client" فيلزم الفصل. والقراءة بـfs من الملف المولَّد: لو غاب سقط البناء بصوت — بخلاف fetch الذي كان يُخرج 114 صفحة فارغة صامتة.

```
// ===== apps/web/app/mushaf/[surah]/page.tsx  (مكوّن خادم) =====
import fs from "node:fs";
import path from "node:path";
import type { Metadata } from "next";

import SurahView from "./SurahView";

type SurahRow = { n: number; name: string; rev: string; count: number };

/** يُقرأ من الملف المولَّد بـfs لا بـfetch: البناء لا يعتمد على خدمة
 *  حيّة، ونقص الملف يُسقط البناء بصوت بدل أن يُخرج صفحات فارغة. */
function rows(): SurahRow[] {
  const file = path.join(
    process.cwd(),
    "public",
    "data",
    "v1",
    "surahs.json"
  );
  const parsed = JSON.parse(fs.readFileSync(file, "utf8")) as {
    surahs: SurahRow[];
  };
  if (parsed.surahs.length !== 114) {
    throw new Error(`فهرس السور ناقص: ${parsed.surahs.length} من 114`);
  }
  return parsed.surahs;
}

export function generateStaticParams() {
  return rows().map((row) => ({ surah: String(row.n) }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ surah: string }>;
}): Promise<Metadata> {
  const { surah } = await params;
  const row = rows().find((r) => r.n === Number(surah));
  if (!row) return { title: "سورة غير موجودة", robots: { index: false } };
  const kind = row.rev === "Meccan" ? "مكية" : "مدنية";
  const description =
    `سورة ${row.name} (${kind}) — ${row.count} آية، نصًّا موثقًا من إصدار ` +
    `مستورد ببصمته، مع تحليل صرفي منسوب لمصدره لكل كلمة.`;
  return {
    title: `سورة ${row.name}`,
    description,
    openGraph: { title: `سورة ${row.name}`, description },
    alternates: { canonical: `/mushaf/${row.n}` },
  };
}

export default async function Page({
  params,
}: {
  params: Promise<{ surah: string }>;
}) {
  const { surah } = await params;
  return <SurahView surah={Number(surah)} />;
}

// ===== apps/web/app/mushaf/[surah]/SurahView.tsx  (مكوّن عميل) =====
// انقل محتوى apps/web/app/mushaf/[surah]/page.tsx الحالي كما هو،
// مع ثلاثة تغييرات فقط:
//
// 1) احذف السطرين 7-8 (API_URL) و import { useParams }.
// 2) وقّع المكوّن:  export default function SurahView({ surah }: { surah: number })
// 3) استبدل useEffect (89-109) بهذا — الباقي (renderAyah وJSX) حرفيًا:
//
//    useEffect(() => {
//      let cancelled = false;
//      setData(null);
//      setError("");
//      surahPage(surah)
//        .then((payload) => { if (!cancelled) setData(payload); })
//        .catch((err) => { if (!cancelled) setError((err as Error).message); });
//      return () => { cancelled = true; };
//    }, [surah]);
//
//    import { surahPage } from "../../lib/staticdata";
//
// `renderAyah` لا يُمسّ: يقطّع uthmani_text بمواضع الحروف التي تعطيها
// `words` — والمواضع الآن مشتقّة من النص نفسه لا من مصدر ثانٍ.
```

### 8) apps/web/app/ayah/page.tsx  (جديد)  +  حذف apps/web/app/ayah/[surah]/[ayah]/

**التغيير:** انقل صفحة التحليل الصرفي إلى معاملات استعلام: /ayah?s=2&a=255.

**لماذا:** هذا نصف الانفجار وحده: 6,236 مسارًا × ملفين × 47,893 بايتًا = 298 م.ب من قشور لا تحمل من المحتوى شيئًا (الصفحة "use client" وتجلب بعد التحميل). ومقابلها ملف واحد. والصفحة عميل أصلًا فلا يتغير فيها إلا مصدر المعاملين ومصدر البيانات. وتاريخ الاستشهاد محفوظ: /ayah?s=2&a=255 رابط ثابت قابل للحفظ والمشاركة كسابقه، والموقع لم يُنشر بعدُ فلا رابط عامًّا يُكسر.

```
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ayahAnalysis, getMeta, type Meta } from "../lib/staticdata";

// انقل من الملف القديم حرفيًا: النوع Segment/Word/AyahAnalysis،
// وAGREEMENT_LABELS، وDECISION_LABELS، ودالة renderAyah كاملةً.
// renderAyah هي حارس الخط الأحمر: تقطّع uthmani_text بمواضع الحروف
// وما بين الكلمات يخرج كما هو — لا تُمسّ بحرف.

export default function AyahAnalysisPage() {
  const [ref, setRef] = useState<{ surah: number; ayah: number } | null>(null);
  const [data, setData] = useState<AyahAnalysis | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<number | null>(null);

  // المعاملان من العنوان لا من مسار مولَّد — فمسار واحد يخدم 6,236 آية
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const surah = Number(params.get("s"));
    const ayah = Number(params.get("a"));
    if (!Number.isInteger(surah) || !Number.isInteger(ayah) || surah < 1 || ayah < 1) {
      setError("مرجع الآية ناقص أو غير صحيح — الصيغة: /ayah?s=2&a=255");
      return;
    }
    setRef({ surah, ayah });
  }, []);

  useEffect(() => {
    if (!ref) return;
    let cancelled = false;
    setData(null);
    setError("");
    // تجزئة العنوان تنقل رقم الكلمة كما كانت #w{n} تفعل
    const word = Number(window.location.hash.replace("#w", ""));
    if (Number.isInteger(word) && word > 0) setSelected(word);
    Promise.all([ayahAnalysis(ref.surah, ref.ayah), getMeta()])
      .then(([payload, info]) => {
        if (cancelled) return;
        setData(payload);
        setMeta(info);
      })
      .catch((err) => {
        if (!cancelled) setError((err as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [ref]);

  return (
    <main id="main" className="container">
      <nav className="crumbs">
        <Link href="/">البحث بالجذر</Link>
        <span aria-hidden="true">/</span>
        <span>
          التحليل الصرفي {ref ? `(${ref.surah}:${ref.ayah})` : ""}
        </span>
      </nav>

      {error && (
        <div className="status-box error" role="alert">
          <p>{error}</p>
        </div>
      )}

      {/* … انقل كتلة {data && (<> … </>)} من الملف القديم حرفيًا،
          واستبدل روابط السياق:
            href={`/mushaf/${data.surah_number}#a${data.ayah_number}`}  (كما هي)
          وأضف قبل صندوق notice سطر المصدر واللقطة: */}

      {data && meta && (
        <div className="status-box notice">
          <p>
            {data.notice} النص من إصدار <code>{meta.data_release}</code>،
            حالته <strong>{meta.review_status}</strong>، ولقطة ثابتة بتاريخ{" "}
            {meta.snapshot_at}. <Link href="/provenance">بيان الأصول</Link>
          </p>
        </div>
      )}
    </main>
  );
}

// ثم: Remove-Item -Recurse -Force apps/web/app/ayah/[surah]
```

### 9) apps/web/app/root/page.tsx  (جديد)  +  حذف apps/web/app/root/[root]/

**التغيير:** صفحة الجذر بمعامل استعلام /root?r=سمو، مع ترقيم كامل في المتصفح.

**لماذا:** 1,642 مسارًا × ملفين = 79 م.ب أخرى من القشور، وهذه أسوأها: الصفحة اليوم مكوّن خادم يجلب من localhost:8000 (السطر 47) فيُخرج على عدّاء Actions 1,642 صفحة فارغة بـrobots:{index:false} ولا يفشل — لأن fetchRoot تلتقط كل استثناء. وفوق ذلك تعرض 20 موضعًا بلا ترقيم (PAGE_SIZE=20 في السطر 43) و377 جذرًا يتجاوز العشرين وأقصاه 1,879 آية، فنقلها كما هي كان سيُثبّت نقصًا. الترقيم هنا على قائمة محمَّلة كاملة: بلا مسار واحد إضافي.

```
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { getMeta, rootOccurrences, type Meta } from "../lib/staticdata";

const STATUS_LABELS: Record<string, string> = {
  draft: "مسودة",
  imported: "مستورد — غير معتمد",
  machine_generated: "آلي فقط",
  under_review: "قيد المراجعة",
  approved: "معتمد",
  published: "منشور",
  disputed: "مختلف فيه",
  rejected: "مرفوض",
  deprecated: "متقادم",
};

const PAGE_SIZE = 20;

// انقل دالة AyahText من الملف القديم حرفيًا (تعرض النص كما هو وتميّز
// كلمات الجذر بالتقسيم على الفراغ وعدّ ما حمل حرفًا عربيًا).

type Payload = NonNullable<Awaited<ReturnType<typeof rootOccurrences>>>;

export default function RootPage() {
  const [root, setRoot] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Payload | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async (query: string, from: number) => {
    setError("");
    try {
      const [payload, info] = await Promise.all([
        rootOccurrences(query, from, PAGE_SIZE),
        getMeta(),
      ]);
      setMeta(info);
      if (!payload) {
        setData(null);
        setError("لم يُعثر على جذر بهذا الإدخال في هذه اللقطة.");
        return;
      }
      setData(payload);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const query = params.get("r") ?? "";
    const from = Math.max(0, Number(params.get("offset") ?? 0) || 0);
    if (!query) {
      setError("لا جذر في العنوان — الصيغة: /root?r=سمو");
      return;
    }
    setRoot(query);
    setOffset(from);
    load(query, from);
  }, [load]);

  function goto(next: number) {
    const url = new URL(window.location.href);
    url.searchParams.set("offset", String(next));
    window.history.pushState(null, "", url);
    setOffset(next);
    load(root, next);
  }

  if (error) {
    return (
      <main id="main" className="container">
        <div className="status-box error" role="alert">
          <p>
            {error} <Link href="/">جرّب البحث</Link>
          </p>
        </div>
      </main>
    );
  }
  if (!data) return <main id="main" className="container" />;

  const { root: info, occurrences, pagination } = data;
  const last = Math.max(0, pagination.total_ayahs - PAGE_SIZE);

  return (
    <main id="main" className="container">
      <nav className="crumbs">
        <Link href="/">البحث بالجذر</Link>
        <span aria-hidden="true">/</span>
        <span>الجذر {info.display_root}</span>
      </nav>

      <header className="analysis-header">
        <h1>
          الجذر <bdi>{info.display_root}</bdi>
        </h1>
        <p className="root-stats">
          {info.occurrence_count} موضعًا في {pagination.total_ayahs} آية
        </p>
        <span className="review-tag">
          {STATUS_LABELS[info.status] ?? info.status}
        </span>
      </header>

      <ol className="ayah-list">
        {occurrences.map((occ) => (
          <li key={`${occ.surah_number}:${occ.ayah_number}`} className="ayah-item">
            <p className="ayah-ref">
              سورة {occ.surah_name} — الآية {occ.ayah_number}
              <span className="ayah-ref-num">
                ({occ.surah_number}:{occ.ayah_number})
              </span>
            </p>
            <AyahText text={occ.uthmani_text} wordIndexes={occ.word_indexes} />
            <p className="ayah-actions">
              <Link href={`/ayah?s=${occ.surah_number}&a=${occ.ayah_number}`}>
                التحليل الصرفي ←
              </Link>
              {" · "}
              <Link href={`/mushaf/${occ.surah_number}#a${occ.ayah_number}`}>
                في سياق سورتها ←
              </Link>
            </p>
          </li>
        ))}
      </ol>

      {/* الترقيم كاملًا: 377 جذرًا يتجاوز العشرين وأقصاه 1,879 آية،
          والبتر عند 20 بلا ترقيم كان نقصًا مثبَّتًا. */}
      <nav className="ayah-actions" aria-label="تصفّح المواضع">
        {offset > 0 && (
          <button type="button" className="ghost" onClick={() => goto(Math.max(0, offset - PAGE_SIZE))}>
            → السابقة
          </button>
        )}
        <span>
          {offset + 1}–{offset + occurrences.length} من {pagination.total_ayahs}
        </span>
        {offset + PAGE_SIZE < pagination.total_ayahs && (
          <button type="button" className="ghost" onClick={() => goto(offset + PAGE_SIZE)}>
            التالية ←
          </button>
        )}
        {offset < last && (
          <button type="button" className="ghost" onClick={() => goto(last)}>
            الأخيرة ⇤
          </button>
        )}
      </nav>

      {meta && (
        <div className="status-box notice">
          <p>
            النص من مشروع تنزيل والجذور من المدونة القرآنية بجامعة ليدز —
            بيانات مستوردة موثقة ببصمات، حالتها{" "}
            <strong>{STATUS_LABELS[info.status] ?? info.status}</strong>، ولم
            تخضع بعد لمراجعة المنصة المزدوجة. لقطة ثابتة بتاريخ{" "}
            {meta.snapshot_at}. <Link href="/provenance">بيان الأصول الكامل</Link>
          </p>
        </div>
      )}
    </main>
  );
}

// ثم: Remove-Item -Recurse -Force 'apps/web/app/root/[root]'
```

### 10) apps/web/app/{page.tsx,compare/page.tsx,morphology/page.tsx,methodology/page.tsx,provenance/page.tsx}

**التغيير:** استبدل كل fetch(`${API_URL}…`) بنداء من staticdata، واحذف تعريف API_URL من الخمسة.

**لماذا:** الخمسة مكوّنات عميل أصلًا، فلا تحتاج تحويلًا: تحتاج مصدرًا آخر للبيانات فحسب. ومكوّنات العرض فيها (AyahText وSharedAyahText وMarkedAyah) هي التي تحمل منطق الخط الأحمر ولا تُمسّ بحرف. وعنوان API معرَّف حرفيًا في كل واحد منها بدل استيراده — فتصحيح lib/api.ts وحده كان سيتركها تنادي localhost صامتةً.

```
// ===== app/page.tsx (الرئيسة — البحث بالجذر) =====
// احذف السطرين 6-7 (API_URL) و REQUEST_TIMEOUT_MS و AbortController،
// واستبدل fetchOccurrences (140-181) بـ:
import { rootOccurrences } from "./lib/staticdata";

async function fetchOccurrences(rootQuery: string, offset: number) {
  const data = await rootOccurrences(rootQuery, offset, PAGE_SIZE);
  if (!data) throw new Error("لم يُعثر على جذر بهذا الإدخال في هذه اللقطة.");
  return data;
}
// وفي السطر 308 غيّر الرابط الثابت:
//   href={`/root?r=${encodeURIComponent(lastQueryRef.current)}`}
// وفي 360 و 366:
//   href={`/ayah?s=${occ.surah_number}&a=${occ.ayah_number}`}
//   href={`/mushaf/${occ.surah_number}#a${occ.ayah_number}`}   (كما هو)

// ===== app/compare/page.tsx =====
// احذف 6-7، واستبدل جسم run (97-116) بـ:
import { compareRoots } from "../lib/staticdata";

const run = useCallback(async (roots: string) => {
  setBusy(true);
  setError("");
  try {
    const payload = await compareRoots(roots, 30);
    if (!payload) {
      setError("لم يُعثر على أي من هذه الجذور في هذه اللقطة.");
      setData(null);
      return;
    }
    setData(payload);
  } catch (err) {
    setError((err as Error).message);
  } finally {
    setBusy(false);
  }
}, []);
// وفي 192 و 240:  href={`/root?r=…`}  و  href={`/ayah?s=…&a=…`}

// ===== app/morphology/page.tsx =====
// احذف 6-7، واستبدل useEffect (49-56) و search (58-91) بـ:
import { getLabels, searchMorphology } from "../lib/staticdata";

useEffect(() => {
  getLabels()
    .then((labels) => setDimensions(labels.dimensions))
    .catch(() => setError("تعذّر جلب أبعاد البحث."));
}, []);

const search = useCallback(
  async (offset = 0) => {
    const active = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v)
    ) as Record<string, string>;
    if (!Object.keys(active).length && !root.trim()) {
      setError("حدّد بُعدًا واحدًا على الأقل أو اكتب جذرًا.");
      setResults(null);
      return;
    }
    setBusy(true);
    setError("");
    try {
      setResults(await searchMorphology(active, root, offset, PAGE_SIZE));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  },
  [filters, root]
);
// وفي 215 و 225-231: href={`/root?r=…`} و href={`/ayah?s=…&a=…`}

// ===== app/methodology/page.tsx و app/provenance/page.tsx =====
// احذف تعريف API_URL، واستبدل fetch(`${API_URL}/methodology`) بـ
//   getMethodology()   و   fetch(`${API_URL}/export/provenance`) بـ
//   getProvenance()   من ../lib/staticdata.
// وأضف في صفحة بيان الأصول عرض snapshot_at وبصمات manifest.json:
//   const m = await getManifest();
//   → «لقطة ثابتة بتاريخ {m.built_at} · بصمة حزمة النص {m.sources[...]}»
// فيصير التزوير مكشوفًا: من عدّل نصًّا منشورًا خالفت بصمته البيان.
```

### 11) apps/web/app/lib/auth.tsx  +  apps/web/app/components/Header.tsx  +  apps/web/app/manifest.ts  +  apps/web/app/layout.tsx

**التغيير:** أوقف نداء /auth/me في الوضع الثابت، وأخفِ روابط الصفحات المحذوفة، وأصلح المسارات الحرفية التي لا يبدّلها basePath.

**لماذا:** AuthProvider ملفوف حول children في التخطيط الجذري فيعمل على كل صفحة عامة، ويطلب /auth/me من عنوان لن يوجد. ونزعه غير ممكن لأن Header يستدعي useAuth. وHeader يعرض /claims و/login دائمًا و/review و/admin/versions بشرط الدور — أربعتها ستصير 404. وNext يبدّل <Link> و_next/* تلقائيًا ولا يبدّل النصوص الحرفية: metadata.icons في layout.tsx (يتجاوز اصطلاح app/icon.svg فتسقط الأيقونات كلها) وstart_url وscope والأيقونات الأربع والاختصارات الثلاثة في manifest.ts.

```
// ===== app/lib/auth.tsx =====
// أضف فوق AuthProvider:
const STATIC = process.env.NEXT_PUBLIC_QSP_STATIC === "1";

// وفي refreshMe، أول سطر:
const refreshMe = useCallback(async () => {
  // الموقع الثابت بلا مصادقة ولا خدمة: الطلب هنا يخطئ حتمًا ويؤخر
  // أول رسم على كل صفحة عامة.
  if (STATIC) {
    setUser(null);
    setLoading(false);
    return;
  }
  if (!getAccessToken()) { /* … كما هو */ }
  /* … */
}, []);

// ===== app/components/Header.tsx =====
const STATIC = process.env.NEXT_PUBLIC_QSP_STATIC === "1";
// ثم لُفّ الروابط الأربعة:
//   {!STATIC && <Link href="/claims" className="nav-link">الادعاءات</Link>}
//   {!STATIC && user && <Link href="/review" …>صندوق المراجعة</Link>}
//   {!STATIC && hasRole(...MANAGE_ROLES) && <Link href="/admin/versions" …>}
//   {STATIC ? null : (loading ? null : user ? (<div className="user-chip">…) : (
//      <Link href="/login" className="nav-link primary-link">دخول</Link>))}

// ===== app/manifest.ts =====
import type { MetadataRoute } from "next";

// basePath لا يُطبَّق على المنيفست تلقائيًا — كل مسار هنا حرفي.
const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const STATIC = process.env.NEXT_PUBLIC_QSP_STATIC === "1";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "منصة الاستقراء الدلالي لجذور ألفاظ القرآن الكريم",
    short_name: "الاستقراء الدلالي",
    description:
      "منصة بحثية موثقة لدراسة جذور ألفاظ القرآن الكريم واستقراء استعمالاتها، بنص موثق ببصمة وتحليل منسوب لمصادره.",
    start_url: `${BASE}/`,
    scope: `${BASE}/`,
    display: "standalone",
    orientation: "portrait-primary",
    dir: "rtl",
    lang: "ar",
    categories: ["education", "books", "reference"],
    background_color: "#faf9f5",
    theme_color: "#1d5c42",
    icons: [
      { src: `${BASE}/icon.svg`, sizes: "any", type: "image/svg+xml" },
      { src: `${BASE}/icon-192.png`, sizes: "192x192", type: "image/png" },
      { src: `${BASE}/icon-512.png`, sizes: "512x512", type: "image/png" },
      {
        src: `${BASE}/icon-maskable-512.png`,
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
    shortcuts: [
      { name: "البحث بالجذر", short_name: "بحث", url: `${BASE}/` },
      { name: "فهرست المصحف", short_name: "المصحف", url: `${BASE}/mushaf` },
      { name: "بيان الأصول", short_name: "الأصول", url: `${BASE}/provenance` },
      // اختصار /claims يُسقط في الموقع الثابت: المسار غير موجود
      ...(STATIC
        ? []
        : [{ name: "الادعاءات البحثية", short_name: "الادعاءات", url: `${BASE}/claims` }]),
    ],
  };
}

// ===== app/layout.tsx (السطور 46-52) =====
// metadata.icons مسارات حرفية يتجاوز بها Next اصطلاح app/icon.svg،
// فتسقط الأيقونات كلها تحت basePath.
const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
//   icons: {
//     icon: [
//       { url: `${BASE}/icon.svg`, type: "image/svg+xml" },
//       { url: `${BASE}/icon-192.png`, sizes: "192x192", type: "image/png" },
//     ],
//     apple: `${BASE}/apple-touch-icon.png`,
//   },
```

### 12) apps/web/public/sw.js

**التغيير:** أعد كتابة عامل الخدمة على أساس «البيانات مثبَّتة بالبناء»: احذف الشيفرة الميتة، واشتقّ القاعدة من نطاق التسجيل، واستبدل addAll الذرّي.

**لماذا:** ثلاثة أعطاب مجتمعة: (1) cache.addAll ذرّي — أي عنصر من SHELL_ASSETS العشرة يعطي 404 يُبطل تخزين القشرة كلها، والسقوط مبتلَع في .catch(() => self.skipWaiting()) فيبدو التثبيت ناجحًا والمخزن فارغ ولا رسالة واحدة تشي بذلك؛ والمسارات المطلقة تفشل جميعها تحت basePath. (2) فرع /api/v1/ يصير شيفرة ميتة، ومعه isAuthRequest وفحص ترويسة authorization — شيفرة تُطمئن زورًا. (3) المعنى ينقلب: networkFirst بُنيت لأن الخادم قد يحمل أحدث، وفي الموقع الثابت البيانات مثبَّتة بالبناء فلا يمكن أن تكون أقدم من «الخادم»؛ الصواب مخزن أولًا لكل ما تحت data/v1/ وشبكة أولًا لـmanifest.json وحده. واشتقاق القاعدة من self.location يلغي كل حاجة إلى تمرير basePath هنا.

```
/* عامل الخدمة — الموقع الثابت.

   قاعدتان تحكمان ما يُخزَّن:

   1. **البيانات مثبَّتة بالبناء.** كل ما تحت `data/v1/` وُلِّد وقت البناء
      وبصمته في `manifest.json`، فلا يمكن أن يكون المخزَّن أقدم من
      «الخادم». المخزن أولًا، والشبكة لـ`manifest.json` وحده — به يُعرف
      أن لقطةً جديدة نُشرت.
   2. **لا شيء يُكتب.** الموقع بلا مصادقة ولا كتابة، فحُذف فرع
      `/api/v1/` و`isAuthRequest` وفحص ترويسة `authorization`: شيفرة
      ميتة تُطمئن زورًا.

   القاعدة تُشتق من موضع الملف نفسه، فتعمل على موقع المشروع
   (`/quran-semantic-platform/`) وموقع المستخدم (`/`) بلا تهيئة. */

const SCOPE = new URL("./", self.location.href);
const BASE = SCOPE.pathname;

// بصمة البناء تصل في عنوان التسجيل: `sw.js?v=<build>`.
// إن لم تُمرَّر NEXT_PUBLIC_BUILD_ID في سير النشر بقيت "dev" فبقيت
// النسخة qsp-dev أبدًا ولم يُبطَل مخزن القشرة قط عبر النشرات — وهو
// العطب المصحَّح في 2026-07-25 بعينه. سير Pages يمرّرها من github.sha.
const BUILD = new URL(self.location.href).searchParams.get("v") || "dev";
const VERSION = `qsp-${BUILD}`;
const SHELL_CACHE = `${VERSION}-shell`;
const DATA_CACHE = `${VERSION}-data`;

const SHELL_ASSETS = [
  "",
  "mushaf/",
  "methodology/",
  "privacy/",
  "terms/",
  "manifest.webmanifest",
  "icon.svg",
  "icon-192.png",
  "icon-512.png",
  "apple-touch-icon.png",
  // بيانات القشرة: بدونها لا يعمل شيء بلا اتصال (2,536 بايتًا مضغوطة)
  "data/v1/manifest.json",
  "data/v1/meta.json",
  "data/v1/surahs.json",
  "data/v1/normspec.json",
].map((path) => BASE + path);

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then(async (cache) => {
      // **لا `addAll`**: هي ذرّية، فأصل واحد مفقود يُفرغ المخزن كله
      // صامتًا. هنا كل أصل على حدة، والناقص يُسجَّل ولا يُبطل الباقي.
      const results = await Promise.allSettled(
        SHELL_ASSETS.map((url) =>
          cache.add(new Request(url, { cache: "reload" }))
        )
      );
      const missing = SHELL_ASSETS.filter(
        (_url, i) => results[i].status === "rejected"
      );
      if (missing.length) console.warn("[qsp] أصول قشرة لم تُخزَّن:", missing);
      await self.skipWaiting();
    })
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith("qsp-") && !key.startsWith(VERSION))
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response && response.ok) cache.put(request, response.clone());
  return response;
}

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((response) => {
      if (response && response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => cached);
  return cached || network;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (!url.pathname.startsWith(BASE)) return;

  // بيان اللقطة: الشبكة أولًا — به وحده يُعرف أن نشرةً جديدة صدرت
  if (url.pathname === `${BASE}data/v1/manifest.json`) {
    event.respondWith(networkFirst(request, DATA_CACHE));
    return;
  }

  // بقية البيانات: المخزن أولًا — مثبَّتة بالبناء وبصمتها في البيان
  if (url.pathname.startsWith(`${BASE}data/v1/`)) {
    event.respondWith(cacheFirst(request, DATA_CACHE));
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(async () => {
        const cache = await caches.open(SHELL_CACHE);
        return (await cache.match(request)) || (await cache.match(BASE));
      })
    );
    return;
  }

  event.respondWith(staleWhileRevalidate(request));
});
```

### 13) apps/web/app/components/AppShell.tsx

**التغيير:** سجّل عامل الخدمة على مسار القاعدة، وصحّح نص شارة انقطاع الاتصال ليصف الواقع.

**لماذا:** '/sw.js' مسار جذري لا يبدّله Next، فيفشل التسجيل تحت basePath. والأخطر أن نص الشارة صار إنذارًا كاذبًا: «قد تكون البيانات من مخزن الجهاز وليست أحدث ما على الخادم» بُني لأن الخادم قد يحمل أحدث؛ وفي الموقع الثابت البيانات مثبَّتة ببصمة البناء فالشارة تشكّك في بيانات صحيحة — وهو نقض لسياسة المنصة في إظهار الحالة كما هي.

```
// السطور 28-36:
      const build = process.env.NEXT_PUBLIC_BUILD_ID || "dev";
      const base = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
      navigator.serviceWorker
        .register(`${base}/sw.js?v=${encodeURIComponent(build)}`, {
          scope: `${base}/`,
        })
        .catch(() => {
          /* التسجيل ليس شرطًا لعمل الموقع */
        });

// السطور 44-48 — الشارة تصف الواقع لا خوفًا لا محل له:
  return (
    <div className="offline-bar" role="status">
      لا يوجد اتصال — المعروض من مخزن الجهاز، وبيانات هذه اللقطة مثبَّتة
      ببصمة البناء فهي كاملة لا ناقصة.
    </div>
  );
```

### 14) .github/workflows/pages.yml  (جديد)

**التغيير:** سير نشر مستقل: يولّد البيانات ثم يبني ثم يرفع artifact — بلا لمس ci.yml ولا الحاويات.

**لماذا:** البناء لا يخاطب الخدمة إطلاقًا: يقرأ الحزمتين. ولو خاطبها فحدّ 120 طلبًا لكل 60 ثانية (config.py:29-30) يجعل توليد 8,001 صفحة 67 دقيقة انتظارًا صرفًا. وupload-pages-artifact يتخطى Jekyll أصلًا ولا يلتزم شيئًا في المستودع، فتبقى 240 ملف بيانات + 252 قشرة خارج تاريخ Git. و.nojekyll احتياط: Jekyll يحذف كل مجلد يبدأ بشرطة سفلية — أي _next كاملًا — فيظهر الموقع بلا CSS ولا JS بلا رسالة خطأ. وNEXT_PUBLIC_BUILD_ID من github.sha: إغفاله يعيد بصمت العطب الموصوف في sw.js:12-15 بوصفه مُصلَحًا. وحارس الحجم يجعل تجاوز الميزانية خطأ بناء لا مفاجأة إنتاج.

```
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

env:
  # موقع مشروع: /quran-semantic-platform  ·  موقع مستخدم: اتركها فارغة
  BASE_PATH: /quran-semantic-platform

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Install API package (for app.utils.arabic)
        run: pip install -e apps/api

      # البيانات أولًا: البناء يقرأ surahs.json بـfs في generateStaticParams
      - name: Generate static data
        env:
          QSP_DATA_DIR: ${{ github.workspace }}/apps/api/data
        run: python scripts/export-static/build_data.py

      # حارس التطبيع: ثلاثة تنفيذات (بايثون، SQL، المتصفح) لا تفترق
      - name: Normalizer parity (browser vs python)
        working-directory: apps/api
        run: pytest tests/test_browser_normalizer_matches_python.py -q

      - name: No scripture in source
        working-directory: apps/api
        run: pytest tests/test_no_scripture_in_source.py -q

      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: apps/web/package-lock.json
      - name: Install
        working-directory: apps/web
        run: npm ci

      - name: Build static export
        working-directory: apps/web
        env:
          QSP_STATIC: "1"
          NEXT_PUBLIC_QSP_STATIC: "1"
          NEXT_PUBLIC_BASE_PATH: ${{ env.BASE_PATH }}
          # بصمة البناء — بها وحدها يُبطَل مخزن عامل الخدمة عند كل نشر
          NEXT_PUBLIC_BUILD_ID: ${{ github.sha }}
          NEXT_TELEMETRY_DISABLED: "1"
        run: npm run build

      # Jekyll يحذف كل مجلد يبدأ بشرطة سفلية — أي `_next` كله
      - name: Disable Jekyll
        run: touch apps/web/out/.nojekyll

      - name: Enforce size budget
        run: |
          BYTES=$(du -sb apps/web/out | cut -f1)
          FILES=$(find apps/web/out -type f | wc -l)
          echo "out/ = $BYTES bytes in $FILES files"
          # المقيس اليوم ≈ 22 م.ب في ≈ 500 ملف. السقف 100 م.ب يترك
          # هامشًا واسعًا ويكشف أي عودة إلى التوليد الشامل فورًا.
          test "$BYTES" -lt 104857600
          test "$FILES" -lt 3000
          test -f apps/web/out/data/v1/manifest.json
          test -f apps/web/out/mushaf/114/index.html
          test -f apps/web/out/404.html

      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: apps/web/out

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

### 15) apps/api/tests/test_browser_normalizer_matches_python.py  (جديد)

**التغيير:** حارس التكافؤ: يشغّل مفسّر المتصفح على Node ويقارن مخرجه بمخرج بايثون على كل حالة مولَّدة.

**لماذا:** التعليق في arabic.py:164 يسمّي عقد الهيكل ملزمًا بين بايثون وSQL ويحرسه test_skeleton_key_matches_its_sql_counterpart. إضافة تنفيذ ثالث للمتصفح بلا توسيع الحارس تعيد بالضبط الخطر الذي بُني له: «بحثًا يعيد صفرًا صامتًا بلا رسالة خطأ». شغّلتُ هذا الحارس فعلًا قبل كتابته: 26,913 حالة في الدوال الأربع و6,236 آية في الترميز — صفر اختلاف. وهو يفشل بصوت لو تغيّرت ثوابت arabic.py ولم يُعَد توليد normspec.json.

```
"""عقد التطبيع من تنفيذين إلى ثلاثة: بايثون، SQL، والمتصفح.

مواصفة `normspec.json` تُولَّد آليًا من ثوابت `app/utils/arabic.py`،
ويقرؤها مفسّر TypeScript عام لا يعرف العربية. هذا الاختبار يشغّل
المفسّر على Node ويقارن مخرجه بمخرج بايثون على:

  * كل آية من 6236،
  * كل كلمة مميزة من 19,002،
  * كل محرف من محارف المصحف وأزواج منها،
  * حالات عدائية (الصلوٰة، الربوٰا، شيـٔا، سبإ، %_/، فراغات مزدوجة).

وأربع دوال معًا: البحث، والهيكل، واسم السورة، ومفتاح الجذر — ومعها
مواضع الكلمات (`tokenize_ayah`).

بلا هذا الحارس ينحرف تطبيع الطلب عن تطبيع الفهرس بصمت، فيعيد البحث
صفرًا بلا رسالة خطأ — وهو عين ما يحذّر منه تعليق `normalize_search_skeleton`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "apps" / "web" / "public" / "data" / "v1"
LIB = REPO / "apps" / "web" / "app" / "lib" / "normalize.ts"

RUNNER = r"""
import fs from "node:fs";
import ts from "node:module";
const [specPath, goldPath, tokPath, libPath] = process.argv.slice(2);
const src = fs.readFileSync(libPath, "utf8")
  .replace(/export type [\s\S]*?\n};\n/g, "")
  .replace(/: [A-Za-z<>\[\]{}|,\s"']+(?=[),=;])/g, "")
  .replace(/export /g, "")
  .replace(/private |readonly /g, "");
const Normalizer = new Function(`${src}; return Normalizer;`)();
const spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
const n = new Normalizer(spec);
let diffs = 0;
for (const [inp, a, b, c, d] of JSON.parse(fs.readFileSync(goldPath, "utf8"))) {
  if (n.search(inp) !== a) diffs++;
  if (n.skeleton(inp) !== b) diffs++;
  if (n.surahName(inp) !== c) diffs++;
  if (n.rootInput(inp) !== d) diffs++;
}
let tokDiffs = 0;
for (const [text, spans] of JSON.parse(fs.readFileSync(tokPath, "utf8"))) {
  const got = n.tokenize(text);
  if (got.length !== spans.length ||
      got.some((g, i) => g.char_start !== spans[i][0] || g.char_end !== spans[i][1]))
    tokDiffs++;
}
console.log(JSON.stringify({ diffs, tokDiffs }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="Node غير متاح")
def test_browser_normalizer_matches_python_exactly(tmp_path: Path):
    for name in ("normspec.json", "normgold.json", "tokengold.json"):
        assert (DATA / name).exists(), (
            f"{name} غير مولَّد — شغّل scripts/export-static/build_data.py أولًا"
        )
    runner = tmp_path / "runner.mjs"
    runner.write_text(RUNNER, encoding="utf-8")
    result = subprocess.run(
        [
            "node",
            str(runner),
            str(DATA / "normspec.json"),
            str(DATA / "normgold.json"),
            str(DATA / "tokengold.json"),
            str(LIB),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["diffs"] == 0, (
        f"تطبيع المتصفح يفترق عن بايثون في {report['diffs']} حالة — "
        "أعد توليد normspec.json أو صحّح المفسّر."
    )
    assert report["tokDiffs"] == 0, (
        f"مواضع الكلمات تفترق في {report['tokDiffs']} آية — "
        "التمييز سيقع على كلمة غير التي طابقت."
    )

```

### 16) apps/api/tests/test_no_scripture_in_source.py

**التغيير:** وسّع الحارس ليغطي الثغرة التي كشفها هذا التصدير: ملفات .json و.txt داخل apps/web/app.

**لماذا:** الحارس اليوم يمسح apps/web/app بلاحقات {.tsx,.ts,.jsx,.js,.py,.css,.html} ولا .json فيها. فمجلد الخرج apps/web/out خارج المسح، وملفات apps/web/public/data/v1/*.json خارجه مرتين — بالموضع وبالامتداد. لكن ملف .json يُوضع **داخل** app/ لن يفحصه الحارس أصلًا — وهي ثغرة صامتة تفتحها هذه المرحلة بالضبط، لأنها تُدخل ملفات بيانات إلى المشروع لأول مرة. والأمان يجب أن يقوم على شرطين مستقلين لا على شرط واحد.

```
# 1) أضف بعد SCANNED_SUFFIXES:

# الحارس الثاني: البيانات لا تسكن شجرة الشيفرة.
#
# التصدير الثابت (2026-07) أدخل ملفات بيانات إلى المشروع لأول مرة،
# فانكشفت ثغرة: ملف `.json` **داخل** `apps/web/app` لا يفحصه المسح
# أعلاه (اللاحقة خارج SCANNED_SUFFIXES). والأمان يقوم على شرطين
# مستقلين معًا: الامتداد `.json`، والموضع خارج `app/`. سقوط أحدهما
# وحده لا يكفي إن تغيّر الآخر لاحقًا.
DATA_SUFFIXES = {".json", ".txt", ".csv", ".ndjson"}


def _scan_data(root: Path) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in DATA_SUFFIXES:
            continue
        if set(path.parts) & set(EXCLUDED_ANYWHERE):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        relative = path.relative_to(REPO_ROOT).as_posix()
        for number, line in enumerate(text.splitlines(), 1):
            if SCRIPTURE.search(line):
                hits.append((relative, number, line.strip()[:120]))
    return hits


# 2) أضف اختبارين جديدين:

def test_no_scripture_in_data_files_inside_the_app_tree():
    """ولا في ملفات بيانات داخل شجرة الواجهة — البيانات مكانها public/.

    شجرة البيانات المولَّدة تسكن `apps/web/public/data/v1/` حصرًا:
    خارج `apps/web/app` (موضعًا) وبامتداد `.json` (لاحقةً). أي نص
    يظهر تحت `app/` — بأي امتداد — خرقٌ للخط الأحمر الأول."""
    hits = _scan_data(REPO_ROOT / "apps" / "web" / "app")
    assert not hits, _fail(hits, "ملفات بيانات داخل شجرة الواجهة")


def test_generated_data_lives_outside_the_scanned_tree():
    """وشجرة البيانات المولَّدة `.json` كلها ولا وحدة برمجية فيها.

    لو وُلِّدت البيانات وحدةَ TypeScript (مثل `app/data/surahs.ts`)
    لسقط الحارس فورًا — وذلك هو الصواب. وهذا الاختبار يمنع الوصول
    إلى تلك الحالة أصلًا: المولّد يكتب `.json` فقط، وخارج `app/`."""
    out = REPO_ROOT / "apps" / "web" / "public" / "data"
    if not out.exists():
        pytest.skip("البيانات غير مولَّدة في هذه البيئة")
    bad = [
        p.relative_to(REPO_ROOT).as_posix()
        for p in out.rglob("*")
        if p.is_file() and p.suffix != ".json"
    ]
    assert not bad, f"ملفات غير .json في شجرة البيانات: {bad}"
    assert not (REPO_ROOT / "apps" / "web" / "app" / "data").exists()


# 3) وفي أعلى الملف: import pytest
```

### 17) apps/api/app/services/quran.py  +  apps/api/app/utils/arabic.py

**التغيير:** صحّح التعليقين اللذين صارا يصفان واقعًا انتهى: تنفيذ التطبيع لم يعد اثنين.

**لماذا:** تعليق _filter_surahs (السطر 42) يقول «التطبيع تنفيذ واحد في بايثون بلا نظير له في TypeScript»، وتعليق normalize_search_skeleton (السطر 164) يسمّي العقد بين بايثون وSQL. وقد صار التنفيذ ثالثًا. تعليقٌ يصف واقعًا انتهى أخطر من غياب التعليق: يقرؤه قارئ لاحق فيظنّ الحماية قائمة حيث زالت — وهذا بعينه هو الصنف الذي حذّر منه فحص 2026-07-25.

```
# ===== apps/api/app/utils/arabic.py — التعليق فوق normalize_search_skeleton =====
#     """مفتاح المطابقة التقريبية — للبحث فقط، ولا يُعرض نصًّا أبدًا.
#
#     **عقد ملزم من ثلاثة تنفيذات:**
#       1. هذه الدالة (بايثون)،
#       2. تعبير SQL في `QuranService._skeleton_expr()` على
#          `Ayah.plain_search_text`،
#       3. مفسّر المتصفح `apps/web/app/lib/normalize.ts` الذي يقرأ
#          `normspec.json` المولَّد من ثوابت هذا الملف وقت البناء.
#
#     أي فرق بين الثلاثة يعني بحثًا يعيد صفرًا صامتًا بلا رسالة خطأ.
#     يحرس (1)+(2) `test_skeleton_key_matches_its_sql_counterpart`،
#     ويحرس (1)+(3) `test_browser_normalizer_matches_python`
#     على 26,913 حالة — كل الآيات وكل الكلمات المميزة وكل المحارف.
#     ومن غيّر ثوابت هذا الملف فعليه إعادة توليد `normspec.json`،
#     وإلا حُمِّر البناء."""

# ===== apps/api/app/services/quran.py — تعليق _filter_surahs (السطر 42) =====
#     """ترشيح السور بالرقم أو بمفتاح الاسم.
#
#     التطبيع نفسه (`normalize_surah_name`) تنفيذٌ واحد في بايثون:
#     في الخدمة الحية يقع الترشيح كله هنا، وفي الموقع الثابت تُشحن
#     **مفاتيح الأسماء محسوبةً في بايثون** داخل `surahs.json`
#     (حقل `key`)، ويُطبَّع **الطلب وحده** في المتصفح. فلا يوجد في
#     الحالتين تطبيعٌ ثانٍ للأسماء المخزَّنة يمكن أن يفترق عن هذا.
#     … (بقية التعليق كما هو: الاتجاه مقصود، الترتيب، الأرقام) """
```

### 18) .gitignore  +  docs/DEPLOYMENT_AR.md

**التغيير:** استثنِ مخرجات البناء والبيانات المولَّدة من Git، وثبّت حدود Pages بأرقامها ومصدرها وتاريخ قراءتها.

**لماذا:** .gitignore لا يذكر out/ ولا public/data/، فبناء محلي واحد يترك ≈22 م.ب من HTML يحمل النص القرآني و13 م.ب من البيانات بلا تتبّع في نسخة العمل، عرضةً لالتزام بالخطأ يضخّم تاريخ Git بلا رجعة (البيانات تُعاد توليدها مع كل إصدار). و*.db يغطي app.db (114,315,264 بايتًا) لكن الاستثناء يجب أن يكون صريحًا في مسار النشر أيضًا: لو تسلّل أكل عُشر حدّ الغيغابايت وسرّب الجزء غير العام. والحدود تتغيّر والمشروع يُبنى ليبقى، فتُدوَّن بمصدرها لا من الذاكرة.

```
# ===== إضافة إلى .gitignore =====

# مخرجات التصدير الثابت — تُبنى في سير النشر وتُرفع artifact، ولا تُلتزم.
# بناء محلي واحد يترك ≈22 م.ب من HTML يحمل النص القرآني بلا تتبّع.
/apps/web/out/
/apps/web/.next-prod/

# شجرة البيانات المولَّدة (240 ملفًا، ≈13 م.ب) — تُشتق من الحزمتين
# الموثقتين بأمر واحد، وإدخالها في التاريخ يضخّمه مع كل إصدار بيانات.
/apps/web/public/data/

# ===== إضافة إلى docs/DEPLOYMENT_AR.md =====
#
# ## النشر الثابت على GitHub Pages
#
# ### الحدود الرسمية (مقروءة من
# ### docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
# ### بتاريخ 2026-07-25 — تُراجَع سنويًا)
#
# | الحدّ | القيمة | نوعه | نصيبنا المقيس |
# |---|---|---|---|
# | حجم الموقع المنشور | 1 غيغابايت | صارم | ≈22 م.ب = **2.2%** |
# | النطاق الشهري | 100 غيغابايت | ليّن | ≈275,000 زيارة باردة |
# | مهلة النشر | 10 دقائق | صارم | البناء ≈3 دقائق |
# | عمليات البناء | 10/ساعة | ليّن | لا يسري مع Actions مخصّصة |
#
# ### تفصيل الحجم (مقيس على الحزمتين، لا مقدَّرًا)
#
# * شجرة البيانات: **240 ملفًا، 13,796,442 بايتًا خامًا، 2,283,106 مضغوطة**.
# * قشور Next: 126 مسارًا × 47,893 بايتًا = ≈6.0 م.ب.
# * حزم JS/CSS/الخطوط: ≈3 م.ب.
#
# ### لماذا 126 مسارًا لا 8,001
#
# توليد صفحة لكل آية وجذر = 16,002 ملفًا في 175–351 م.ب، وزمن حزم ورفع
# 8–20 دقيقة مقابل مهلة `actions/deploy-pages` عشر دقائق. ونصيب
# `[root]` و`[surah]/[ayah]` وحدهما 7,878 من 8,001 (98.5%) = 377 م.ب.
# فحُوِّلا إلى معاملات استعلام، وبقي `/mushaf/[surah]` (114 مسارًا =
# 5.5 م.ب) لأنه الرابط المستشهد به والوحيد الذي يكسب بطاقة وصفية حقيقية.
#
# ### ما لا يجوز نسيانه
#
# * `NEXT_PUBLIC_BUILD_ID` من `github.sha` — بغيره تبقى نسخة عامل الخدمة
#   `qsp-dev` أبدًا فلا يُبطَل المخزن عبر النشرات (العطب المصحَّح 2026-07-25).
# * `.nojekyll` في جذر الخرج — Jekyll يحذف `_next` كله بلا رسالة.
# * لا تُشحن ملفات `.gz` ولا `.br`: Pages لا يضع لها `Content-Encoding`
#   فيصل المتصفحَ ركامٌ. Pages يضغط gzip بنفسه (متحقَّق منه)، ولا brotli.
# * `apps/api/data/app.db` (114 م.ب) لا يدخل مسار النشر بحال.
#
# ### قياس زمن البناء الحقيقي (لم يُقَس بعد)
#
# لا يوجد على القرص بناء إنتاجي (`.next/BUILD_ID` غير موجود). لقياسه
# **بأمان** بينما خادم التطوير يعمل — فالبناء على `.next` المشغول هو
# العطب الذي سبق وقوعه في هذا المشروع — استعمل مجلدًا منفصلًا:
#
#     $env:QSP_STATIC='1'; $env:QSP_DIST='.next-prod'; npm run build
#
# (أضف في next.config.ts: `distDir: process.env.QSP_DIST ?? ".next"`)
# وسجّل الرقم هنا ليصير مرساةً لكل تقدير لاحق.
```

## حراسة الخطوط الحمراء

1. **النص لا يُعاد تركيبه ولا يُكتب في الشيفرة — محروسًا في أربعة مواضع:** (1) المولّد ينسخ سلسلة الآية من الحزمة كما هي ولا يمرّرها على أي دالة: `write(f"text/s{n}.json", [text for _s, _a, text in chunk])`؛ (2) `staticdata.ts` يمرّرها إلى العرض سلسلةً واحدة ولا يقسمها؛ (3) مكوّنات العرض الأربعة (`MarkedAyah` في mushaf/page.tsx، و`renderAyah` في SurahView و/ayah، و`AyahText` في page.tsx و/root، و`SharedAyahText` في /compare) تُنقل **حرفيًا** بلا تعديل — وهي التي تقطّع `uthmani_text` بمواضع الحروف فيخرج ما بين الكلمات (علامات الوقف ورموز نهاية الآية والفراغات) كما هو؛ (4) `test_no_scripture_in_source.py` يبقى أخضر ويتوسّع.
2. **مواضع الحروف مشتقّة من النص المشحون نفسه، فلا مصدر ثانٍ يمكن أن يفترق عنه:** `Normalizer.tokenize` يعيد `char_start/char_end` فقط ولا يعيد نصًّا. قِستُ تطابقه مع `tokenize_ayah` على المصحف كله: **6,236 آية، 77,433 رمزًا، صفر اختلاف**. والنتيجة أن التمييز مستحيل بنيويًا أن يقع خارج نص الآية المعروض — بخلاف شحن المواضع مصفوفةً منفصلة (كان سيكلف 113,544 بايتًا مضغوطة ويفتح باب الانحراف).
3. **التطبيع للبحث لا للعرض، ولا يُطبَّع نصُّ مصحف في المتصفح قط:** مفاتيح البحث الـ6,236 محسوبة في بايثون بـ`normalize_arabic_search` نفسها المستعملة في البذر ومشحونة في `norm.json`؛ والمتصفح يطبّع **سلسلة الطلب وحدها**. فلو انحرف تطبيع الطلب يومًا فأسوأ ما يقع نتيجةٌ ناقصة يراها المستعمل — لا نصٌّ مخزَّن مشوَّه.
4. **عقد التطبيع من تنفيذين إلى ثلاثة، معلنًا ومحروسًا:** `normspec.json` (944 بايتًا) مولَّد آليًا من ثوابت `arabic.py` لا مكتوب يدويًا، و`normalize.ts` مفسّر عام لا يحمل قاعدة عربية واحدة. شغّلتُ الحارس فعلًا: **26,913 حالة × 4 دوال (البحث، الهيكل، اسم السورة، مفتاح الجذر) = صفر اختلاف**، و**6,236 آية ترميزًا = صفر اختلاف**. وتعليقا `arabic.py:164` و`quran.py:42` يُصحَّحان ليسمّيا التنفيذ الثالث — فلا يظنّ قارئ لاحق الحمايةَ قائمةً حيث زالت.
5. **عقد التمييز محروس في المولّد نفسه:** يؤكّد أن `normalize_arabic_search(نص الآية).split(' ')` يوافق `tokenize_ayah` كلمةً بكلمة في الآيات الـ6,236 كلها (قِسته: صفر اختلاف، 4,578 جزءًا غير كلمة يُبتلع في ضغط الفراغات، وصفر رمزٍ يطبَّع إلى فراغ). لولاه لَوقع تمييز نتائج البحث على كلمة غير التي طابقت — فشلٌ صامت لا رسالة فيه.
6. **سلسلة السمات تبقى حرفيًا كما وردت (شرط رخصة المدونة القرآنية):** `morph/dims.json` يحمل السلسلة الأصلية في العمود الأول والأبعاد المشتقة بعدها — فهرسة فوقها لا تعديل فيها. والمولّد يؤكّد أنها دالّة أحادية القيمة (12,405 سلسلة مميزة، صفر تعارض في tag/pos/lemma/lemma_index/root_ar/root_key)، و`ayahAnalysis` يعرضها بـ`<code dir="ltr">` كما تُعرض اليوم.
7. **كل مخرَج يحمل مصدره وحالة مراجعته وبصمته:** `manifest.json` يحمل بصمة sha256 لكل ملف مُخرَج، وبصمات الحزمتين المصدريتين، والبصمات المعلنة داخلهما للملفات الأصلية الثلاثة، وتاريخ اللقطة. وكل شاشة تعرض `data_release` و`review_status` و`snapshot_at` — لا صفحة بيان الأصول وحدها. فمن عدّل نصًّا منشورًا خالفت بصمته البيان.
8. **تاريخ اللقطة ظاهر لأن اللقطة تجمّد حالةً قد تتقدّم:** حالة المراجعة اليوم `imported`/`machine_only` وكل المواضع الـ49,968 «مصدر صرفي واحد بلا شاهد ثانٍ». لو اعتُمدت قرارات لاحقًا في النسخة المحلية ولم يُعَد النشر، عرض الموقع حالةً أقدم من الحقيقة وهو يدّعي أنها الحالة. ولذلك `decision: null` صريح في `ayahAnalysis` مع تعليق يقول لماذا، و`snapshot_at` في كل شاشة تحمل مخرَجًا.
9. **البيانات لا تسكن شجرة الشيفرة، بشرطين مستقلين:** `.json` حصرًا (يؤكده المولّد في `write` ويحرسه اختبار جديد)، وموضعٌ في `apps/web/public/data/v1/` خارج `apps/web/app` (يحرسه اختبار جديد يمسح `.json/.txt/.csv/.ndjson` داخل `app/` بالسمة نفسها). سقوط أحد الشرطين وحده لا يكفي إن تغيّر الآخر لاحقًا — وهذا هو سدّ الثغرة التي تفتحها هذه المرحلة بعينها.
10. **`test_no_scripture_in_source.py` يبقى أخضر — وهذا برهانه:** دالتا الفحص تمسحان `apps/web/app` و`apps/api/app` فقط، و`SCANNED_SUFFIXES = {.tsx,.ts,.jsx,.js,.py,.css,.html}` ولا `.json` فيها. فشجرة البيانات في `apps/web/public/data/v1/` خارج المسح **مرتين** (بالموضع وبالامتداد)، ومجلد الخرج `apps/web/out` خارجه بالموضع. ولا يُولَّد ملف `.ts` ولا `.js` يحمل نصًّا في أي خطوة — لو وُلِّد (مثل `app/data/surahs.ts`) لسقط الحارس فورًا، وذلك هو الصواب. والملفات التي تُمسّ في هذه المواصفة (`next.config.ts`, `normalize.ts`, `staticdata.ts`, الصفحات, `sw.js`, `manifest.ts`) لا يدخلها حرف قرآني مشكَّل: الأمثلة في التعليقات مراجع رقمية (`2:255`) لا اقتباسات، والنصوص العربية فيها نثر واجهة غير مشكَّل. والاستثناء الوحيد يبقى محصورًا بـ`apps/api/app/content/methodology.py` — و`test_the_exemption_list_stays_narrow` يمنع توسيعه بلا تعديل متعمَّد. وسير النشر يشغّل هذا الاختبار قبل البناء، فالخرق يوقف النشرة.

## المخاطر المسجَّلة

1. **العرض المبتور صار كاملًا فظهر حِمل جديد:** صفحة الجذر كانت تعرض 20 موضعًا فقط بلا ترقيم، والآن تُحمَّل قائمة الجذر كاملة في الذاكرة. أثقل حالة «اله» = 1,879 آية. الترقيم يبقى 20 لكل صفحة فلا تُرسم آلاف العناصر، لكن `roots.json` كاملًا 167,543 بايتًا مضغوطة يُحمَّل عند أول بحث بالجذر. مقبول (يُخزَّن بعدها)، لكن يجب قياس أول رسم على هاتف بطيء قبل الإعلان.
2. **الترميز الست عشري للجذور مرفوض عمدًا بكلفة 57 ك.ب:** `roots.txt` بالدلتا يزن 110,226 مقابل 167,543 لـ`roots.json` العادي. رفضتُه لأن مرمِّزًا مخصّصًا يحتاج مراجعةً وحارسًا، والفرق يقع مرةً واحدة كسولًا. إن ثقُل على شبكات بطيئة فالتغيير محصور في دالتين (`getRoots` والمولّد) ويلزمه اختبار تكافؤ.
3. **البحث النصي مسح خطي على 6,236 سطرًا في الخيط الرئيس.** قِيس في جولة سابقة 0.4–2.5 مللي ثانية، لكنه لم يُقَس على هاتف ضعيف مع `skeletonOf` يُستدعى لكل سطر. إن ثقُل فالعلاج المحفوظ للدلالة هو شحن طبقة الهيكل محسوبةً من بايثون (160,023 بايتًا مضغوطة) لا فهرسًا مقلوبًا — فالفهرس الكلمي يغيّر الدلالة صامتًا من «تضمين داخل الكلمة» إلى «كلمة»، وهو عين ما حذّر منه تعليق `normalize_search_skeleton`.
4. **تغيير شكل الروابط يكسر ما بُني عليه، ولا يجوز أن يقع مرتين.** `/root/{جذر}` و`/ayah/{س}/{آ}` يصيران `/root?r=` و`/ayah?s=&a=`. الموقع لم يُنشر بعدُ فلا رابط عامًّا يُكسر اليوم — لكن بعد النشر يصير الكسر دائمًا. فليُحسم شكل العناوين **قبل** أول نشرة، وليُذكر صراحةً في صفحة المنهج أنه شكل الاستشهاد المعتمد.
5. **فقدان الفهرسة لصفحات الآيات والجذور.** بعد التحويل تبقى 114 صفحة سورة مفهرسة ببطاقات وصفية حقيقية، وتصير 6,236 آية و1,642 جذرًا وراء معاملات استعلام لا تفهرسها محركات البحث. هذا ثمن مقصود مقابل 377 م.ب — لكنه ثمن: مَن يبحث عن جذر في محرك بحث لن يجد صفحته. البديل الوحيد الذي يستعيدها بلا انفجار هو خريطة موقع + عرض على الخادم، وكلاهما خارج الموقع الثابت.
6. **`morph/s2.json` وحده 88,504 بايتًا مضغوطة (686,700 خامًا).** فتح تحليل أي آية من البقرة يجلب صرف السورة كلها. الوسيط 6,044 والحالة نادرة، لكن البقرة أكثر السور فتحًا. إن ثقُل، فالتقسيم إلى كتل من 32 آية داخل السور الكبرى وحدها علاجٌ موضعي — والتقسيم لكل آية مرفوض بالقياس (3.65 م.ب مقابل 1.22).
7. **زمن البناء لم يُقَس ولم أُشغّله** (خادم التطوير يعمل والبناء على `.next` المشغول هو العطب الذي سبق وقوعه). التقدير: ≈3 دقائق (126 مسارًا + توليد بيانات ≈40 ثانية) مقابل مهلة نشر عشر دقائق — هامش مريح لكنه غير مبرهن. أول ما يُفعل بعد إقرار المواصفة: قياسه في `distDir` منفصل وتسجيله في `docs/DEPLOYMENT_AR.md`.
8. **اختبار التكافؤ يزيل الأنواع من `normalize.ts` بتعابير نمطية** ليشغّله على Node بلا مترجم TypeScript. هذا هشّ: تركيب جديد في الملف قد يكسر التجريد فيسقط الاختبار لسبب غير الذي بُني له. الأمتن تشغيله عبر `tsx` أو `esbuild` كتبعية تطوير — أُجّل لأنه يضيف تبعية إلى `apps/web` من أجل اختبار في `apps/api`. إن تكرر السقوط فليُبدَّل.
9. **اللقطة تجمّد حالة مراجعة قد تتقدّم بلا نشر.** الحالة اليوم `imported`/`machine_only`، وقرارات المنصة تُتَّخذ في النسخة المحلية ولا تدخل الحزمتين. `snapshot_at` ظاهر في كل شاشة و`decision: null` صريح — لكن لا آلية تنبّه إن تخلّفت اللقطة عن الحقيقة شهورًا. يلزم قرار تشغيلي: نشرة دورية أو وسمٌ يقول «عمر هذه اللقطة كذا».
10. **`morph/labels.json` يُشتق من `morphology_tags.py` وقت البناء، وليس عليه حارس تكافؤ.** لو أُضيف وسم أو بُعد ولم يُعَد توليد البيانات، عرضت الواجهة وسمًا خامًا بدل تسميته العربية — وهو تدهور صامت لا يكسر شيئًا فلا يُنتبه له. علاجه سطر في اختبار موجود يقارن عدد الوسوم في الملف المولَّد بـ`len(POS_LABELS_AR)`.
11. **نطاق عامل الخدمة على موقع المستخدم يشمل الأصل كله.** اخترتُ موقع المشروع (`BASE_PATH=/quran-semantic-platform`) لهذا السبب تحديدًا: لو نُشر على `hasanawida.github.io` مباشرةً لسيطر العامل على كل مواقع المشاريع الأخرى في الحساب نفسه، فصار المخزن المشترك بينها مصدر تشويش. التحويل إلى موقع المستخدم يبقى ممكنًا بتفريغ `BASE_PATH` — لكن ليكن قرارًا يُتَّخذ لا أثرًا جانبيًا.
12. **GitHub Pages لا يسمح بترويسة واحدة:** `Strict-Transport-Security` في `ops/Caddyfile:44` و`Cache-Control: no-store` على مسارات المصادقة يسقطان. الأثر محدود لأن الموقع بلا مصادقة ولا كتابة، لكن أي CSP لن تكون إلا `<meta http-equiv>` ناقصة — فليُذكر ذلك في `docs/SECURITY_AR.md` بدل السكوت عنه.
13. **`next/font/google` هي تبعية الشبكة الوحيدة التي يجب أن تنجح في CI.** فشلها لا يُسقط البناء بالضرورة بل قد يُخرج موقعًا بخطوط بديلة — وفي واجهة عربية RTL بخط عثماني (Amiri) هذا تشويه بصري صامت للنص القرآني نفسه. يلزم تحقّق في سير النشر أن ملفات الخطوط ظهرت في `out/_next/static/media/`.
