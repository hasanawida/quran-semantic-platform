#!/usr/bin/env python
"""يبني حزمة المعاجم الثلاثة من ملفات OpenITI — متنًا كلاسيكيًّا خالصًا.

**القرار الحاكم (قرار المالك 2026-07-31 — `docs/audits/OPENITI_MATN_DECISION.md`):**
يُدخَل **متنُ** المعاجم الكلاسيكية الثلاثة نصًّا كاملًا ببحثٍ آليّ بالجذر:

| الكتاب | المؤلف | وفاته |
|---|---|---|
| الصحاح تاج اللغة | الجوهري | ٣٩٣هـ |
| معجم مقاييس اللغة | ابن فارس | ٣٩٥هـ |
| المفردات في غريب القرآن | الراغب الأصفهاني | ٥٠٢هـ |

**والأساس:** المتن ملكُ مؤلفيه الأقدمين منذ ألف عام. وعملُ المحقِّق
المعاصر المحميُّ — المقدمات والحواشي والفهارس — **يُستبعد كلُّه**:

- ملفا ابن فارس والراغب (JK) موسومان في ترويسة نسختهما أنّ OpenITI
  أزالت منهما كل العناصر المصاحبة (عملية Clean، 2023) — فهما متنٌ خالص
  من المنبع.
- ملف الصحاح (Shamela) تُبتر منه المقدماتُ الحديثة (تبدأ الحزمة من أول
  «باب» معجمي)، وتُجرَّد أرقامُ إحالات الحواشي، وتُسقَط أسطرُ الحواشي —
  والحارس `test_lexicon_openiti.py` يثبت ألّا أثر لجهاز المحقق في المنشور.

**والإسناد كامل لا يُخفى:** كل كتابٍ يُنشر مع محقِّقه وناشره وطبعته كما
سجّلتها ترويسة `#META#` نفسها، ومعرِّف OpenITI ورابطه وبصمة الملف — نسبةً
وإحالةً على الطبعة، لا ادّعاءً لترخيصٍ منها.

التشغيل:
    python scripts/import-lexicon/build_openiti.py
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

from app.utils.arabic import normalize_root_input, normalize_surah_name  # noqa: E402

RAW = REPO / "data" / "raw" / "openiti"
OUT = REPO / "apps" / "api" / "data" / "openiti_lexicon.json.gz"
ROOTS = REPO / "apps" / "web" / "public" / "data" / "v1" / "roots.json"
SURAHS = REPO / "apps" / "web" / "public" / "data" / "v1" / "surahs.json"

# أسماء السور المطبَّعة — لفكّ وسم الموضع الملتصق بآخر الآية في المصدر
# (عبس31، الحاقة7، عمران120 من «آل عمران») دون أن تُنتزع كلمةٌ من الآية
# ليست اسمَ سورة.
_SURAH_KEYS: set[str] = {
    normalize_surah_name(s["name"])
    for s in json.loads(SURAHS.read_text(encoding="utf-8"))["surahs"]
}
# «آل عمران» قد يُقطع فلا يبقى داخل الوسم إلا «عمران»
_SURAH_KEYS.add("عمران")

DECISION = (
    "قرار المالك 2026-07-31: يُنشر متنُ المعاجم الكلاسيكية وحده — "
    "مؤلفوها ماتوا قبل تسعة قرون فمتنُها ملكٌ عام — ويُستبعد جهازُ "
    "المحقِّق المعاصر (مقدمات وحواشي وفهارس) وهو موضعُ الحق. والإسناد "
    "إلى الطبعة نسبةٌ وإحالة لا ادّعاءُ ترخيص. التفصيل: "
    "docs/audits/OPENITI_MATN_DECISION.md"
)

GITHUB = "https://raw.githubusercontent.com/OpenITI"

BOOKS = [
    {
        "key": "sihah_jawhari",
        "file": "sihah.Shamela0023235.txt",
        "parser": "sihah",
        "openiti_uri": "0393IbnHammadJawhari.SihahTajLugha.Shamela0023235-ara1",
        "source_url": (
            f"{GITHUB}/0400AH/master/data/0393IbnHammadJawhari/"
            "0393IbnHammadJawhari.SihahTajLugha/"
            "0393IbnHammadJawhari.SihahTajLugha.Shamela0023235-ara1"
        ),
        # الملف غير موسوم Clean فتُنفَّذ الإزالة عندنا (انظر _parse_sihah)
        "apparatus": "المقدمات الحديثة مبتورة وأرقام الحواشي مجرَّدة عندنا",
    },
    {
        "key": "maqayis",
        "file": "maqayis.JK008008.txt",
        "parser": "maqayis",
        "openiti_uri": "0395IbnFarisQazwini.MucjamMaqayis.JK008008-ara1",
        "source_url": (
            f"{GITHUB}/0400AH/master/data/0395IbnFarisQazwini/"
            "0395IbnFarisQazwini.MucjamMaqayis/"
            "0395IbnFarisQazwini.MucjamMaqayis.JK008008-ara1"
        ),
        "apparatus": "أزالتها OpenITI من المنبع (Clean 2023) — موثَّق في ترويسة النسخة",
    },
    {
        "key": "mufradat",
        "file": "mufradat.JK001150.txt",
        "parser": "mufradat",
        "openiti_uri": "0502RaghibIsbahani.Mufradat.JK001150-ara1",
        "source_url": (
            f"{GITHUB}/0525AH/master/data/0502RaghibIsbahani/"
            "0502RaghibIsbahani.Mufradat/"
            "0502RaghibIsbahani.Mufradat.JK001150-ara1"
        ),
        "apparatus": "أزالتها OpenITI من المنبع (Clean 2023) — موثَّق في ترويسة النسخة",
    },
    {
        # الرابع — أشمل المعاجم: يسدّ ما لم تبلغه الثلاثة ويعمّق الباقي
        "key": "lisan",
        "file": "lisan.JK000880.txt",
        "parser": "lisan",
        "openiti_uri": "0711IbnManzurIfriqi.LisanCarab.JK000880-ara1",
        "source_url": (
            f"{GITHUB}/0725AH/master/data/0711IbnManzurIfriqi/"
            "0711IbnManzurIfriqi.LisanCarab/"
            "0711IbnManzurIfriqi.LisanCarab.JK000880-ara1"
        ),
        "apparatus": "أزالتها OpenITI من المنبع (Clean 2023) — موثَّق في ترويسة النسخة",
    },
]

PAGE = re.compile(r"PageV(\d+)P(\d+)")
MILESTONE = re.compile(r"\s*(?:@\d+@|ms\d+)\s*")
FOOTNOTE_REF = re.compile(r"\s*\(\d+\)")
QURAN_MUFRADAT = re.compile(r"@QB@\s*(.*?)\s*@QE@", re.S)
QURAN_MAQAYIS = re.compile(r"\^\s*\(\s*(.*?)\s*\)\s*\^", re.S)
WS = re.compile(r"\s+")


def _meta(text: str) -> dict[str, str]:
    """يقرأ ترويسة `#META#` — فالإسناد من الملف نفسه لا من حفظنا."""
    fields: dict[str, str] = {}
    for line in text.split("#META#Header#End#", 1)[0].splitlines():
        match = re.match(r"#META# (\S+)\t*::\s*(.*)", line)
        if match and match.group(2).strip() not in ("", "NODATA", "NOTGIVEN", "NOCODE"):
            fields[match.group(1)] = match.group(2).strip()
    return fields


def _quran_quote(match: re.Match) -> str:
    """يصوغ سياج آيةٍ اقتبسها المعجم: «الآية» ثم وسمُ موضعها إن وُجد.

    المصدر يلصق وسمَ الموضع بآخر الآية (حتى تكون حرضا يوسف85)، فيُفصل
    عن اللفظ القرآني إلى ما بعد القوسين. ولا يُفصل إلا ما ثبت أنه اسمُ
    سورةٍ حقًّا — فكلمةٌ أخيرة تُشبه الوسم وليست سورةً تبقى في مكانها."""
    inner = WS.sub(" ", match.group(1)).strip()
    tagged = re.match(r"(.*?)\s*((?:آل )?[ء-ي]{2,})(\d{1,3})$", inner)
    if tagged and normalize_surah_name(tagged.group(2)) in _SURAH_KEYS:
        name = tagged.group(2)
        if name == "عمران":
            name = "آل عمران"
        verse = tagged.group(1).removesuffix("آل").strip()
        return f"«{verse}» ({name} {tagged.group(3)})"
    return f"«{inner}»"


def _clean(text: str, *, book: str) -> str:
    """يجرّد نصَّ مادةٍ من ترميز mARkdown إلى متنٍ مقروء."""
    # `# |` و `# ` بداياتُ فقرات، و `~~` وصلُ أسطر — تُزال أولًا حتى لا
    # يتسرب أثرها إلى داخل سياج الآيات الممتد عبر الأسطر
    text = re.sub(r"^#+ ?\|?", "", text, flags=re.M)
    text = re.sub(r"^~~", "", text, flags=re.M)
    # سياجا الآيات كلاهما في كل كتاب: المقاييس مثلًا يستعمل `^(…)^`
    # و`@QB@…@QE@` معًا — كشفه الحارس test_no_openiti_markup_survives
    text = QURAN_MUFRADAT.sub(_quran_quote, text)
    text = QURAN_MAQAYIS.sub(_quran_quote, text)
    # سياجٌ أعرج في المصدر (فتحٌ بلا إغلاق أو العكس، وسياجان يتشاركان
    # علامة): يُلتقط ما بقي بعد الصحيح، ثم تُمحى العلامة اليتيمة
    text = re.sub(r"\^\s*\(([^()^]*)\)", _quran_quote, text)
    text = text.replace("^", " ")
    # وسمُ فتحٍ مكرر بلا إغلاق (@QB@ أ @QB@ ب @QE@): ما بقي يُقلب قوسَي
    # اقتباس مباشرةً بدل أن يصل القارئ خامًا
    text = text.replace("@QB@", "«").replace("@QE@", "»")
    if book == "sihah_jawhari":
        # أرقامُ إحالات حواشي المحقِّق — الجهاز نفسه غير منقول أصلًا
        text = FOOTNOTE_REF.sub("", text)
    text = PAGE.sub(" ", text)
    text = MILESTONE.sub(" ", text)
    text = text.replace("%", "·")  # سياج الأبيات
    if book == "maqayis":
        text = text.replace(" | ", " · ")
    if book == "lisan":
        # فواصل المواد `[ * ]` وبقايا علامات الفتح `]` وأرقامُ إحالات
        # الحواشي المتباعدة `( 2 )` — جهازُها نفسه محذوف من المنبع
        text = text.replace("[ * ]", " ").replace("[", " ").replace("]", " ")
        text = re.sub(r"\( ?\d+ ?\)", "", text)
        text = text.replace(" | ", " · ")
    return WS.sub(" ", text).strip(" ·|-—")


def _page_of(matn: str, position: int) -> str | None:
    """آخرُ علامة صفحةٍ قبل الموضع: النصُّ بعد العلامة على صفحتها."""
    last = None
    for match in PAGE.finditer(matn, 0, position):
        last = match
    if last is None:
        return None
    return f"ج{int(last.group(1))} ص{int(last.group(2))}"


def _entries_sihah(matn: str) -> list[tuple[str, str, str | None]]:
    """الصحاح: رؤوسه معقوفة `### | [أجأ]` — أوضحُ الثلاثة.

    تُبتر المقدماتُ الحديثة ببدء المعالجة من أول «باب» معجمي، وتُسقَط
    أسطرُ الحواشي (تبدأ برقمٍ بين قوسين)."""
    start = re.search(r"^### \| باب ", matn, re.M)
    if not start:
        raise SystemExit("الصحاح: لم يُعثر على أول باب — بنية الملف تغيّرت")
    matn = matn[start.start() :]
    matn = re.sub(r"^# \(\d+\).*$", "", matn, flags=re.M)  # أسطر الحواشي

    # الرأس قد تلحقه نقطة في المصدر («[حقق] .») — الصرامة هنا أسقطت موادَّ
    heads = list(re.finditer(r"^### \| \[([^\]\n]+)\][ .]*$", matn, re.M))
    out = []
    for i, match in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(matn)
        body = matn[match.end() : end]
        # رؤوس البنية (فصل/باب) داخل المدى تُحذف ولا تقطع المادة
        body = re.sub(r"^### \|.*$", "", body, flags=re.M)
        out.append((match.group(1), body, _page_of(matn, match.start())))
    return out


def _entries_mufradat(matn: str) -> list[tuple[str, str, str | None]]:
    """المفردات: رأسُ المادة `# كلمة : …` — الكلمةُ ساقُ اللفظ القرآني."""
    heads = list(re.finditer(r"^# ([ء-ي]{2,6}) : ", matn, re.M))
    out = []
    for i, match in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(matn)
        body = matn[match.end() : end]
        out.append((match.group(1), body, _page_of(matn, match.start())))
    return out


def _entries_maqayis(matn: str) -> list[tuple[str, str, str | None]]:
    """مقاييس اللغة: رؤوسه `( جذر )` جاريةٌ في السياق.

    كلُّ `( كلمة عربية قصيرة )` خارج سياج القرآن `^(…)^` مرشَّحُ رأسٍ،
    وكلُّ مرشّحٍ **يقطع** المادةَ قبله ولو لم يكن جذرًا قرآنيًّا — فغيرُ
    القرآني مادةٌ لجذرٍ ليس في المصحف، لا جزءًا من التي قبله."""
    # سياج القرآن يُطمس مؤقتًا كي لا تُلتقط أقواسه رؤوسًا
    masked = QURAN_MAQAYIS.sub(lambda m: " " * len(m.group(0)), matn)
    heads = list(re.finditer(r"\( ([ء-ي]{2,5}) \)", masked))
    out = []
    for i, match in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(matn)
        body = matn[match.end() : end]
        out.append((match.group(1), body, _page_of(matn, match.start())))
    return out


def _entries_lisan(matn: str) -> list[tuple[str, str, str | None]]:
    """لسان العرب (نسخة JK المنظَّفة): رأس المادة سطرٌ مفرد `# أبأ` يليه
    متنها مفتتحًا `# ] أبأ : …` — فيُشترط الافتتاحُ المؤكِّد لئلا تُحسب
    كلمةٌ منفردةٌ عابرة رأسًا، وتفصل المواد علامات `[ * ]`."""
    heads = list(
        re.finditer(r"^# ([ء-ي]{2,7})\s*\n# \] \1 ?:", matn, re.M)
    )
    out = []
    for i, match in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(matn)
        body = matn[match.end() : end]
        out.append((match.group(1), body, _page_of(matn, match.start())))
    return out


PARSERS = {
    "sihah": _entries_sihah,
    "mufradat": _entries_mufradat,
    "maqayis": _entries_maqayis,
    "lisan": _entries_lisan,
}


def _fallback_keys(key: str) -> list[str]:
    """مفاتيح احتياطية لرأسٍ لم يطابق بحرفه — كلُّها أعرافٌ معجمية مقيسة:

    - المضعّف يُكتب بحرفين: «حق» والجذر عندنا «حقق».
    - المعتلّ اللام يُكتب بالألف: «سما» جذره «سمو»، و«عصا» تجمع الواويَّ
      واليائيَّ معًا فتُرَدُّ إلى كليهما إن وُجدا (عصو وعصي).
    - الأجوف يُكتب بألفٍ وسطى: «لات» جذره «لوت» أو «ليت».

    ولا يُنشر مفتاحٌ منها إلا إذا كان جذرًا قرآنيًّا قائمًا في فهرسنا —
    فالاحتياط يوسّع البحث لا الصدق."""
    out: list[str] = []
    if len(key) == 2:
        out.append(key + key[1])
    if len(key) >= 3 and key[-1] == "ا":
        out += [key[:-1] + "و", key[:-1] + "ي"]
    if len(key) == 3 and key[1] == "ا":
        out += [key[0] + "و" + key[2], key[0] + "ي" + key[2]]
    # الاسم بحروف مدّه (خنزير، قنطار) وجذرُنا هيكلُه (خنزر، قنطر)
    if len(key) >= 5:
        stripped = key.translate(str.maketrans("", "", "اوي"))
        if len(stripped) >= 4:
            out.append(stripped)
    return out


# مواضع تحقَّقنا منها بقراءة المصدر: الكلمة القرآنية درجت في مادة أصلٍ
# آخر (العنكبوت في «عكب»، القنطار في «قطر»). لا يُنسب الجذرُ إلى المادة
# الحاضنة إلا إذا وردت الكلمةُ الشاهدة في متنها فعلًا — فالقيد في الشيفرة
# لا في الذاكرة، وتبدُّل المصدر يكشفه سقوطُ الشرط.
VERIFIED_HOSTS: dict[str, tuple[str, str]] = {
    # الجذر ← (مفتاح المادة الحاضنة مطبَّعًا، الكلمة الشاهدة في متنها)
    "عنكب": ("عكب", "عنكبوت"),
    "قنطر": ("قطر", "قنطار"),
    "سنبل": ("سبل", "سنبل"),
    "فاي": ("فيا", "فئة"),  # «فيأ» تُطبَّع «فيا»، والفئة مذكورة في مادته
    "جيد": ("جود", "الجيد"),
    "كوكب": ("ككب", "كوكب"),
}


def _reduplicated_parent_keys(root_key: str) -> list[str]:
    """الرباعي المكرر (زلزل) تُدرجه المعاجم في مادة ثنائيِّه: زلل أو زل."""
    if len(root_key) == 4 and root_key[:2] == root_key[2:]:
        pair = root_key[:2]
        return [pair + pair[1], pair]
    return []


def main() -> int:
    our_roots: list[str] = json.loads(ROOTS.read_text(encoding="utf-8"))["roots"]
    keyed = {normalize_root_input(r): r for r in our_roots}

    books_meta: dict[str, dict] = {}
    entries: dict[str, dict[str, list[dict]]] = {}
    dropped: dict[str, int] = {}

    for book in BOOKS:
        path = RAW / book["file"]
        raw_bytes = path.read_bytes()
        text = raw_bytes.decode("utf-8")
        meta = _meta(text)
        matn = text.split("#META#Header#End#", 1)[1]

        parsed = PARSERS[book["parser"]](matn)
        matched = 0
        # فهرس رؤوس الكتاب — للممر العكسي (الرباعي المكرر) أدناه
        head_index: dict[str, tuple[str, str, str | None]] = {}
        for head, body, page in parsed:
            key = normalize_root_input(head)
            head_index.setdefault(key, (head, body, page))
            raw_last = head.strip()[-1:] if head.strip() else ""
            if raw_last == "ا":
                # رأسٌ بألفٍ عارية معتلُّ اللام قطعًا — فالمعاجم تكتب
                # المهموز بهمزته ([نسأ] مادة مستقلة عن [نسا]). والتطبيع
                # يُسوّي «نسا» بـ«نسأ» فيخطفها المهموزُ ويضيع الواويُّ —
                # فيُقدَّم الواوي واليائي، ولا يُرجَع للمهموز إلا عدمهما
                weak = [
                    keyed[k]
                    for k in (key[:-1] + "و", key[:-1] + "ي")
                    if k in keyed
                ]
                roots_hit = weak or ([keyed[key]] if key in keyed else [])
            else:
                roots_hit = [keyed[key]] if key in keyed else []
            if not roots_hit:
                # الأعراف المعجمية: مضعّف بحرفين، معتلٌّ بالألف، أجوف —
                # وقد يعود الرأس الواحد (عصا) إلى جذرين قائمين (عصو وعصي)
                roots_hit = [
                    keyed[k] for k in _fallback_keys(key) if k in keyed
                ]
            if not roots_hit:
                dropped[book["key"]] = dropped.get(book["key"], 0) + 1
                continue
            cleaned = _clean(body, book=book["key"])
            if len(cleaned) < 25:
                continue
            record = {"head": head, "text": cleaned}
            if page:
                record["page"] = page
            for root in roots_hit:
                entries.setdefault(root, {}).setdefault(book["key"], []).append(
                    record
                )
                matched += 1

        # الممر العكسي: جذرٌ رباعي مكرر (زلزل) بابُه في المعاجم مادةُ
        # ثنائيِّه (زلل/زل) — يُلتمس رأسُ الأصل ويُنسب إليه بِرأسه الصادق
        for root in our_roots:
            if book["key"] in entries.get(root, {}):
                continue
            for parent_key in _reduplicated_parent_keys(normalize_root_input(root)):
                found = head_index.get(parent_key)
                if not found:
                    continue
                head, body, page = found
                cleaned = _clean(body, book=book["key"])
                if len(cleaned) < 25:
                    continue
                record = {"head": head, "text": cleaned}
                if page:
                    record["page"] = page
                entries.setdefault(root, {}).setdefault(book["key"], []).append(
                    record
                )
                matched += 1
                break

        # المواضع المتحقَّق منها: الكلمة درجت في مادة أصلٍ آخر — الشرط
        # أن ترد الكلمةُ الشاهدة في متن المادة الحاضنة، وإلا لا نسبة
        for root, (host_key, witness) in VERIFIED_HOSTS.items():
            if book["key"] in entries.get(root, {}):
                continue
            found = head_index.get(host_key)
            if not found or witness not in found[1]:
                continue
            head, body, page = found
            cleaned = _clean(body, book=book["key"])
            if len(cleaned) < 25:
                continue
            record = {"head": head, "text": cleaned}
            if page:
                record["page"] = page
            entries.setdefault(root, {}).setdefault(book["key"], []).append(record)
            matched += 1

        books_meta[book["key"]] = {
            "title": meta.get("020.BookTITLE", ""),
            "author": meta.get("010.AuthorNAME", meta.get("010.AuthorAKA", "")),
            "author_died_hijri": meta.get("011.AuthorDIED", ""),
            # طبعة دار صادر للسان لا تسمّي محقِّقًا — يُقال ذلك ولا يُخترع اسم
            "editor": meta.get("040.EdEDITOR", "غير مسمًّى في ترويسة المصدر"),
            "publisher": meta.get("043.EdPUBLISHER", ""),
            "edition": " · ".join(
                v
                for v in (
                    meta.get("041.EdNUMBER", ""),
                    meta.get("044.EdPLACE", ""),
                    meta.get("045.EdYEAR", ""),
                )
                if v
            ),
            "openiti_uri": book["openiti_uri"],
            "source_url": book["source_url"],
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "apparatus": book["apparatus"],
            "entries_matched": matched,
            "entries_unmatched_roots": dropped.get(book["key"], 0),
        }

    bundle = {
        "meta": {
            "decision": DECISION,
            "statement": (
                "المتون لمؤلفيها الأقدمين (ت ٣٩٣هـ، ٣٩٥هـ، ٥٠٢هـ، ٧١١هـ) "
                "وهي ملك عام. أُخذت نصوصها من مدونة OpenITI، واستُبعد منها "
                "جهاز المحقِّق المعاصر كلُّه. وكل كتابٍ منشور بمحقِّقه "
                "وناشره وطبعته وبصمة ملفه — فالقارئ يعلم من أين جاء كل حرف."
            ),
            "review_status": "imported",
            "books": books_meta,
            "roots_covered": len(entries),
            "roots_total": len(our_roots),
        },
        "entries": entries,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as handle:
        json.dump(bundle, handle, ensure_ascii=False, separators=(",", ":"))

    print(f"جذور مغطاة: {len(entries)} من {len(our_roots)}")
    for key, m in books_meta.items():
        print(
            f"  {key}: {m['entries_matched']} مادة مطابقة"
            f" · {m['entries_unmatched_roots']} رأس غير قرآني"
        )
    print(f"كُتب: {OUT} ({OUT.stat().st_size:,} بايت)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
