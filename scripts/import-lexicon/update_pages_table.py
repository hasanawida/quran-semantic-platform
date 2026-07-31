#!/usr/bin/env python
"""يجدّد جدول «حال الصفحات» في وثيقة النسخ من الملفات نفسها.

الجدول يُكتب بيدٍ فيَبْلَى: تُضاف صفحاتٌ ولا يُضاف سطرُها، فيقرأ المراجع
حالًا غير الحال. فيُولَّد من الترويسات ورؤوس المواد، وتُعلَن الفجوات في
تسلسل المصوَّرة صراحةً لأنها تقطع سلاسل التقطيع في البنّاء.

التشغيل:
    python scripts/import-lexicon/update_pages_table.py
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAGES_DIR = REPO / "data" / "transcriptions" / "mukhtar-sihah-1920"
README = PAGES_DIR / "README.md"

HEAD = re.compile(r"^\* ([ء-ي](?: [ء-ي]){1,4})\s*$", re.M)
MARKER = "## حال الصفحات"
ARABIC_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def fields_of(text: str) -> dict[str, str]:
    _, header, _ = text.split("---", 2)
    out: dict[str, str] = {}
    for line in header.strip().splitlines():
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def state_of(fields: dict[str, str]) -> str:
    if fields.get("status") == "reviewed":
        return f"**مراجَعة بشريًّا** — {fields.get('reviewed', '')}"
    if fields.get("agent_review"):
        return "قوبلت بالصورة آليًّا — تنتظر المراجعة البشرية"
    return "منسوخة — تنتظر المقابلة والمراجعة"


def main() -> int:
    files = sorted(PAGES_DIR.glob("n[0-9]*.md"), key=lambda f: int(f.stem[1:]))
    rows: list[str] = []
    previous: int | None = None
    reviewed = agent_checked = 0

    for path in files:
        page = int(path.stem[1:])
        if previous is not None and page != previous + 1:
            missing = page - previous - 1
            span = f"n{previous + 1}–n{page - 1}" if missing > 1 else f"n{previous + 1}"
            rows.append(
                f"| — | — | **فجوة: {span}** "
                f"({str(missing).translate(ARABIC_DIGITS)} صفحة) | تقطع السلسلة |"
            )
        previous = page

        text = path.read_text(encoding="utf-8")
        fields = fields_of(text)
        roots = [m.group(1).replace(" ", "") for m in HEAD.finditer(text)]
        state = state_of(fields)
        if fields.get("status") == "reviewed":
            reviewed += 1
        elif fields.get("agent_review"):
            agent_checked += 1
        printed = str(fields.get("printed_page", "?")).translate(ARABIC_DIGITS)
        listed = " · ".join(roots) if roots else "تكملةُ مادةٍ سابقة"
        rows.append(f"| `{path.name}` | {printed} | {listed} | {state} |")

    total = len(files)
    pending = total - reviewed - agent_checked
    table = "\n".join(
        [
            MARKER,
            "",
            f"**{str(total).translate(ARABIC_DIGITS)} صفحة منسوخة** — منها "
            f"{str(reviewed).translate(ARABIC_DIGITS)} مراجَعة بشريًّا، و"
            f"{str(agent_checked).translate(ARABIC_DIGITS)} قوبلت بالصورة آليًّا، و"
            f"{str(pending).translate(ARABIC_DIGITS)} تنتظر.",
            "",
            "> هذا الجدول مُولَّد: `python scripts/import-lexicon/update_pages_table.py`",
            "> — فلا يُحرَّر بيدٍ، ويُعاد توليده بعد كل دفعة نسخ أو مراجعة.",
            "",
            "| الملف | صفحة المطبوع | الموادّ | الحال |",
            "|---|---|---|---|",
            *rows,
            "",
        ]
    )

    text = README.read_text(encoding="utf-8")
    head, marker, _ = text.partition(MARKER)
    if not marker:
        raise SystemExit(f"لم يُعثر على «{MARKER}» في {README.name}")
    README.write_text(head + table, encoding="utf-8")
    print(f"جُدّد الجدول: {total} صفحة · {reviewed} مراجَعة · {agent_checked} مقابَلة آليًّا")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
