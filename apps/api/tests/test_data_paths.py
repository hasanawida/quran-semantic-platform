"""حزم البيانات تُوجَد أيًّا كانت طريقة التثبيت.

**لماذا:** أول تشغيل لـCI في تاريخ المشروع (2026-07-25) سقط بـ99 اختبارًا،
كلها `BUNDLE_MISSING`. والسبب أن مواضع الحزم كانت تُشتق من
`Path(__file__).resolve().parents[2] / "data"` — وهو صحيح فقط حين تكون
الحزمة مثبتة تثبيتًا **قابلًا للتحرير** كما على جهاز التطوير. وفي CI
تثبيتٌ ناسخ، فأشار `__file__` إلى `site-packages` حيث لا مجلد بيانات.

وصورة الإنتاج كانت تنجو **بالمصادفة** لا بالتصميم: مجلد العمل `/app`
يسبق `site-packages` في مسار البحث فتُحلّ الحزمة من الشجرة المنسوخة.
اعتمادٌ على ترتيب مسار البحث ليس ضمانًا.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.paths import DATA_DIR_ENV, data_dir, data_file, describe_search


def test_both_bundles_resolve_and_are_readable():
    """الحزمتان موجودتان وغير فارغتين — بدونهما لا نصّ ولا صرف."""
    for name, minimum in [
        ("quran_bundle.json.gz", 100_000),
        ("morphology_qac04.json.gz", 1_000_000),
    ]:
        path = data_file(name)
        assert path.exists(), f"{name} غير موجودة\n{describe_search(name)}"
        assert path.stat().st_size > minimum, f"{name} أصغر مما يجب — نسخة مقطوعة؟"


def test_bundles_are_valid_gzip_not_corrupted_by_line_endings():
    """الحزم ثنائية: تحويل نهايات الأسطر يفسدها بصمت.

    المستودع يُستنسخ على ويندوز ولينكس معًا، وGit يحوّل LF↔CRLF في ما
    يعدّه نصًّا. لو عُدَّت حزمة `.gz` نصًّا لفسدت عند الاستنساخ ولم
    يُكتشف ذلك إلا عند أول قراءة."""
    import gzip
    import json

    with gzip.open(data_file("quran_bundle.json.gz"), "rt", encoding="utf-8") as handle:
        bundle = json.load(handle)
    assert len(bundle["ayahs"]) == 6236


def test_golden_cases_file_resolves():
    path = data_file("golden_roots.json")
    assert path.exists(), describe_search("golden_roots.json")


def test_resolution_does_not_depend_on_the_current_directory():
    """تغيير مجلد العمل لا يُضيع الحزم — وهو ما كسر CI."""
    original = Path.cwd()
    try:
        os.chdir(original.parent)
        assert data_file("quran_bundle.json.gz").exists()
    finally:
        os.chdir(original)


def test_the_environment_override_wins(tmp_path, monkeypatch):
    """مخرج النجاة: تخطيط تثبيت غير متوقَّع يُعالَج بمتغير بيئة."""
    (tmp_path / "quran_bundle.json.gz").write_bytes(b"stub")
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    assert data_file("quran_bundle.json.gz") == tmp_path / "quran_bundle.json.gz"
    assert data_dir() == tmp_path


def test_a_missing_bundle_names_every_path_it_searched():
    """الرسالة القديمة قالت «غير موجودة» ولم تقل أين، فأخذ تشخيصها وقتًا."""
    message = describe_search("لا-وجود-له.json")
    assert "لا-وجود-له.json" in message
    assert DATA_DIR_ENV in message
    assert message.count("  - ") >= 1


def test_load_morphology_bundle_error_says_where_it_looked():
    from app.services.morphology import MorphologyError, load_morphology_bundle

    with pytest.raises(MorphologyError) as exc:
        load_morphology_bundle(Path("/no/such/bundle.json.gz"))
    assert exc.value.code == "BUNDLE_MISSING"
    assert "بُحث عن" in exc.value.message
