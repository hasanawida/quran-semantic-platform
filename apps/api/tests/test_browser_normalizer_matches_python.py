"""عقد التطبيع من تنفيذين إلى ثلاثة: بايثون، وSQL، والمتصفح.

مواصفة `normspec.json` تُولَّد آليًا من ثوابت `app/utils/arabic.py`،
ويقرؤها مفسّر TypeScript **عام لا يعرف العربية** — لا قاعدة همزة ولا ألف
مكتوبة فيه. وهذا الاختبار يشغّل المفسّر على Node ويقارن مخرجه بمخرج
بايثون على كل آية وكل كلمة مميزة وحالات عدائية، في أربع دوال معًا:
البحث، والهيكل، واسم السورة، ومفتاح الجذر — ومعها مواضع الكلمات.

بلا هذا الحارس ينحرف تطبيع الطلب عن تطبيع الفهرس **بصمت**، فيعيد البحث
صفرًا بلا رسالة خطأ — وهو عين ما يحذّر منه تعليق
`normalize_search_skeleton`، وعين صنف العطب الذي وقع في مسار الاستيراد.

**الترجمة بـ`tsc` لا بتعابير نمطية.** اقترحت الخطة تجريد الأنواع بـregex
ووسمت ذلك خطرًا مسجَّلًا — وقد سقط فعلًا من أول تشغيل
(`SyntaxError: Unexpected identifier 'NormSpec'`). ومترجمٌ حقيقي يجعل
الاختبار يفشل لسببه لا لهشاشة أداته، و`tsc` موجود أصلًا في تبعيات
الواجهة فلا تبعية جديدة.
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
BIN = REPO / "apps" / "web" / "node_modules" / ".bin"

RUNNER = """
import fs from "node:fs";
import { Normalizer } from "./normalize.js";

const [specPath, goldPath, tokPath] = process.argv.slice(2);
const n = new Normalizer(JSON.parse(fs.readFileSync(specPath, "utf8")));

const failures = [];
for (const [inp, a, b, c, d] of JSON.parse(fs.readFileSync(goldPath, "utf8"))) {
  if (n.search(inp) !== a) failures.push(["search", inp, n.search(inp), a]);
  if (n.skeleton(inp) !== b) failures.push(["skeleton", inp, n.skeleton(inp), b]);
  if (n.surahName(inp) !== c) failures.push(["surahName", inp, n.surahName(inp), c]);
  if (n.rootInput(inp) !== d) failures.push(["rootInput", inp, n.rootInput(inp), d]);
}

let tokDiffs = 0;
let tokChecked = 0;
for (const [text, spans] of JSON.parse(fs.readFileSync(tokPath, "utf8"))) {
  tokChecked += 1;
  const got = n.tokenize(text);
  const same =
    got.length === spans.length &&
    got.every((g, i) => g.char_start === spans[i][0] && g.char_end === spans[i][1]);
  if (!same) tokDiffs += 1;
}

console.log(
  JSON.stringify({
    diffs: failures.length,
    sample: failures.slice(0, 5),
    tokDiffs,
    tokChecked,
  })
);
"""


def _tsc() -> Path | None:
    for name in ("tsc.cmd", "tsc"):
        candidate = BIN / name
        if candidate.exists():
            return candidate
    return None


@pytest.fixture(scope="module")
def compiled(tmp_path_factory) -> Path:
    """يترجم `normalize.ts` بـtsc إلى ESM قابل للتشغيل على Node."""
    if shutil.which("node") is None:
        pytest.skip("Node غير متاح")
    tsc = _tsc()
    if tsc is None:
        pytest.skip("tsc غير مثبَّت — شغّل npm ci في apps/web")

    work = tmp_path_factory.mktemp("normalizer")
    shutil.copy(LIB, work / "normalize.ts")
    result = subprocess.run(
        [
            str(tsc),
            "normalize.ts",
            "--target",
            "es2022",
            "--module",
            "es2022",
            "--moduleResolution",
            "bundler",
            "--strict",
        ],
        cwd=work,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, (
        "فشلت ترجمة normalize.ts:\n" + (result.stdout or "") + (result.stderr or "")
    )
    (work / "runner.mjs").write_text(RUNNER, encoding="utf-8")
    return work


@pytest.fixture(scope="module")
def report(compiled) -> dict:
    for name in ("normspec.json", "normgold.json", "tokengold.json"):
        assert (DATA / name).exists(), (
            f"{name} غير مولَّد — شغّل scripts/export-static/build_data.py أولًا"
        )
    result = subprocess.run(
        [
            "node",
            str(compiled / "runner.mjs"),
            str(DATA / "normspec.json"),
            str(DATA / "normgold.json"),
            str(DATA / "tokengold.json"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_browser_normalizer_matches_python_exactly(report):
    """أربع دوال تطبيع، على كل آية وكل كلمة مميزة وحالات عدائية."""
    assert report["diffs"] == 0, (
        f"تطبيع المتصفح يفترق عن بايثون في {report['diffs']} حالة.\n"
        f"عيّنة: {json.dumps(report['sample'], ensure_ascii=False, indent=2)}\n"
        "أعد توليد normspec.json أو صحّح المفسّر."
    )


def test_browser_tokenizer_matches_python_exactly(report):
    """مواضع الكلمات: انحرافها يجعل التمييز يقع على كلمة غير التي طابقت."""
    assert report["tokChecked"] == 6236, report["tokChecked"]
    assert report["tokDiffs"] == 0, (
        f"مواضع الكلمات تفترق في {report['tokDiffs']} آية من "
        f"{report['tokChecked']} — التمييز سيقع على كلمة غير التي طابقت."
    )
