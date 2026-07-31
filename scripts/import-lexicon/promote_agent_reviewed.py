#!/usr/bin/env python
"""يرقّي حالة الصفحة من `machine_transcribed` إلى `agent_checked` متى وقعت
عليها مقابلةٌ آليةٌ مستقلة بالصورة (حقل `agent_review` مملوء).

**لماذا هذا الملف:** البنّاء (`build_sihah.py`) يعرف ثلاث حالات ويعرض كل
مادة بأضعف حالات صفحاتها: `reviewed` (بشرية) > `agent_checked` (وكيل آلي
مستقل قابل النصَّ بالصورة) > `machine_transcribed` (نسخٌ آليّ بلا مقابلة).
والمقابلة الآلية تكتب شهادتها في `agent_review`، فوجب أن تُترجم الشهادةُ
حالةً — وإلا عُرضت صفحةٌ قوبلت كأنها لم تُقابَل، وهو **بخسٌ** للحال لا
ادّعاء عليها.

**ما لا يفعله:** لا يرفع شيئًا إلى `reviewed` أبدًا. المراجعة البشرية
لا ينوب عنها وكيل، وهذا نصُّ §24.6. والترقية هنا إلى منزلةٍ دون ذلك
صريحةٍ في اسمها.

التشغيل:
    python scripts/import-lexicon/promote_agent_reviewed.py [--dry-run]
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAGES_DIR = REPO / "data" / "transcriptions" / "mukhtar-sihah-1920"


def header_of(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    _, header, _ = text.split("---", 2)
    fields: dict[str, str] = {}
    for line in header.strip().splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip("'\"")
    return fields


def main() -> None:
    dry = "--dry-run" in sys.argv
    promoted: list[str] = []
    already: list[str] = []
    unchecked: list[str] = []

    for path in sorted(PAGES_DIR.glob("n[0-9]*.md")):
        text = path.read_text(encoding="utf-8")
        fields = header_of(text)
        if not fields:
            raise SystemExit(f"{path.name}: لا ترويسة")
        status = fields.get("status", "")
        review = fields.get("agent_review", "")

        if status == "reviewed":
            already.append(path.name)  # بشرية: أعلى من الترقية، لا تُمَس
            continue
        if not review:
            unchecked.append(path.name)
            continue
        if status == "agent_checked":
            already.append(path.name)
            continue
        if status != "machine_transcribed":
            raise SystemExit(f"{path.name}: حالة غير معروفة ({status})")

        if not dry:
            # سطر الحالة وحده يُبدَّل — لا يُمَسّ المتن ولا بقية الترويسة
            new = text.replace(
                "\nstatus: machine_transcribed\n",
                "\nstatus: agent_checked\n",
                1,
            )
            if new == text:
                raise SystemExit(f"{path.name}: تعذّر إبدال سطر الحالة")
            path.write_text(new, encoding="utf-8")
        promoted.append(path.name)

    head = "سيُرقَّى" if dry else "رُقِّيت"
    print(f"{head}: {len(promoted)} صفحة", promoted or "")
    print(f"على حالها (بشرية أو مرقّاة سلفًا): {len(already)}")
    print(f"بلا مقابلة آلية بعد: {len(unchecked)}", unchecked or "")


if __name__ == "__main__":
    main()
