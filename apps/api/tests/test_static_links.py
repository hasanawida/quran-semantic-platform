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
    return found


def _local_only_routes() -> set[str]:
    """صفحات `page.node.tsx` — موجودة محليًا و**معدومة في الموقع الثابت**.

    `pageExtensions` في next.config.ts تُسقطها من التصدير، فأي رابط
    إليها من صفحة تُشحن ثابتًا يعطي 404 للزائر."""
    return {
        f"/{page.parent.relative_to(APP).as_posix()}"
        for page in APP.rglob("page.node.tsx")
    }


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
    # الصفحات المحلية موجودة في المستودع — وجودُها هنا يعني «ليست
    # مسارًا معدومًا»، أما كونها معدومة في الموقع الثابت فيحرسه الاختبار
    # الأخير وحده. الفصل مقصود: خطآن مختلفان برسالتين مختلفتين.
    known = routes | dynamic | _local_only_routes()

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


def test_no_static_page_links_to_a_local_only_page():
    """الثغرة التي فاتت الحارس نفسه — وكشفتها مراجعة خارجية.

    كان `_routes()` يعدّ صفحات `page.node.tsx` مساراتٍ صالحة، فمرّ رابط
    الشريط إلى `/claims` وهو معدوم في الموقع الثابت: الزائر يضغطه فيصله
    404. وحارسٌ يعدّ ما لا يُنشر موجودًا يحرس نفسه لا الموقع.

    فالشرط الآن: صفحةٌ تُشحن ثابتًا لا تربط بصفحة محلية إلا خلف
    `STATIC`."""
    local = _local_only_routes()
    assert local, "لا صفحات محلية — أتغيّر التخطيط؟"

    broken: list[str] = []
    for page in APP.rglob("*.tsx"):
        if page.name.endswith(".node.tsx"):
            continue  # صفحة محلية تربط بمحلية: لا بأس
        text = page.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            for match in HREF.finditer(line):
                href = (match.group(1) or match.group(2)).split("?")[0].rstrip("/")
                if href not in local:
                    continue
                # مقبول إن كان خلف حارس الوضع الثابت. والنافذة عشرون
                # سطرًا لأن الشرط قد يلفّ كتلة JSX كاملة (كتلة المستخدم
                # في الشريط تمتدّ أربعة عشر سطرًا بين الحارس والرابط).
                window = " ".join(
                    text.splitlines()[max(0, number - 20) : number]
                )
                if "STATIC" in window:
                    continue
                rel = page.relative_to(REPO).as_posix()
                broken.append(f"{rel}:{number} → {href}")

    assert not broken, (
        "روابط إلى صفحات معدومة في الموقع الثابت (تعطي 404 للزائر):\n  "
        + "\n  ".join(broken)
        + "\nالعلاج: لُفّها بـ{!STATIC && …} أو احذفها."
    )
