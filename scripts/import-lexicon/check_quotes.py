#!/usr/bin/env python
"""يقابل كلَّ اقتباسٍ في نسخ «مختار الصحاح» بنصِّ المصحف الموثَّق.

**لماذا هذا الحارس قائمٌ بذاته:** المعجم يستشهد بالآيات، والناسخ — بشرًا
كان أو وكيلًا — قد يُسقط كلمةً أو يُبدل حرفًا وهو يقرأ صورةً باهتة. وخطأٌ
في لفظٍ عاديٍّ يُصحَّح في مراجعة، أمَّا خطأٌ في آيةٍ فتحريفٌ يُنشر باسم
المصحف. فالمقابلة هنا **حتمية لا بصرية**: نصّ المنصة المبصوم هو الحَكَم،
لا عينُ الناسخ ولا ذاكرةُ النموذج.

وليس كلُّ ما بين «…» آيةً: في المعجم أحاديثُ وقراءاتٌ شاذّة وأشعارٌ
وأمثال. فالقاعدة المنفَّذة: **كلُّ اقتباسٍ إمّا أن يطابق آيةً، وإمّا أن
يكون مُعلَنًا في `non-quran-quotes.md` بسببه**. فلا يمرّ اقتباسٌ مجهولٌ
صامتًا، ولا يُتَّهم حديثٌ بأنه آية محرَّفة.

والاقتباس قد ينفتح آخرَ صفحةٍ وينغلق في التالية، فتُوصل الصفحات المتّصلة
قبل الاستخراج.

التشغيل:
    python scripts/import-lexicon/check_quotes.py          # تقرير
    python scripts/import-lexicon/check_quotes.py --json   # للأدوات
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "apps" / "api"))

from app.utils.arabic import normalize_arabic_search  # noqa: E402

PAGES_DIR = REPO / "data" / "transcriptions" / "mukhtar-sihah-1920"
QURAN = REPO / "apps" / "api" / "data" / "quran_bundle.json.gz"
DECLARED = PAGES_DIR / "quotes-not-quran.md"
# صفحاتُ النسخ وحدها: `n*.md` كان يبتلع أيَّ ملفٍّ آخر في المجلد
PAGE_FILE = "n[0-9]*.md"

FLAG = re.compile(r"⟨[^⟩]*⟩")
QUOTE = re.compile(r"«([^»]*)»")
# المطبوع يحوّط الكلمةَ المشروحة بقوسين داخل الاقتباس نفسه: «وكان له
# (ثُمُـر)» — والقوسان علامةُ المعجم لا من لفظ الآية. فإبقاؤهما يمنع
# مطابقةَ آيةٍ صحيحة، فتُتَّهم بأنها ليست قرآنًا. تُنزع للمقابلة وحدها،
# والنصُّ المعروض يبقى كما نُسخ.
MARKUP = re.compile(r"[()]")
# «لايَبْغُونَ» في النسخ و﴿لَا يَبْغُونَ﴾ في المصحف: فَقْدُ مسافةٍ في
# النسخ يمنع المطابقة. يُلتمَس الوصلُ للعثور، ويُبلَّغ عنه ليُصحَّح.
GLUED = re.compile(r"\s+")

# الألف الخنجرية في الرسم العثماني: ﴿خِتَـٰمُهُۥ﴾ ألفُها فوقيّة والمعجم
# يكتبها مبسوطة «ختامه»، والمطبِّع العام يحذفها فيصير الرسمان «ختمه»
# و«ختامه» فلا يلتقيان — فتُتَّهم آيةٌ صحيحة بأنها ليست قرآنًا.
#
# ولا يصلح إبدالُها ألفًا مطلقًا: ﴿حَتَّىٰ﴾ و﴿عَلَىٰ﴾ و﴿ٱلْهُدَىٰ﴾ ألفُها
# الفوقيةُ فوق ياءٍ تنوب عنها، فإبدالُها يُخرج «حتىا» و«علىا». فالوجهان
# محتملان في الرسم، والمفتاحان يُبنيان معًا ويُقبل ما التقى بأحدهما.
DAGGER_ALEF = "ٰ"
# والهمزةُ مثلُ الألف: المصحف يرسم ﴿تَسْـَٔلُهُمْ﴾ بهمزةٍ على السطر والمعجم
# «تَسْأَلُهُمْ» بهمزةٍ على ألف، فتسقط آيةٌ صحيحة بفرق رسمٍ لا لفظ.
#
# ولا يكفي إسقاطُ الهمزة **بعد** التطبيع: `normalize_arabic_search` يردّ
# همزة المصحف المركَّبة إلى «ئ» ثم إلى «ي»، وهمزةَ المعجم «أ» إلى «ا»،
# فيفترق الحرفان ياءً وألفًا قبل أن تعمل الشبكة. فتُنزع صورُ الهمزة كلها
# من النصّ **الخام** قبل التطبيع، فيلتقي الرسمان على هيكلٍ واحد.
HAMZA_FORMS = str.maketrans("", "", "ءأإآؤئٕٔ")
ALEF_FORMS = str.maketrans("", "", "اأإآٱى")


def quote_keys(value: str) -> set[str]:
    """مفتاحا المقابلة: الألفُ الفوقية محذوفةً، ومبسوطةً."""
    value = MARKUP.sub("", value)
    return {
        normalize_arabic_search(value.replace(DAGGER_ALEF, "")).strip(),
        normalize_arabic_search(value.replace(DAGGER_ALEF, "ا")).strip(),
    } - {""}


def alef_blind(value: str) -> str:
    """شبكةٌ أخيرة: رسمُ الألف يختلف بين المصحف والمعجم في مواضع أخرى.

    للعثور وحدَه — والموضعُ المعثور عليه يُعرض بمرجعه ليراه إنسان، فلا
    يُبنى على هذا التساهل حكمُ صحّةٍ بل دلالةُ مكان."""
    raw = MARKUP.sub("", value).replace(DAGGER_ALEF, "").translate(HAMZA_FORMS)
    return normalize_arabic_search(raw).translate(ALEF_FORMS)


def load_pages() -> list[dict]:
    """الصفحات مرتَّبةً بترتيب المصوَّرة، مع متونها مجرَّدةً من علامات الناسخ."""
    pages = []
    for path in sorted(PAGES_DIR.glob(PAGE_FILE)):
        text = path.read_text(encoding="utf-8")
        _, header, body = text.split("---", 2)
        fields = {}
        for line in header.strip().splitlines():
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip("'\"")
        pages.append(
            {
                "file": path.name,
                "archive_page": int(fields["archive_page"]),
                "printed_page": int(fields["printed_page"]),
                "body": FLAG.sub("", body),
            }
        )
    return sorted(pages, key=lambda p: p["archive_page"])


def extract_quotes(pages: list[dict]) -> list[dict]:
    """يستخرج الاقتباسات، ويصل ما انفتح في صفحةٍ وانغلق في تاليتها.

    الوصل مشروطٌ باتصال الصفحتين في المصوَّرة: فاقتباسٌ مفتوحٌ آخرَ ص١١٤
    لا يُغلق بصفحةٍ من ص٢٠٠ لم يُنسخ ما بينهما."""
    quotes: list[dict] = []
    carry: dict | None = None
    prev_archive: int | None = None

    for page in pages:
        body = page["body"]
        # ما انفتح في الصفحة السابقة يُغلَق هنا إن كانت الصفحتان متّصلتين
        if carry is not None:
            if prev_archive is not None and page["archive_page"] == prev_archive + 1:
                head, sep, rest = body.partition("»")
                if sep:
                    carry["text"] = f"{carry['text']} {head}".strip()
                    carry["pages"].append(page["printed_page"])
                    quotes.append(carry)
                    body = rest
                else:  # اقتباسٌ يمتدّ صفحةً كاملة: نادر، ويُترك مبتورًا معلنًا
                    carry["truncated"] = True
                    quotes.append(carry)
            else:
                carry["truncated"] = True
                quotes.append(carry)
            carry = None

        for match in QUOTE.finditer(body):
            quotes.append(
                {
                    "text": match.group(1).strip(),
                    "pages": [page["printed_page"]],
                    "file": page["file"],
                    "truncated": False,
                }
            )
        # اقتباسٌ فُتح ولم يُغلق حتى آخر الصفحة
        tail = body.rsplit("»", 1)[-1] if "»" in body else body
        if "«" in tail:
            carry = {
                "text": tail.rsplit("«", 1)[-1].strip(),
                "pages": [page["printed_page"]],
                "file": page["file"],
                "truncated": False,
            }
        prev_archive = page["archive_page"]

    if carry is not None:
        carry["truncated"] = True
        quotes.append(carry)
    return quotes


def load_corpus() -> list[tuple[int, int, set[str], str]]:
    """كل آية بمفاتيحها: وجها الألف الفوقية، ثم الأعمى عن رسم الألف."""
    with gzip.open(QURAN, "rt", encoding="utf-8") as handle:
        bundle = json.load(handle)
    return [(s, a, quote_keys(t), alef_blind(t)) for s, a, t in bundle["ayahs"]]


def find_ayah(text: str, corpus: list[tuple[int, int, set[str], str]]) -> list[tuple]:
    """يبحث بالمفاتيح المضبوطة، فإن خابت فبالأعمى — ويُعلِم أيُّهما أصاب."""
    needles = quote_keys(text)
    if not needles:
        return []
    hits = [
        (s, a, "مطابق")
        for s, a, keys, _ in corpus
        if any(n in k for n in needles for k in keys)
    ]
    if hits:
        return hits
    loose = alef_blind(text).strip()
    if len(loose) < 12:  # عبارةٌ قصيرة عمياءُ عن الألف تلتقط ما ليس منها
        return []
    hits = [(s, a, "برسم ألفٍ أو همزةٍ مختلف") for s, a, _, blind in corpus if loose in blind]
    if hits:
        return hits
    # آخرُ محاولة: لعلّ الناسخ لصَق كلمتين. تُلتقط لتُصحَّح لا لتُقبل.
    glued = GLUED.sub("", loose)
    if len(glued) < 12:
        return []
    return [
        (s, a, "بفَقْدِ مسافةٍ في النسخ — يجب التصحيح")
        for s, a, _, blind in corpus
        if glued in GLUED.sub("", blind)
    ]


def load_declared() -> dict[str, str]:
    """الاقتباسات المُعلَن أنها ليست قرآنًا، مفهرسةً بكل مفاتيح نصّها."""
    if not DECLARED.exists():
        return {}
    declared: dict[str, str] = {}
    for line in DECLARED.read_text(encoding="utf-8").splitlines():
        if not line.startswith("- «"):
            continue
        body = line[2:]
        match = QUOTE.match(body)
        if not match:
            continue
        reason = body[match.end() :].lstrip(" —·:").strip()
        for key in quote_keys(match.group(1)):
            declared[key] = reason or "بلا سبب معلن"
    return declared


def main() -> int:
    pages = load_pages()
    corpus = load_corpus()
    declared = load_declared()
    quotes = extract_quotes(pages)

    matched, explained, unknown, defective = [], [], [], []
    for quote in quotes:
        needles = quote_keys(quote["text"])
        if not needles:
            continue
        hits = find_ayah(quote["text"], corpus)
        reason = next((declared[n] for n in needles if n in declared), None)
        if hits and "يجب التصحيح" in hits[0][2]:
            defective.append({**quote, "ayahs": hits[:4]})
        elif hits:
            matched.append({**quote, "ayahs": hits[:4]})
        elif reason:
            explained.append({**quote, "reason": reason})
        else:
            unknown.append(quote)

    if "--json" in sys.argv:
        print(
            json.dumps(
                {
                    "matched": matched,
                    "explained": explained,
                    "defective": defective,
                    "unknown": unknown,
                },
                ensure_ascii=False,
            )
        )
        return 1 if unknown or defective else 0

    print(f"صفحات: {len(pages)} · اقتباسات: {len(quotes)}")
    print(f"  طابق المصحف: {len(matched)}")
    print(f"  معلَنٌ أنه ليس قرآنًا: {len(explained)}")
    print(f"  آيةٌ نُسخت بخلل: {len(defective)}")
    print(f"  مجهول: {len(unknown)}")
    for quote in defective:
        refs = "، ".join(f"{s}:{a}" for s, a, _ in quote["ayahs"])
        print(f"  ⚠️ ص{quote['pages'][0]} «{quote['text'][:56]}» → {refs}")
    for quote in matched:
        refs = "، ".join(f"{s}:{a}" for s, a, _ in quote["ayahs"])
        how = quote["ayahs"][0][2]
        note = "" if how == "مطابق" else f" ⟨{how}⟩"
        print(f"  ✅ ص{quote['pages'][0]} «{quote['text'][:56]}» → {refs}{note}")
    for quote in explained:
        print(f"  ◻️ ص{quote['pages'][0]} «{quote['text'][:44]}» — {quote['reason']}")
    for quote in unknown:
        mark = " (مبتور)" if quote["truncated"] else ""
        print(f"  ❌ ص{quote['pages'][0]}{mark} «{quote['text'][:70]}»")
    if unknown:
        print(
            "\nاقتباسٌ مجهول: إمّا أن يكون آيةً نُسخت خطأً — فتُصحَّح على"
            f"\nالمصوَّرة — وإمّا حديثًا أو قراءةً، فيُعلَن في {DECLARED.name}."
        )
    if defective:
        print("\nآيةٌ عُثر عليها بتساهلٍ في المسافات: النسخ خطأ ويُصحَّح على المصوَّرة.")
    if not unknown and not defective:
        print("\nلا اقتباسَ مجهولًا: كلُّ ما بين «…» إمّا طابق المصحف وإمّا مُعلَن.")
    return 1 if unknown or defective else 0


if __name__ == "__main__":
    raise SystemExit(main())
