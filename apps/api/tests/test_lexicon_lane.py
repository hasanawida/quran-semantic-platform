"""حارس معجم لِين: الطبعة والشروط والنسبة — لا يسقط منها شيء صامتًا.

**لماذا:** إتاحة لِين ليست رخصةً مفتوحة بلا قيد. نصُّ الملف نفسه يشترط
ثلاثة: النسبة بعبارةٍ بعينها، وإبقاء بيان الإتاحة، وعرض التعديلات. فإن
سقطت النسبة من الواجهة صار الاستعمال مخالفًا لشرط صاحبه — ولا يكشف ذلك
مترجمٌ ولا بناء.

**وأخطر منه:** أن يُفكّ ترميز المصدر اللاتيني إلى حرفٍ عربي. ترميز
Perseus ليس باكوولتر قياسيًّا، وفكُّه الظنّي يولّد عربيةً لم يكتبها لِين.
فيُحرَس ألّا يتسرّب حرفٌ عربي إلى حقول المصدر.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
BUNDLE = REPO / "apps" / "api" / "data" / "lane_bundle.json.gz"
OUT = REPO / "apps" / "web" / "public" / "data" / "v1"

REQUIRED_CREDIT = "Text provided by Perseus Digital Library"


@pytest.fixture(scope="module")
def bundle() -> dict:
    if not BUNDLE.exists():
        pytest.skip(
            "حزمة لِين غير مبنيّة. شغّل:\n"
            "  python scripts/import-lexicon/build_lane.py <arabic.tar.gz>"
        )
    with gzip.open(BUNDLE, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def test_edition_and_hashes_are_recorded(bundle):
    """§10: الكتاب + الطبعة + الملف + الترخيص + البصمة — كلها أو لا شيء."""
    meta = bundle["meta"]
    assert meta["work"] == "An Arabic-English Lexicon"
    assert meta["author"] == "Edward William Lane"
    assert meta["edition"] == "London: Williams and Norgate, 1863"
    assert len(meta["archive_sha256"]) == 64
    assert meta["file_sha256"], "بصمات الملفات مفقودة"
    for name, digest in meta["file_sha256"].items():
        assert len(digest) == 64, name


def test_the_three_availability_conditions_survive(bundle):
    """شروط الإتاحة منقولة حرفيًا — لا تُلخَّص ولا تُترجَم ولا تُسقَط."""
    availability = bundle["meta"]["availability"]
    conditions = availability["conditions"]
    assert len(conditions) == 3, conditions
    assert REQUIRED_CREDIT in availability["attribution_required"]
    joined = " ".join(conditions)
    assert "credit Perseus" in joined
    assert "availability statement intact" in joined
    assert "modifications" in joined


def test_no_arabic_script_leaks_into_source_fields(bundle):
    """الترميز اللاتيني لا يُفكّ. حرفٌ عربي في حقل المصدر يعني أن أحدًا
    فكّه ظنًّا — وذلك يولّد نصًّا لم يكتبه لِين."""
    leaked: list[str] = []
    for root, items in bundle["entries"].items():
        for item in items:
            for field in ("key",):
                if any("؀" <= c <= "ۿ" for c in item[field]):
                    leaked.append(f"{root}: {field}={item[field]!r}")
    assert not leaked, "عربية مفكوكة في حقول المصدر:\n  " + "\n  ".join(leaked[:10])


def test_every_entry_carries_a_real_page(bundle):
    """§لا مادةَ بلا صفحة. وأرقام لِين تقع في مدى الطبعة المعروف."""
    bad = [
        f"{root}: {item['key']} ص{item['page']}"
        for root, items in bundle["entries"].items()
        for item in items
        if not isinstance(item["page"], int) or not 1 <= item["page"] <= 3100
    ]
    assert not bad, "صفحات خارج المدى:\n  " + "\n  ".join(bad[:10])


def test_every_matched_root_is_one_of_ours(bundle):
    """لا مادةَ لجذرٍ ليس في فهرسنا — وإلا عُرضت مادةٌ لا يصل إليها أحد."""
    roots_file = OUT / "roots.json"
    if not roots_file.exists():
        pytest.skip("بيانات الجذور غير مولَّدة")
    ours = set(json.loads(roots_file.read_text(encoding="utf-8"))["roots"])
    stray = sorted(set(bundle["entries"]) - ours)
    assert not stray, f"جذور غريبة: {stray[:10]}"


def test_published_registry_declares_the_limits(bundle):
    """الحدود معلَنة في الملف المنشور لا في وثيقةٍ جانبية."""
    published = OUT / "lexicon.json"
    if not published.exists():
        pytest.skip("lexicon.json غير مولَّد")
    data = json.loads(published.read_text(encoding="utf-8"))
    assert data["state"] == "partial", "الحال يجب أن تقول إن التغطية جزئية"
    assert len(data["with_text"]) == bundle["meta"]["limits"]["roots_matched"]
    assert data["lane"]["edition"] == bundle["meta"]["edition"]
    assert REQUIRED_CREDIT in data["lane"]["availability"]["attribution_required"]
    # التغطية الجزئية رقمٌ يُقال، لا يُترك للقارئ يستنتجه
    assert data["lane"]["limits"]["roots_matched"] < data["entry_count"]
