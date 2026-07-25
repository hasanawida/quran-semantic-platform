"""حارس الرخصة والإسناد.

**لماذا:** فحص جاهزية النشر في 2026-07-25 وجد المشروع بلا ملف رخصة
البتة، بينما حزمتان مشتقتان من بيانات مرخّصة GPL محفوظتان داخل الشجرة.
نشر المستودع بهذه الحال توزيعٌ بلا رخصة، وخرقٌ لشرط المصدر.

والأدقّ من ذلك خطرًا: الخلط بين رخصة الشيفرة وشروط البيانات. رخصة ليدز
تشترط **الاستعمال غير التجاري**، وAGPL تبيح التجاري. ادعاءٌ واحد يجمعهما
يُضلّل من يبني على المنصة — فيُفصَل بينهما نصًّا، ويُحرس الفصل هنا.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_license_file_exists_and_is_the_real_agpl():
    """نص الرخصة كامل لا مقتطع — رخصة منقوصة أسوأ من لا رخصة."""
    license_text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in license_text
    assert "Version 3, 19 November 2007" in license_text
    # المادة 13 هي جوهر AGPL وما يميّزها عن GPL: التشغيل عبر الشبكة
    assert "13. Remote Network Interaction" in license_text
    # وطولها المعروف — يكشف القصّ
    assert len(license_text.splitlines()) > 600


def test_notice_separates_code_licence_from_data_conditions():
    """الفصل صريح: AGPL للشيفرة، وشروط أصحابها للبيانات."""
    notice = (REPO_ROOT / "NOTICE").read_text(encoding="utf-8")

    # رخصة الشيفرة معلنة
    assert "AGPL-3.0" in notice
    # وشرط ليدز غير التجاري مذكور صراحةً لا مطويًّا
    assert "غير التجاري" in notice
    # ولا يُدّعى أن AGPL تشمل البيانات
    assert "رخصها مستقلة" in notice or "لا تشملها" in notice

    # والمصدران بروابطهما
    for required in ("tanzil.net", "corpus.quran.com"):
        assert required in notice, required


def test_both_packages_declare_the_licence():
    """الرخصة في بيانات الحزمتين كذلك، لا في ملف الجذر وحده."""
    pyproject = (REPO_ROOT / "apps" / "api" / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert 'license = "AGPL-3.0-or-later"' in pyproject

    package_json = (REPO_ROOT / "apps" / "web" / "package.json").read_text(
        encoding="utf-8"
    )
    assert '"license": "AGPL-3.0-or-later"' in package_json


def test_readme_points_to_the_notice_not_just_the_licence():
    """قارئ README يجب أن يعرف بالقيد غير التجاري قبل أن يبني عليه."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "NOTICE" in readme
    assert "غير التجاري" in readme
