"""الخط الأحمر الأول، محروسًا آليًا: لا نص قرآني مكتوب في الشيفرة.

القاعدة (docs/SCIENTIFIC_SAFETY.md): النص القرآني لا يُولَّد ولا يُكتب
يدويًا ولا يُعاد تركيبه — يدخل المنصة من ملف مصدري ببصمته عبر مسار
استيراد موثق، ويُقرأ من سجل الآية المرتبط بالإصدار النشط.

**لماذا صار الحرس آليًا:** فحص جاهزية النشر في 2026-07-25 وجد في
`apps/web/app/admin/versions/page.tsx` زرًّا يبني إصدار نص من آيتين
مكتوبتين نصًّا في الملف، باسم مصدر «إدخال تجريبي»، مشحونًا في حزمة
الإنتاج. مرّ ذلك شهورًا لأن لا شيء كان يفحصه.

**سمة الكشف:** ثلاثة أحرف عربية مشكَّلة متتابعة. اختيرت بعد تجريب:
- «حرف + تشكيل» وحده يُنذر زورًا — الشدّة ترد في نثر عربي عادي («تحقّق»).
- وجود «ٱ» وحده يُنذر زورًا — يرد في أصناف المحارف وجداول التطبيع.
- أما ثلاثة متتابعة (بِسْمِ) فلا تقع إلا في نص مشكَّل بالكامل.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

ARABIC_LETTER = "ء-يٱ"
DIACRITIC = "ً-ْٰۖ-ۭ"
SCRIPTURE = re.compile(f"(?:[{ARABIC_LETTER}][{DIACRITIC}]){{3}}")

# مجلدات لا تُفحص: مولَّدة أو خارجية أو هي مصدر النص أصلًا
EXCLUDED_ANYWHERE = (
    ".git",
    "node_modules",
    ".venv",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
)

SCANNED_SUFFIXES = {".tsx", ".ts", ".jsx", ".js", ".py", ".css", ".html"}

# الاستثناء الوحيد، ومحصور بملف واحد بحجّته:
#
# `app/content/methodology.py` نثرٌ تحريري يُعرض في صفحة المنهج، وفيه
# موضع خلاف «حدود الكلمة» — ولا سبيل إلى شرحه دون تسمية الكلمتين
# المتنازع في عدّهما. والاقتباس هنا **هو موضوع الكلام** لا بيانًا.
#
# ولا خطر فيه: هذا الملف ثوابت عرض، لا يمرّ بمسار استيراد، ولا يمكن أن
# يصير سجل آية. الخطر الذي بُني له هذا الحارس كان زرًّا يبني **إصدار نص**
# من كلام مكتوب في الشيفرة — وذلك ممنوع بلا استثناء.
EXEMPT_FILES = {"apps/api/app/content/methodology.py"}


def _scan(root: Path) -> list[tuple[str, int, str]]:
    hits: list[tuple[str, int, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in SCANNED_SUFFIXES:
            continue
        parts = set(path.parts)
        if parts & set(EXCLUDED_ANYWHERE):
            continue
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative in EXEMPT_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if SCRIPTURE.search(line):
                hits.append((relative, number, line.strip()[:120]))
    return hits


def _fail(hits: list[tuple[str, int, str]], where: str) -> str:
    listing = "\n".join(f"  {f}:{n} — {s}" for f, n, s in hits)
    return (
        f"نص قرآني مشكَّل في {where}:\n{listing}\n\n"
        "النص يُقرأ من سجل الآية لا يُكتب في الشيفرة. إن كان مثالًا "
        "توضيحيًا فأشر إلى موضعه (مثل «20:94») بدل اقتباسه."
    )


def test_no_scripture_in_the_web_bundle():
    """شيفرة الواجهة بلا نص مشكَّل — فلا شيء منه يُشحن إلى المتصفح."""
    hits = _scan(REPO_ROOT / "apps" / "web" / "app")
    assert not hits, _fail(hits, "شيفرة الواجهة")


def test_no_scripture_in_the_api_service_layer():
    """وشيفرة الخدمة كذلك: النص يأتي من القاعدة لا من ثابت في الشيفرة."""
    hits = _scan(REPO_ROOT / "apps" / "api" / "app")
    assert not hits, _fail(hits, "شيفرة الخدمة")


def test_the_guard_detects_scripture_and_spares_ordinary_arabic():
    """حارس لا يكشف ما بُني له حارسٌ زائف — يُختبر الكاشف نفسه."""
    # الآيتان اللتان كانتا مكتوبتين في الواجهة قبل حذفهما
    assert SCRIPTURE.search("بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ")
    assert SCRIPTURE.search("ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَٰلَمِينَ")

    # ونصوص الواجهة العربية العادية لا تُنذر
    assert not SCRIPTURE.search("إدارة إصدارات النص — تحقّق بنيوي")
    assert not SCRIPTURE.search("البحث بالجذر في المصحف")
    assert not SCRIPTURE.search("لا يعتمد مراجع عمله، ويلزم مراجعان مختلفان")

    # ولا أصناف المحارف وجداول التطبيع — وهي شيفرة لا نص
    assert not SCRIPTURE.search("const ARABIC_LETTER = /[ء-يٱ]/;")
    assert not SCRIPTURE.search('"ٱ": "ا",  # همزة وصل')


def test_the_exemption_list_stays_narrow():
    """الاستثناء يبقى محصورًا: ملف عرض واحد، لا مجلد ولا نمط.

    استثناء يتوسّع بلا حساب يُبطل الحارس بهدوء — فيُثبَّت عدده هنا،
    ويلزم تعديل هذا الاختبار عمدًا لتوسيعه."""
    assert EXEMPT_FILES == {"apps/api/app/content/methodology.py"}
    # وملفات الاستيراد والنماذج والخدمات لا استثناء فيها بحال
    assert not any("services" in path or "models" in path for path in EXEMPT_FILES)
