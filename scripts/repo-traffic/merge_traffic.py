#!/usr/bin/env python3
"""دمج لقطة حركة المستودع في سجل تراكمي.

**ما يقيسه:** مشاهدات صفحة المستودع على github.com ونسخه (clones).

**وما لا يقيسه — وهذا أهم من قياسه:** زيارات الموقع المنشور على GitHub
Pages. تلك سجلّات عند GitHub لا تُصدَّر لصاحب الموقع. فمن قدّم هذه
الأرقام على أنها «زوّار الموقع» فقد أخطأ في المعنى لا في الرقم.

**ولماذا لقطة يومية:** نافذة واجهة GitHub **أربعة عشر يومًا فقط**، فما
لا يُلتقط يسقط بلا رجعة.

**ولماذا سكربت لا سطر jq:** الدمج **تحديثٌ لا إلحاق**. GitHub تعيد
إحصاء اليوم الجاري في كل لقطة، فإلحاق اللقطات يضاعف أيامًا بعينها.
وآخر قيمة لليوم هي الصحيحة.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

FIELDS = ["date", "views", "view_uniques", "clones", "clone_uniques"]


def _by_day(payload: dict, key: str) -> dict[str, tuple[int, int]]:
    """{"2026-07-26": (count, uniques)} — الطابع الزمني يومي أصلًا."""
    out: dict[str, tuple[int, int]] = {}
    for item in payload.get(key, []):
        day = str(item["timestamp"])[:10]
        out[day] = (int(item["count"]), int(item["uniques"]))
    return out


def merge(views_path: str, clones_path: str, csv_path: str) -> int:
    views = _by_day(json.loads(Path(views_path).read_text("utf-8")), "views")
    clones = _by_day(json.loads(Path(clones_path).read_text("utf-8")), "clones")

    history: dict[str, dict[str, str]] = {}
    target = Path(csv_path)
    if target.exists():
        with target.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                history[row["date"]] = dict(row)

    for day in sorted(set(views) | set(clones)):
        row = history.get(day, {"date": day})
        row["date"] = day
        if day in views:
            row["views"], row["view_uniques"] = (str(n) for n in views[day])
        if day in clones:
            row["clones"], row["clone_uniques"] = (str(n) for n in clones[day])
        history[day] = {field: row.get(field, "") for field in FIELDS}

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for day in sorted(history):
            writer.writerow(history[day])
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "usage: merge_traffic.py views.json clones.json out.csv",
            file=sys.stderr,
        )
        raise SystemExit(2)
    raise SystemExit(merge(sys.argv[1], sys.argv[2], sys.argv[3]))
