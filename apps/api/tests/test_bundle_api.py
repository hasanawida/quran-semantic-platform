"""اختبارات ذهبية على المسارات المدعومة بقاعدة البيانات (بيانات مبذورة في conftest)."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionFactory
from app.main import app
from app.services.morphology import MorphologyService

# سور تُرمَّز هنا حتى لا يعتمد اختبار المواضع على ترتيب وحدات الاختبار
TOKENIZED = {1, 2, 55, 112}


def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def tokenized_scope():
    """يضمن وجود كلمات مرقَّمة للسور المفحوصة (عملية idempotent)."""

    async def _run():
        async with SessionFactory() as session:
            await MorphologyService(session).tokenize_version(surahs=TOKENIZED)

    asyncio.run(_run())
    yield


def test_surahs_complete():
    body = client().get("/api/v1/surahs").json()
    assert body["success"] is True
    surahs = body["data"]
    assert len(surahs) == 114
    by_number = {s["number"]: s for s in surahs}
    assert by_number[1]["ayah_count"] == 7
    assert by_number[2]["ayah_count"] == 286
    assert by_number[12]["ayah_count"] == 111


def test_root_asr_golden_occurrences():
    # جذر ع ص ر: خمسة مواضع معلومة، منها العصر 103:1
    body = client().get("/api/v1/roots/ع ص ر/occurrences?limit=50").json()
    root = body["data"]["root"]
    occurrences = body["data"]["occurrences"]
    assert root["occurrence_count"] == 5
    refs = {(o["surah_number"], o["ayah_number"]) for o in occurrences}
    assert refs == {(2, 266), (12, 36), (12, 49), (78, 14), (103, 1)}
    # الحالة العلمية ظاهرة: مستورد لا معتمد
    assert root["status"] == "imported"


def test_hamzated_root_forms_resolve_to_same_root():
    counts = set()
    for form in ["سأل", "سءل", "سؤل"]:
        body = client().get(f"/api/v1/roots/{form}").json()
        counts.add(body["data"]["occurrence_count"])
        assert body["data"]["normalized_root"] == "سال"
    assert counts == {129}


def test_ayah_endpoint_returns_uthmani_text():
    body = client().get("/api/v1/ayahs/103/1").json()
    data = body["data"]
    assert data["surah_number"] == 103
    assert data["ayah_number"] == 1
    assert len(data["uthmani_text"]) > 0
    assert data["review_status"] == "imported"


def test_occurrences_pagination():
    first = client().get("/api/v1/roots/امن/occurrences?limit=5").json()["data"]
    assert len(first["occurrences"]) == 5
    assert first["pagination"]["total_ayahs"] > 5
    second = client().get(
        "/api/v1/roots/امن/occurrences?limit=5&offset=5"
    ).json()["data"]
    refs1 = {(o["surah_number"], o["ayah_number"]) for o in first["occurrences"]}
    refs2 = {(o["surah_number"], o["ayah_number"]) for o in second["occurrences"]}
    assert not refs1 & refs2


def test_highlight_indexes_present_for_safe_ayahs():
    body = client().get("/api/v1/roots/ع ص ر/occurrences?limit=50").json()["data"]
    by_ref = {
        (o["surah_number"], o["ayah_number"]): o["word_indexes"]
        for o in body["occurrences"]
    }
    # البقرة 266 موضع آمن للتمييز (كلمة إعصار)
    assert by_ref[(2, 266)] == [25]


def test_unknown_root_404():
    response = client().get("/api/v1/roots/زخذف")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ROOT_NOT_FOUND"


def test_meta_reports_active_version():
    body = client().get("/api/v1/meta").json()["data"]
    assert body["review_status"] == "imported"
    assert body["counts"]["ayahs"] == 6236


# ---- تصفح المصحف (سورة كاملة) ------------------------------------------
def test_surah_page_separates_the_basmala_from_the_first_ayah():
    body = client().get("/api/v1/surahs/2/ayahs?limit=3").json()
    assert body["success"] is True
    data = body["data"]
    assert data["surah"]["arabic_name"]
    assert data["surah"]["ayah_count"] == 286
    # البسملة بيان للسورة، والآية الأولى حروف مقطعة وحدها
    assert data["surah"]["basmala_text"] and "بِسْمِ" in data["surah"]["basmala_text"]
    first = data["ayahs"][0]
    assert first["ayah_number"] == 1
    assert "بِسْمِ" not in first["uthmani_text"]

    # الفاتحة: البسملة آية مستقلة فلا تتكرر بيانًا للسورة
    fatiha = client().get("/api/v1/surahs/1/ayahs").json()["data"]
    assert fatiha["surah"]["basmala_text"] is None
    assert "بِسْمِ" in fatiha["ayahs"][0]["uthmani_text"]

    # براءة: لا بسملة لها
    tawbah = client().get("/api/v1/surahs/9/ayahs?limit=1").json()["data"]
    assert tawbah["surah"]["basmala_text"] is None


def test_surah_page_word_offsets_reproduce_the_text_exactly():
    """عقد صفحة المصحف: النص يُقطَّع بالمواضع ولا يُعاد تركيبه.

    إعادة التركيب من الكلمات تُسقط علامات الوقف ورموز نهاية الآية —
    خرق للبند 2 من سياسة السلامة العلمية."""
    for surah in sorted(TOKENIZED):
        data = client().get(f"/api/v1/surahs/{surah}/ayahs?limit=300").json()["data"]
        assert data["ayahs"]
        # الكلمات موجودة فعلًا، وإلا مرّ الاختبار بلا أن يفحص شيئًا
        assert any(ayah["words"] for ayah in data["ayahs"])
        for ayah in data["ayahs"]:
            text = ayah["uthmani_text"]
            rebuilt = []
            cursor = 0
            for word in sorted(ayah["words"], key=lambda w: w["char_start"]):
                assert word["char_start"] >= cursor
                rebuilt.append(text[cursor : word["char_start"]])
                rebuilt.append(text[word["char_start"] : word["char_end"]])
                cursor = word["char_end"]
            rebuilt.append(text[cursor:])
            assert "".join(rebuilt) == text, f"{surah}:{ayah['ayah_number']}"


def test_surah_page_pagination_and_unknown_surah():
    page = client().get("/api/v1/surahs/2/ayahs?offset=10&limit=5").json()["data"]
    assert [a["ayah_number"] for a in page["ayahs"]] == [11, 12, 13, 14, 15]
    assert page["pagination"]["total"] == 286
    assert client().get("/api/v1/surahs/115/ayahs").status_code == 422


# ---- مقارنة الجذور ------------------------------------------------------
def test_root_comparison_reports_distribution_and_shared_ayahs():
    body = client().get("/api/v1/roots/compare?roots=سأل,قول&limit=5").json()
    assert body["success"] is True
    data = body["data"]
    assert len(data["roots"]) == 2
    for root in data["roots"]:
        assert root["occurrence_count"] > 0
        assert root["surah_count"] > 0
        # نوع النزول بيان وصفي من بيانات السور
        assert (
            root["by_revelation"]["meccan"] + root["by_revelation"]["medinan"]
            == root["occurrence_count"]
        )
        # مجموع توزيع السور = عدد المواضع
        assert sum(s["count"] for s in root["by_surah"]) == root["occurrence_count"]

    # الآيات المشتركة تحوي فعلًا الجذرين معًا
    assert data["shared"]["ayah_count"] > 0
    for item in data["shared"]["ayahs"]:
        assert set(item["word_indexes_by_root"]) == {
            root["display_root"] for root in data["roots"]
        }
    assert data["shared"]["shown"] <= 5
    # لا حكم دلالي في المخرَج
    assert "لا يعني الترادف" in data["notice"]
    assert "similarity" not in str(data)


def test_root_comparison_with_itself_is_total_overlap():
    """اختبار سلامة: جذر مع صورة أخرى منه يعطي مفتاحًا واحدًا فيُرفض."""
    same = client().get("/api/v1/roots/compare?roots=سأل,سءل")
    assert same.status_code == 422
    assert same.json()["error"]["code"] == "TOO_FEW_ROOTS"


def test_root_comparison_input_guards():
    assert client().get("/api/v1/roots/compare?roots=سأل").status_code == 422
    unknown = client().get("/api/v1/roots/compare?roots=سأل,زخذف")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "ROOT_NOT_FOUND"
    too_many = client().get(
        "/api/v1/roots/compare?roots=سأل,قول,علم,كتب,امن,حمد"
    )
    assert too_many.status_code == 422
    assert too_many.json()["error"]["code"] == "TOO_MANY_ROOTS"


# ---- بيان المنهج والمصادر والخلاف --------------------------------------
def test_methodology_is_public_and_documents_every_adopted_source():
    body = client().get("/api/v1/methodology").json()
    assert body["success"] is True
    data = body["data"]

    # كل مصدر معتمد: رابط ورخصة وسبب اختيار وحدود معلومة وما فعلته المنصة
    assert len(data["adopted_sources"]) >= 2
    for source in data["adopted_sources"]:
        assert source["url"].startswith("http")
        assert source["license"]
        assert source["why_chosen"]
        assert source["known_limits"], f"{source['key']}: بلا حدود معلومة"
        assert source["what_we_did"]

    roles = {source["role"] for source in data["adopted_sources"]}
    assert "نص المصحف" in roles
    assert any("صرف" in role for role in roles)


def test_methodology_states_disagreements_with_a_position_for_each():
    data = client().get("/api/v1/methodology").json()["data"]
    keys = {item["key"] for item in data["disagreements"]}
    # مواضع الخلاف التي تمسّ عمل المنصة مباشرة
    assert {
        "ayah_counting",
        "basmala",
        "script",
        "word_boundaries",
        "root_assignment",
        "hamza_in_root",
    } <= keys
    for item in data["disagreements"]:
        assert item["summary"]
        # لا يُذكر خلاف بلا بيان موقف المنصة منه
        assert item["platform_position"], f"{item['key']}: بلا موقف معلن"


def test_methodology_declares_the_single_source_limitation_honestly():
    """أخطر ما يجب ألا يُخفى: كل موضع جذر اليوم شهادة مصدر واحد."""
    data = client().get("/api/v1/methodology").json()["data"]
    qac = next(s for s in data["adopted_sources"] if s["key"] == "qac")
    assert "مصدر واحد" in qac["what_we_did"]
    # ودقة المصدر المعلنة مذكورة لا مسكوت عنها
    assert any("99" in limit for limit in qac["known_limits"])

    warning = data["machine_analyzer_warning"]
    assert warning["reference"].startswith("Journal") or "http" in warning["reference"]
    assert "machine_only" in warning["consequence"]


def test_every_candidate_source_carries_a_license_verification_state():
    """لا يُذكر مرشح بلا تصريح: أوُجد نص رخصته أم لا أم لم يكتمل الفحص؟

    الغرض منع ما وقع فعلًا قبل التحقق: نُسبت إلى «الخليل» رخصة Apache 2.0
    نقلًا عن قائمة طرف ثالث، وموقعها الرسمي يقول غير ذلك."""
    data = client().get("/api/v1/methodology").json()["data"]
    candidates = data["candidate_second_sources"]
    assert candidates, "قائمة المرشحين لا تكون فارغة"
    for candidate in candidates:
        assert candidate["license_status"] in {
            "verified",
            "unverified",
            "incomplete",
        }, candidate["name"]
        assert candidate["license_note"].strip(), candidate["name"]
        assert candidate["verdict"].strip(), candidate["name"]

    # ولا يُقبل مرشح قبولًا مطلقًا: كل حكم فيه شرط أو تأجيل أو رفض
    assert not any(c["verdict"].strip() == "يُعتمد" for c in candidates)


def test_methodology_states_plainly_that_no_second_root_witness_exists():
    """الشرط غير مستوفى، فيُعلَن. تلطيفه في الواجهة إيهام باتفاق لا وجود له."""
    data = client().get("/api/v1/methodology").json()["data"]
    verdict = data["second_witness_verdict"]
    assert verdict["answer"].startswith("لا")
    assert "مصدر واحد" in verdict["consequence"]
    # وسبب عدم خفض الشرط مذكور، لا مسكوت عنه
    assert "الآلة" in verdict["why_not_lowered"]
    assert verdict["path_forward"], "الطريق إلى الأمام مذكور لا مبهم"


def test_methodology_red_lines_and_pipeline_are_served():
    data = client().get("/api/v1/methodology").json()["data"]
    method = data["method"]
    assert len(method["layers"]) == 4
    assert len(method["pipeline"]) >= 5
    assert len(method["red_lines"]) >= 4
    joined = " ".join(method["red_lines"])
    assert "لا يُولَّد نص قرآني" in joined
    assert "الخلاف العلمي يُعرض ولا يُخفى" in joined
    # ليست فتوى ولا تفسيرًا
    assert "فتوى" in data["notice"]
