#!/usr/bin/env python
"""يبني حزمة «مختار الصحاح» من ملفات النسخ المراجَعة.

**المصدر:** طبعة المطبعة الأميرية ١٩٢٠م — **ملكية عامة نصًّا وترقيمًا**
(قبل ١٩٢٩). لا حقَّ لأحدٍ فيها ولا إذنَ يُطلب. المصوَّرة:
https://archive.org/details/AAlexandrina-196404

**القواعد المُنفَّذة هنا لا المُدَّعاة:**

1. **سياسة النشر — بقرار المالك (2026-07-30):** «انشر كل شيء وأنا
   أراجعها بعدها». فتدخل الحزمةَ كلُّ الصفحات المنسوخة، و**تحمل كل مادة
   حالتها الصادقة**: `reviewed` إن رُوجعت كلُّ صفحاتها بشريًّا، وإلا
   عُرضت موسومةً «قيد المراجعة» — لا يُدَّعى ما لم يقع. (وهذا عدولٌ
   موثَّق عن حرفية §24.6 بقرار صاحب الدستور نفسه، والوسم الصادق بدله.)
2. **المواد تمتدّ عبر الصفحات:** التقطيع يجري على السلاسل المتّصلة من
   الصفحات المنسوخة، و**آخر مادة في كل سلسلة تُسقَط** لاحتمال بترها —
   وتعود تلقائيًّا حين تُنسخ الصفحة التالية.
3. **المطابقة بجذورنا:** رأس المادة (* ج م ع) يُطبَّع بـ
   `normalize_root_input` نفسها المستعملة في البذر، ويُنشر منها ما طابق
   فهرس جذور المصحف وحده.
4. **الصفحة تُنشر مع كل مادة** — وهي صفحة الطبعة الحرّة، فذكرُها مشروع
   (ADR-012: الصفحة اختيارية، وهنا متاحة بلا حرج).

التشغيل:
    python scripts/import-lexicon/build_sihah.py
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "apps" / "api"))

from app.utils.arabic import normalize_root_input  # noqa: E402

PAGES_DIR = REPO / "data" / "transcriptions" / "mukhtar-sihah-1920"
OUT = REPO / "apps" / "api" / "data" / "sihah_bundle.json.gz"
ROOTS = REPO / "apps" / "web" / "public" / "data" / "v1" / "roots.json"

ARCHIVE_ID = "AAlexandrina-196404"
HEAD = re.compile(r"^\* ([ء-ي](?: [ء-ي]){1,4})\s*$", re.M)
FLAG = re.compile(r"⟨[^⟩]*⟩")


def parse_page(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise SystemExit(f"{path.name}: لا ترويسة")
    _, header, body = text.split("---", 2)
    fields: dict[str, str] = {}
    for line in header.strip().splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip("'\"")
    # قفل المصدر: صفحة من غير هذه المصوَّرة لا تدخل
    if fields.get("archive") != ARCHIVE_ID:
        raise SystemExit(f"{path.name}: مصوَّرة غير المعتمدة ({fields.get('archive')})")
    if "archive.org/download/" + ARCHIVE_ID not in fields.get("image", ""):
        raise SystemExit(f"{path.name}: رابط الصورة لا يطابق المصوَّرة")
    return {
        "file": path.name,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "archive_page": int(fields["archive_page"]),
        "printed_page": int(fields["printed_page"]),
        "image": fields["image"],
        "status": fields.get("status", ""),
        "reviewed": fields.get("reviewed", ""),
        "body": body.strip(),
    }


def contiguous_runs(pages: list[dict]) -> list[list[dict]]:
    runs: list[list[dict]] = []
    for page in sorted(pages, key=lambda p: p["archive_page"]):
        if runs and page["archive_page"] == runs[-1][-1]["archive_page"] + 1:
            runs[-1].append(page)
        else:
            runs.append([page])
    return runs


def segment_run(run: list[dict]) -> list[dict]:
    """يقطّع سلسلةً متصلة موادَّ، ويحذف الأخيرة لاحتمال بترها."""
    # موضع كل صفحة في النص المتّصل — لتُنسب المادة إلى صفحة رأسها
    joined = ""
    marks: list[tuple[int, dict]] = []
    for page in run:
        marks.append((len(joined), page))
        joined += page["body"] + "\n"

    def page_of(position: int) -> dict:
        current = marks[0][1]
        for start, page in marks:
            if start <= position:
                current = page
            else:
                break
        return current

    def pages_spanning(start: int, end: int) -> list[dict]:
        """كلُّ الصفحات التي يمتدّ عليها نصُّ المادة — لحساب حالتها."""
        spanned = []
        for i, (offset, page) in enumerate(marks):
            nxt = marks[i + 1][0] if i + 1 < len(marks) else len(joined)
            if offset < end and nxt > start:
                spanned.append(page)
        return spanned

    # حالة المادة = **أضعفُ** حالات صفحاتها: مراجعةُ نصفِ مادةٍ ليست
    # مراجعةً لها. human > agent > machine.
    RANK = {"reviewed": 2, "agent_checked": 1, "machine_transcribed": 0}
    STATE = {2: "human", 1: "agent", 0: "machine"}

    entries: list[dict] = []
    heads = list(HEAD.finditer(joined))
    for i, match in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(joined)
        body = joined[match.end():end].strip()
        if len(body) < 20:
            continue
        weakest = min(
            RANK.get(p["status"], 0) for p in pages_spanning(match.start(), end)
        )
        entries.append(
            {
                "display": match.group(1),
                "text": re.sub(r"\s+", " ", body),
                "page": page_of(match.start())["printed_page"],
                "flags": len(FLAG.findall(body)),
                "review": STATE[weakest],
            }
        )
    # آخر مادة قد تكون مبتورة عند نهاية السلسلة — تُسقَط ولا تُنشَر ناقصة
    return entries[:-1] if entries else []


def main() -> None:
    # صفحاتُ النسخ وحدها: `n*.md` كان يبتلع أيَّ ملفٍّ آخر في المجلد
    files = sorted(PAGES_DIR.glob("n[0-9]*.md"))
    if not files:
        raise SystemExit(f"لا ملفات نسخ في {PAGES_DIR}")
    pages = [parse_page(f) for f in files]
    reviewed = [p for p in pages if p["status"] == "reviewed"]
    pending = [p for p in pages if p["status"] != "reviewed"]

    # سياسة المالك (2026-07-30): يُنشر المنسوخ كلُّه، وكلُّ مادةٍ بوسمها
    entries_all: list[dict] = []
    for run in contiguous_runs(pages):
        entries_all += segment_run(run)

    our_roots: list[str] = json.loads(ROOTS.read_text(encoding="utf-8"))["roots"]
    keyed = {normalize_root_input(r): r for r in our_roots}

    matched: dict[str, dict] = {}
    unmatched: list[str] = []
    for entry in entries_all:
        key = normalize_root_input(entry["display"].replace(" ", ""))
        root = keyed.get(key)
        if root:
            matched.setdefault(root, entry)
        else:
            unmatched.append(entry["display"])

    bundle = {
        "meta": {
            "work": "مختار الصحاح",
            "author": "محمد بن أبي بكر الرازي (ت نحو ٦٦٦هـ)",
            "edition": "المطبعة الأميرية — ١٩٢٠م",
            "public_domain": True,
            "statement": (
                "الطبعة ملكية عامة نصًّا وترقيمًا (طُبعت قبل ١٩٢٩). نُسخ "
                "المتن آليًّا من صور المصوَّرة، وكلُّ مادةٍ تحمل حالة "
                "مراجعتها الصادقة: بشرية، أو وكيل آلي مستقل، أو قيد "
                "المراجعة. وما يُنتَج هنا يُعاد نشره حرًّا."
            ),
            "scan": f"https://archive.org/details/{ARCHIVE_ID}",
            "review_status": "imported",
            "pages": {
                "transcribed": len(pages),
                "reviewed": len(reviewed),
                "pending": [p["file"] for p in pending],
            },
            "page_files_sha256": {p["file"]: p["sha256"] for p in pages},
            "entries_published": len(matched),
            "entries_dropped_truncated_or_unmatched": len(unmatched),
        },
        "entries": matched,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as handle:
        json.dump(bundle, handle, ensure_ascii=False, separators=(",", ":"))

    print(f"صفحات: {len(pages)} منسوخة · {len(reviewed)} مراجَعة · {len(pending)} تنتظر")
    print(f"مواد منشورة (جذور قرآنية): {len(matched)}", sorted(matched) or "")
    if unmatched:
        print(f"غير قرآنية أو مُسقَطة: {unmatched}")
    print(f"كُتب: {OUT} ({OUT.stat().st_size:,} بايت)")


if __name__ == "__main__":
    main()
