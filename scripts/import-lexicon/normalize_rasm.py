#!/usr/bin/env python
"""يوحّد رسم الياء في صفحات النسخ على رسم المطبوع.

طبعة المطبعة الأميرية ١٩٢٠م تُهمِل الياء (ى بلا نقطتين) في موضعين
ثابتين، وقد قُوبلا بالصور:

1. **آخر الكلمة:** «فى» و«التى» و«الأصمعىّ» و«بحاجتى» — لا «في» و«التي».
2. **قبل الهمزة المفردة:** «الشىء» و«يجىء» — لا «الشيء».

ووكلاء النسخ تفاوتوا: بعضهم نقل رسم المطبوع، وبعضهم حدّثه من غير قصد.
والتفاوتُ في نفسه خطأ: النصّ الواحد لا يكون بحرفين. فهذا يردّ الجميع إلى
المطبوع — وهو تصحيحٌ للنسخ لا تغييرٌ للأصل.

ما لا يُمَسّ: ترويسة الملف (بياناتها بلغتنا لا بلغة المطبوع)، والياء في
وسط الكلمة (فهي منقوطة في المطبوع).

التشغيل:
    python scripts/import-lexicon/normalize_rasm.py          # تقرير فقط
    python scripts/import-lexicon/normalize_rasm.py --apply  # وينفّذ
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAGES_DIR = REPO / "data" / "transcriptions" / "mukhtar-sihah-1920"

YA = "ي"  # ي
ALIF_MAQSURA = "ى"  # ى
# الحركات تلتصق بالحرف فلا تُخرجه عن موضعه الأخير
MARKS = "ً-ْٰ"
LETTERS = "ء-يٱ-ۓ"

# ياءٌ في آخر الكلمة: لا يتلوها حرفٌ عربي (والحركات لا تُحتسب)
FINAL = re.compile(f"{YA}(?=[{MARKS}]*(?![{LETTERS}{MARKS}]))")
# ياءٌ قبل همزة مفردة: الشىء، يجىء
BEFORE_HAMZA = re.compile(f"{YA}(?=[{MARKS}]*ء)")


def normalize(body: str) -> tuple[str, int]:
    out, count = BEFORE_HAMZA.subn(ALIF_MAQSURA, body)
    out, more = FINAL.subn(ALIF_MAQSURA, out)
    return out, count + more


def main() -> int:
    apply = "--apply" in sys.argv
    files = sorted(PAGES_DIR.glob("n[0-9]*.md"), key=lambda f: int(f.stem[1:]))
    if not files:
        raise SystemExit(f"لا ملفات نسخ في {PAGES_DIR}")

    total = 0
    touched: list[tuple[str, int]] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            raise SystemExit(f"{path.name}: لا ترويسة")
        _, header, body = text.split("---", 2)
        fixed, count = normalize(body)
        if not count:
            continue
        total += count
        touched.append((path.name, count))
        if apply:
            path.write_text(f"---{header}---{fixed}", encoding="utf-8")

    verb = "صُحّحت" if apply else "تحتاج تصحيحًا"
    print(f"{verb}: {total} ياء في {len(touched)} صفحة من {len(files)}")
    for name, count in touched:
        print(f"  · {name}: {count}")
    if not apply and total:
        print("\nللتنفيذ: python scripts/import-lexicon/normalize_rasm.py --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
