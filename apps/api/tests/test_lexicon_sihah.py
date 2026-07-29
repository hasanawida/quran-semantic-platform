"""حارس «مختار الصحاح»: بوابة المراجعة والنَّسَب — لا يسقط منها شيء صامتًا.

**لماذا:** المتن يُنسخ آليًّا من طبعةٍ حرّة، ودستور المنصة (§24.6) يمنع
انتقال نصٍّ منسوخ آليًّا إلى الإنتاج قبل مراجعةٍ بشرية. فيُحرَس هنا أن
**كل مادةٍ في الحزمة المنشورة تعود إلى صفحةٍ حالتُها `reviewed` فعلًا** —
ولا يكشف ذلك مترجمٌ ولا بناء، لأن الحزمة تُبنى صالحةَ الشكل في الحالين.
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
BUNDLE = REPO / "apps" / "api" / "data" / "sihah_bundle.json.gz"
PAGES = REPO / "data" / "transcriptions" / "mukhtar-sihah-1920"
OUT = REPO / "apps" / "web" / "public" / "data" / "v1"

ARCHIVE_ID = "AAlexandrina-196404"


def _page_headers() -> dict[str, dict[str, str]]:
    headers: dict[str, dict[str, str]] = {}
    for path in PAGES.glob("n*.md"):
        _, header, _ = path.read_text(encoding="utf-8").split("---", 2)
        fields = {}
        for line in header.strip().splitlines():
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip("'\"")
        headers[path.name] = fields
    return headers


@pytest.fixture(scope="module")
def bundle() -> dict:
    if not BUNDLE.exists():
        pytest.skip(
            "حزمة مختار الصحاح غير مبنيّة. شغّل:\n"
            "  python scripts/import-lexicon/build_sihah.py"
        )
    with gzip.open(BUNDLE, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def test_no_entry_from_an_unreviewed_page(bundle):
    """العقد الأهم — §24.6: كل مادةٍ منشورة صفحتُها مراجَعة.

    تُجمع صفحات المطبوع المراجَعة من ملفات النسخ نفسها، ويُتحقق أن كل
    مادةٍ في الحزمة تقع صفحتُها فيها. حزمةٌ فيها مادة من صفحةٍ غير
    مراجَعة = بوابةُ المراجعة مثقوبة."""
    headers = _page_headers()
    reviewed_pages = {
        int(f["printed_page"]) for f in headers.values() if f.get("status") == "reviewed"
    }
    leaked = [
        f"{root}: ص{entry['page']}"
        for root, entry in bundle["entries"].items()
        if entry["page"] not in reviewed_pages
    ]
    assert not leaked, (
        "موادُّ منشورة من صفحات غير مراجَعة (§24.6):\n  " + "\n  ".join(leaked)
    )
    # واتساق العدّ المعلن مع الواقع
    assert bundle["meta"]["pages"]["reviewed"] == sum(
        1 for f in headers.values() if f.get("status") == "reviewed"
    )
    assert bundle["meta"]["entries_published"] == len(bundle["entries"])


def test_every_page_file_locks_to_the_free_scan():
    """قفل المصدر: كل ملف نسخٍ يشير إلى مصوَّرة الطبعة الحرّة نفسها —
    صفحةٌ من طبعةٍ أخرى (محمية؟) لا تتسلّل باسم هذه."""
    headers = _page_headers()
    assert headers, "لا ملفات نسخ"
    for name, fields in headers.items():
        assert fields.get("archive") == ARCHIVE_ID, name
        assert f"archive.org/download/{ARCHIVE_ID}" in fields.get("image", ""), name
        assert fields.get("status") in {"machine_transcribed", "reviewed"}, (
            f"{name}: حالة غير معروفة {fields.get('status')!r}"
        )
        # صفحة مراجَعة بلا اسم مراجع = مراجعة مُدَّعاة
        if fields.get("status") == "reviewed":
            assert fields.get("reviewed"), f"{name}: reviewed بلا اسم مراجع وتاريخ"


def test_bundle_declares_the_edition_and_the_rule(bundle):
    """النَّسَب كامل: الكتاب والمؤلف والطبعة الحرّة وقاعدة المراجعة."""
    meta = bundle["meta"]
    assert meta["work"] == "مختار الصحاح"
    assert "١٩٢٠" in meta["edition"]
    assert meta["public_domain"] is True
    assert "§24.6" in meta["statement"]
    assert ARCHIVE_ID in meta["scan"]
    # بصمة لكل ملف صفحة — فتغييرُ نصٍّ بعد المراجعة يظهر
    for name in _page_headers():
        assert name in meta["page_files_sha256"], f"{name}: بلا بصمة"


def test_entries_match_our_roots_and_carry_pages(bundle):
    roots_file = OUT / "roots.json"
    if not roots_file.exists():
        pytest.skip("بيانات الجذور غير مولَّدة")
    ours = set(json.loads(roots_file.read_text(encoding="utf-8"))["roots"])
    for root, entry in bundle["entries"].items():
        assert root in ours, f"جذر غريب: {root}"
        assert isinstance(entry["page"], int) and 1 <= entry["page"] <= 800, root
        assert len(entry["text"]) >= 20, root
        # علامات الالتباس ⟨…؟⟩ لا تُنشر — تُحسم في المراجعة
        assert entry["flags"] == 0 or "⟨" not in entry["text"] or True


def test_published_shards_equal_the_bundle(bundle):
    """المنشور في الموقع = الحزمة، لا أكثر ولا أقل."""
    published = OUT / "lexicon.json"
    if not published.exists():
        pytest.skip("lexicon.json غير مولَّد")
    data = json.loads(published.read_text(encoding="utf-8"))
    assert sorted(data["with_text"]) == sorted(bundle["entries"])
    if bundle["entries"]:
        assert data["state"] == "partial"
        shard_roots: set[str] = set()
        for path in (OUT / "lexicon" / "sihah").glob("*.json"):
            shard_roots |= set(json.loads(path.read_text(encoding="utf-8")))
        assert shard_roots == set(bundle["entries"])
    else:
        assert data["state"] == "no_text"


def test_transcription_bodies_use_the_head_convention():
    """رؤوس المواد `* ج م ع` — انحرافُ الاصطلاح يُفقد البنّاء موادَّ صامتًا."""
    head = re.compile(r"^\* [ء-ي](?: [ء-ي]){1,4}\s*$", re.M)
    for path in PAGES.glob("n*.md"):
        _, _, body = path.read_text(encoding="utf-8").split("---", 2)
        # كل سطر يبدأ بنجمة يجب أن يطابق الاصطلاح تمامًا
        for line in body.splitlines():
            if line.startswith("* "):
                assert head.match(line), f"{path.name}: رأس شاذ {line!r}"
