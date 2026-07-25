"""حارس الروابط الداخلية: لا رابط إلى مسار لا وجود له.

**لماذا:** بعد التحويل إلى الموقع الثابت صار `/ayah/{س}/{آ}` و
`/root/{جذر}` معاملَي استعلام (`/ayah?s=&a=` و`/root?r=`)، وحُذف
المساران المولَّدان. لكن أربعة روابط بقيت على الشكل القديم في ملفين
بُنيا **بعد** تشغيل مُصلِح الروابط، فأفلتا منه.

والأخطر أن العطب **مرّ من كل الحُرّاس**: فحص الأنواع لا يعرف المسارات،
والبناء ينجح لأن `<Link href>` نصٌّ حرّ، وCI خضراء. ولم يظهر إلا حين
ضغط مستعمل على كلمة في المصحف فوصل إلى 404.

فالحارس هنا يفحص ما لا يفحصه المترجم: **كل رابط داخلي يقابل صفحة
موجودة فعلًا في شجرة `app/`.**
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
APP = REPO / "apps" / "web" / "app"

# `<Link href="/x">` أو href={`/x/${y}`}
HREF = re.compile(r"""href=(?:"(/[^"]*)"|\{`(/[^`]*)`\})""")

# مسارات خارجية أو خاصة لا تُفحص
SKIP_PREFIXES = ("/api/", "/#", "/data/")


def _routes() -> set[str]:
    """المسارات الموجودة فعلًا، مشتقّة من ملفات الصفحات لا مكتوبة يدويًا."""
    found = {"/"}
    for page in APP.rglob("page.tsx"):
        rel = page.parent.relative_to(APP).as_posix()
        found.add("/" if rel == "." else f"/{rel}")
    # الصفحات المحلية (page.node.tsx) موجودة خارج الموقع الثابت
    for page in APP.rglob("page.node.tsx"):
        rel = page.parent.relative_to(APP).as_posix()
        found.add(f"/{rel}")
    return found


def _static_prefix(href: str) -> str:
    """الجزء الثابت من الرابط قبل أول تعويض أو معامل استعلام."""
    href = href.split("?")[0].split("#")[0]
    if "${" in href:
        href = href[: href.index("${")]
    return href.rstrip("/") or "/"


def test_every_internal_link_points_at_a_real_route():
    """لا رابط إلى مسار محذوف — وهو ما جعل الضغط على كلمة يعطي 404."""
    routes = _routes()
    # المسارات ذات المعاملات المتغيّرة: يكفي أن يوجد أصلها
    dynamic = {re.sub(r"/\[[^\]]+\]", "", route) or "/" for route in routes}
    known = routes | dynamic

    broken: list[str] = []
    for page in list(APP.rglob("*.tsx")) + list(APP.rglob("*.ts")):
        text = page.read_text(encoding="utf-8")
        for match in HREF.finditer(text):
            href = match.group(1) or match.group(2)
            if href.startswith(SKIP_PREFIXES):
                continue
            prefix = _static_prefix(href)
            if prefix in known:
                continue
            # مسار ديناميكي: /mushaf/${n} ⇐ يقابل /mushaf/[surah]
            if any(
                route.startswith(prefix + "/") and "[" in route for route in routes
            ):
                continue
            rel = page.relative_to(REPO).as_posix()
            broken.append(f"{rel}: {href}")

    assert not broken, "روابط إلى مسارات غير موجودة:\n  " + "\n  ".join(broken)


def test_the_query_param_routes_exist_after_the_static_move():
    """المساران اللذان حلّا محلّ المسارين المولَّدين موجودان."""
    routes = _routes()
    assert "/ayah" in routes, "مسار /ayah مفقود"
    assert "/root" in routes, "مسار /root مفقود"
    # والمسارات المولَّدة القديمة محذوفة فعلًا
    assert not (APP / "ayah" / "[surah]").exists()
    assert not (APP / "root" / "[root]").exists()


def test_no_link_uses_the_removed_dynamic_shape():
    """الشكل القديم `/ayah/${س}/${آ}` و`/root/${ج}` لا يعود أبدًا."""
    stale = re.compile(r"`/(?:ayah|root)/\$\{")
    hits = [
        f"{page.relative_to(REPO).as_posix()}:{n}"
        for page in APP.rglob("*.tsx")
        for n, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1)
        if stale.search(line)
    ]
    assert not hits, (
        "روابط بالشكل المحذوف — تعطي 404 على الموقع الثابت:\n  "
        + "\n  ".join(hits)
    )
