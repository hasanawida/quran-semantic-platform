"""أسماء عربية لوسوم الأقسام الصرفية في المدونة القرآنية (45 وسمًا).

الوسوم نفسها من المصدر ولا تُعدَّل؛ هذه طبقة عرض عربية فقط. أي وسم غير
معروف يُعرض كما هو من المصدر بدل إخفائه.
"""

from __future__ import annotations

import re

POS_LABELS_AR: dict[str, str] = {
    # أسماء وأفعال
    "N": "اسم",
    "PN": "اسم علم",
    "ADJ": "صفة",
    "IMPN": "اسم فعل أمر",
    "V": "فعل",
    "PRON": "ضمير",
    "DEM": "اسم إشارة",
    "REL": "اسم موصول",
    "T": "ظرف زمان",
    "LOC": "ظرف مكان",
    # أدوات وحروف
    "P": "حرف جر",
    "DET": "أداة تعريف",
    "CONJ": "حرف عطف",
    "SUB": "حرف مصدري",
    "ACC": "حرف نصب",
    "AMD": "حرف استفتاح",
    "ANS": "حرف جواب",
    "AVR": "حرف ردع",
    "CAUS": "حرف سببية",
    "CERT": "حرف تحقيق",
    "CIRC": "واو الحال",
    "COM": "واو المعية",
    "COND": "أداة شرط",
    "EMPH": "لام التوكيد",
    "EQ": "أداة تسوية",
    "EXH": "حرف تحضيض",
    "EXL": "حرف تفسير",
    "EXP": "أداة استثناء",
    "FUT": "حرف استقبال",
    "INC": "حرف ابتداء",
    "INL": "حروف مقطعة",
    "INT": "حرف تفسير (أنْ)",
    "INTG": "أداة استفهام",
    "NEG": "حرف نفي",
    "PREV": "حرف كافّ",
    "PRO": "لا الناهية",
    "PRP": "لام التعليل",
    "REM": "حرف استئناف",
    "RES": "أداة حصر",
    "RET": "حرف إضراب",
    "RSLT": "حرف جواب الشرط",
    "SUP": "حرف زائد",
    "SUR": "إذا الفجائية",
    "VOC": "حرف نداء",
}


def pos_label(tag: str) -> str:
    return POS_LABELS_AR.get(tag, tag)


# =============================================================================
# تفكيك سمات المصدر إلى أبعاد قابلة للبحث
#
# عمود `features` يُحفظ **حرفيًا كما ورد** (شرط رخصة المدونة: لا تعديل).
# ما هنا فهرسة له لا تعديل فيه: تُقرأ الرموز وتوزَّع على أبعاد معروفة،
# ويبقى الأصل مرجعًا لكل ما لم يُفهرس.
# =============================================================================

ASPECTS = {"PERF": "ماضٍ", "IMPF": "مضارع", "IMPV": "أمر"}
VOICES = {"ACT": "معلوم", "PASS": "مجهول"}
MOODS = {"SUBJ": "منصوب", "JUS": "مجزوم"}
CASES = {"NOM": "مرفوع", "ACC": "منصوب", "GEN": "مجرور"}
NOMINAL_FORMS = {"PCPL": "اسم مشتق (فاعل/مفعول)", "VN": "مصدر"}
PERSONS = {"1": "متكلم", "2": "مخاطب", "3": "غائب"}
GENDERS = {"M": "مذكر", "F": "مؤنث"}
NUMBERS = {"S": "مفرد", "D": "مثنى", "P": "جمع"}

# أوزان الفعل المزيد كما ترمز لها المدونة: (II) … (XII)
VERB_FORMS = {
    "I": "مجرد",
    "II": "فعَّل",
    "III": "فاعَل",
    "IV": "أفعَل",
    "V": "تفعَّل",
    "VI": "تفاعَل",
    "VII": "انفعَل",
    "VIII": "افتعَل",
    "IX": "افعَلَّ",
    "X": "استفعَل",
    "XI": "افعالَّ",
    "XII": "افعوعَل",
}

# 3MS ‏/ 2MP ‏/ 1P ‏/ MD ‏/ FS ‏/ P … — الشخص ثم الجنس ثم العدد، وكلها اختيارية
_PGN = re.compile(r"^([123])?([MF])?([SDP])?$")
_VERB_FORM = re.compile(r"^\((I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)\)$")


def parse_features(features: str) -> dict[str, str | None]:
    """يفكك سلسلة سمات المصدر إلى أبعاد مسمّاة.

    ما لا يُعرف يُترك — لا يُخمَّن ولا يُسقط من العمود الأصلي."""
    parsed: dict[str, str | None] = {
        "aspect": None,
        "verb_form": None,
        "voice": None,
        "mood": None,
        "person": None,
        "gender": None,
        "grammatical_number": None,
        "case_marking": None,
        "definiteness": None,
        "nominal_form": None,
    }
    for token in features.split("|"):
        if not token or token.endswith("+") or ":" in token and not token.startswith("MOOD:"):
            continue
        if token in ASPECTS:
            parsed["aspect"] = token
        elif token in VOICES:
            parsed["voice"] = token
        elif token in CASES:
            parsed["case_marking"] = token
        elif token in NOMINAL_FORMS:
            parsed["nominal_form"] = token
        elif token == "INDEF":
            # المصدر يوسم النكرة صراحةً ولا يوسم المعرفة، فلا يُفترض عكسها
            parsed["definiteness"] = "INDEF"
        elif token.startswith("MOOD:"):
            value = token[5:]
            if value in MOODS:
                parsed["mood"] = value
        else:
            form = _VERB_FORM.match(token)
            if form:
                parsed["verb_form"] = form.group(1)
                continue
            pgn = _PGN.match(token)
            if pgn and any(pgn.groups()):
                person, gender, number = pgn.groups()
                if person:
                    parsed["person"] = person
                if gender:
                    parsed["gender"] = gender
                if number:
                    parsed["grammatical_number"] = number
    return parsed


# تسميات عربية موحّدة لكل بُعد — تُستعمل في الواجهة وفي التصدير
FEATURE_LABELS: dict[str, dict[str, str]] = {
    "aspect": ASPECTS,
    "verb_form": VERB_FORMS,
    "voice": VOICES,
    "mood": MOODS,
    "person": PERSONS,
    "gender": GENDERS,
    "grammatical_number": NUMBERS,
    "case_marking": CASES,
    "definiteness": {"INDEF": "نكرة"},
    "nominal_form": NOMINAL_FORMS,
}

FEATURE_TITLES = {
    "pos": "القسم",
    "aspect": "الزمن",
    "verb_form": "وزن الفعل",
    "voice": "البناء",
    "mood": "الإعراب (الفعل)",
    "person": "الشخص",
    "gender": "الجنس",
    "grammatical_number": "العدد",
    "case_marking": "الإعراب (الاسم)",
    "definiteness": "التعريف",
    "nominal_form": "الاشتقاق",
}


def feature_label(dimension: str, value: str | None) -> str | None:
    if value is None:
        return None
    return FEATURE_LABELS.get(dimension, {}).get(value, value)
