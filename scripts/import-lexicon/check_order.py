#!/usr/bin/env python
"""يكشف رؤوس المواد الخارجة عن الترتيب الهجائي في صفحات النسخ.

المعجم مرتَّب بالجذر ترتيبًا هجائيًّا صارمًا، فرأسٌ يسبق ما قبله دليلٌ
آليّ على تصحيف: إمّا خطأ في المطبوع (كـ«خ ر ض» موضع «ح ر ض»)، وإمّا
خطأ في النسخ. وكلاهما يجب أن يُرى قبل النشر لا بعده.

القاعدة (README §5، بقرار المالك 2026-07-31): الخطأ المُبَرهَن يُصوَّب في
المتن، ويُسجَّل المطبوع في حقل `corrections` بترويسة الصفحة.

التشغيل:
    python scripts/import-lexicon/check_order.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAGES_DIR = REPO / "data" / "transcriptions" / "mukhtar-sihah-1920"

HEAD = re.compile(r"^\* ([ء-ي](?: [ء-ي]){1,4})\s*$", re.M)
# لافتة الباب في المطبوع: يليها رأسٌ للحرف نفسه (* ت ا) يفتتح الباب قبل
# مواده المرتَّبة، فلا يُقاس على ما قبله.
BAB = re.compile(r"^باب\s", re.M)

# ترتيب حروف المعجم كما يرتّب به «مختار الصحاح» — الهمزة أولًا والياء آخرًا
ALPHABET = "ءابتثجحخدذرزسشصضطظعغفقكلمنهوي"
RANK = {letter: index for index, letter in enumerate(ALPHABET)}

# الألف المقصورة والمدّة وأخواتها تُردّ إلى أصلها في الترتيب
# والياء المهملة في المطبوع ياءٌ لا ألف — إلا في الموضع الأخير فتُعامَل
# معاملة المعتلّ أدناه.
FOLD = {"أ": "ء", "إ": "ء", "آ": "ء", "ؤ": "ء", "ئ": "ء", "ى": "ي", "ة": "ه"}

# عرفُ المعجم: المعتلُّ الآخر يُؤخَّر إلى ذيل بابه — (ج ب ا) بعد (ج ب ه)
# لا قبل (ج ب ب). فحرفُ العلّة في الموضع الأخير يُعطى رتبةً فوق الحروف.
WEAK_FINAL = 99

# مواضع قُوبلت بالصورة فثبت أن **المطبوع نفسه** خالف ترتيبه، وحروف الرأس
# سليمة — فلا شيء يُصوَّب. تُستثنى لئلا يغرق التنبيهُ الصحيحُ في الضجيج.
VERIFIED_PRINT_ORDER = {
    # ص171: قدّم المطبوعُ الرباعيَّ (خ ر د ل) على (خ ر ج) — فُحص بالصورة
    ("خ ر ج", "n182.md"),
}


def key(head: str) -> tuple[int, ...]:
    letters = head.split()
    ranks = [RANK[FOLD.get(ch, ch)] for ch in letters]
    if len(letters) > 1 and letters[-1] in ("ا", "ى"):
        ranks[-1] = WEAK_FINAL
    return tuple(ranks)


def main() -> int:
    files = sorted(
        PAGES_DIR.glob("n[0-9]*.md"),
        key=lambda f: int(f.stem[1:]),
    )
    if not files:
        raise SystemExit(f"لا ملفات نسخ في {PAGES_DIR}")

    heads: list[tuple[str, str]] = []  # (الرأس، اسم الملف)
    previous_page: int | None = None
    for path in files:
        page = int(path.stem[1:])
        # الفجوة تقطع السلسلة: لا يُقارَن رأسٌ برأسٍ عبر صفحات مفقودة
        if previous_page is not None and page != previous_page + 1:
            heads.append(("—فجوة—", path.name))
        previous_page = page
        text = path.read_text(encoding="utf-8")
        events = [(m.start(), m.group(1)) for m in HEAD.finditer(text)]
        events += [(m.start(), None) for m in BAB.finditer(text)]
        for _, head in sorted(events):
            heads.append((head or "—باب—", path.name))

    problems: list[str] = []
    last: tuple[str, str] | None = None
    opening = False  # الرأس التالي للافتة الباب هو رأس الحرف نفسه
    for head, file in heads:
        if head == "—فجوة—":
            last, opening = None, False
            continue
        if head == "—باب—":
            last, opening = None, True
            continue
        if opening:
            opening = False
            continue
        if (head, file) in VERIFIED_PRINT_ORDER:
            last = (head, file)
            continue
        if last is not None and key(head) < key(last[0]):
            problems.append(
                f"{file}: «{head}» يسبق «{last[0]}» ({last[1]}) في الترتيب"
            )
        last = (head, file)

    counted = sum(1 for h, _ in heads if h not in ("—فجوة—", "—باب—"))
    print(f"رؤوس مفحوصة: {counted} في {len(files)} صفحة")
    if not problems:
        print("لا خروج عن الترتيب.")
        return 0
    print(f"خارجة عن الترتيب: {len(problems)} — كلٌّ منها يحتاج مقابلةً بالصورة")
    for problem in problems:
        print(f"  · {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
