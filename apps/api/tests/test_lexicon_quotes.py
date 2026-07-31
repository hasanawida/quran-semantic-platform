"""حارسُ الاقتباسات: لا يُنشر متنُ معجمٍ فيه «اقتباس» مجهولُ النسب.

المعجم يستشهد بالآيات، والناسخ — بشرًا كان أو وكيلًا — يقرأ صورةً باهتة
فيُسقط كلمةً أو يُبدل حرفًا. وخطأٌ في لفظٍ عاديٍّ يُصحَّح في مراجعة، أمّا
خطأٌ في آيةٍ **فتحريفٌ يُنشر باسم المصحف**. فالمقابلة هنا حتمية: نصُّ
المنصة المبصوم هو الحَكَم، لا عينُ الناسخ ولا ذاكرةُ النموذج.

وليس كلُّ ما بين «…» آيةً — في المعجم أحاديثُ وقراءاتٌ وأمثال — فالقاعدة
المنفَّذة: كلُّ اقتباسٍ إمّا أن يطابق آيةً، وإمّا أن يكون **معلَنًا**
بسببه في `quotes-not-quran.md`. فلا يمرّ مجهولٌ صامتًا، ولا يُتَّهم حديثٌ
بأنه آية محرَّفة. وإعلانُ ما ليس بقرآنٍ فِعلٌ واعٍ يفعله إنسانٌ أو وكيلٌ
ويوقّع عليه — لا استثناءٌ يبتلعه الحارس.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
CHECKER = REPO / "scripts" / "import-lexicon" / "check_quotes.py"


def _load_checker():
    if not CHECKER.exists():  # pragma: no cover - يكشفه أول تشغيل
        pytest.skip("فاحص الاقتباسات غير موجود")
    sys.path.insert(0, str(REPO / "apps" / "api"))
    spec = importlib.util.spec_from_file_location("check_quotes", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def scan():
    checker = _load_checker()
    if not checker.QURAN.exists():
        pytest.skip("حزمة المصحف غير مبنيّة")
    pages = checker.load_pages()
    if not pages:
        pytest.skip("لا صفحات نسخ")
    corpus = checker.load_corpus()
    declared = checker.load_declared()
    matched, explained, unknown = [], [], []
    for quote in checker.extract_quotes(pages):
        needles = checker.quote_keys(quote["text"])
        if not needles:
            continue
        if checker.find_ayah(quote["text"], corpus):
            matched.append(quote)
        elif any(n in declared for n in needles):
            explained.append(quote)
        else:
            unknown.append(quote)
    return {"matched": matched, "explained": explained, "unknown": unknown}


def test_no_unattributed_quote_is_published(scan):
    """اقتباسٌ لا يطابق المصحف ولا هو معلَنٌ = إمّا آيةٌ محرَّفة وإمّا نسبٌ مجهول."""
    lines = [
        f"ص{q['pages'][0]} ({q['file']}): «{q['text'][:70]}»" for q in scan["unknown"]
    ]
    assert not lines, (
        "اقتباساتٌ مجهولة النسب — صحِّحها على المصوَّرة إن كانت آيات،\n"
        "أو أعلِنها في data/transcriptions/mukhtar-sihah-1920/quotes-not-quran.md:\n  "
        + "\n  ".join(lines)
    )


def test_quran_quotes_actually_match_our_text(scan):
    """طمأنينةٌ عكسية: لو انهار التطبيع لصارت المطابقات صفرًا والحارسُ ساكتًا."""
    if scan["matched"] or scan["explained"]:
        assert scan["matched"], (
            "لا اقتباسَ واحدٌ طابق المصحف مع وجود اقتباسات — "
            "التطبيع أو حزمة المصحف معطوبة، والحارسُ يمرّ كاذبًا"
        )


def test_declared_exceptions_are_reasoned():
    """إعلانٌ بلا سبب بابٌ خلفيّ: يُسكِت الحارس دون أن يقول لماذا."""
    checker = _load_checker()
    if not checker.DECLARED.exists():
        return
    for text, reason in checker.load_declared().items():
        assert reason and reason != "بلا سبب معلن", f"إعلانٌ بلا سبب: {text[:50]}"
