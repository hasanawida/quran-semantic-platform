"""مواضع حزم البيانات — محلولة بلا اعتماد على طريقة التثبيت.

**لماذا هذا الملف موجود:** كان كل مستهلك يشتق مجلد البيانات بنفسه من
`Path(__file__).resolve().parents[2] / "data"`. وهذا صحيح **فقط** حين
تكون الحزمة مثبتة تثبيتًا قابلًا للتحرير أو مشغَّلة من شجرة المصدر:

- محليًا (تثبيت `-e`) يشير `__file__` إلى الشجرة ⇒ يعمل.
- في CI (تثبيت ناسخ) يشير إلى `site-packages` ⇒ `site-packages/data`
  غير موجود، فسقط 99 اختبارًا بـ`BUNDLE_MISSING` في أول تشغيل لـCI.
- وفي صورة الإنتاج يعمل **بالمصادفة**: مجلد العمل `/app` يسبق
  `site-packages` في مسار البحث فتُحلّ `app` من الشجرة المنسوخة التي
  يجاورها `data`. اعتمادٌ على ترتيب المسار لا على تصميم.

فالحلّ هنا: البحث في مواضع مرتَّبة، مع تجاوز صريح بمتغير بيئة، ورسالة
خطأ **تسمّي ما بُحث فيه** — الرسالة القديمة كانت تقول «غير موجودة» ولا
تقول أين، فأخذ تشخيصها وقتًا لا يُبذل.

وحزم البيانات ليست تفصيلًا: بدونها لا نصّ ولا صرف، والمنصة كلها معطَّلة.
"""

from __future__ import annotations

import os
from pathlib import Path

# متغير بيئة يتقدّم على كل شيء — مخرج نجاة لأي تخطيط تثبيت غير متوقَّع
DATA_DIR_ENV = "QSP_DATA_DIR"

# `app/core/paths.py` ← parents[2] هو جذر الحزمة (apps/api أو /app)
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _candidates() -> list[Path]:
    """مواضع البحث بالترتيب. أولها المصرَّح به، ثم شجرة الحزمة، ثم العمل."""
    found: list[Path] = []
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        found.append(Path(override).expanduser().resolve())
    found.append(_PACKAGE_ROOT / "data")
    found.append(Path.cwd() / "data")
    # إزالة التكرار مع حفظ الترتيب
    unique: list[Path] = []
    for path in found:
        if path not in unique:
            unique.append(path)
    return unique


def data_dir() -> Path:
    """أول مجلد بيانات موجود، وإلا فأوّل المرشحين (ليُبلَّغ عنه بوضوح)."""
    candidates = _candidates()
    for path in candidates:
        if path.is_dir():
            return path
    return candidates[0]


def data_file(name: str) -> Path:
    """مسار حزمة بعينها، مبحوثًا عنها في كل المرشحين."""
    for folder in _candidates():
        candidate = folder / name
        if candidate.exists():
            return candidate
    return data_dir() / name


def describe_search(name: str) -> str:
    """نصّ يُدرج في رسالة الخطأ: أين بُحث بالضبط ولم يُوجد."""
    tried = "\n".join(f"  - {folder / name}" for folder in _candidates())
    return (
        f"بُحث عن «{name}» في:\n{tried}\n"
        f"يمكن التصريح بالمجلد عبر متغير البيئة {DATA_DIR_ENV}."
    )
