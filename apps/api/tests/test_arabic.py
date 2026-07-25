from app.utils.arabic import normalize_arabic_search, normalize_root_input


def test_normalize_arabic_search():
    assert normalize_arabic_search("إِنَّ") == "ان"


def test_normalize_root_input():
    assert normalize_root_input("ع-ص-ر") == "عصر"
    assert normalize_root_input("ع ص ر") == "عصر"


def test_strips_dagger_alef_and_wasla():
    # سلاسل صناعية بنقاط ترميز محددة، ليست نصًا قرآنيًا
    assert normalize_arabic_search("رحٰم") == "رحم"
    assert normalize_arabic_search("ٱلرس") == "الرس"


def test_strips_quranic_stop_marks():
    # علامة نهاية آية U+06DD وعلامة وقف U+06DA ملحقة بحرف الباء
    assert normalize_arabic_search("ب۝ۚ") == "ب"


def test_strips_extended_a_marks():
    # علامات Arabic Extended-A المركبة (U+08F0 فتحتان مفتوحتان) بعد حرف الباء
    assert normalize_arabic_search("بࣰࣱࣲ") == "ب"


def test_tatweel_removed():
    assert normalize_arabic_search("عـــصـــر") == "عصر"


def test_combining_hamza_is_letter_not_diacritic():
    # الرسم العثماني يكتب الهمزة المتوسطة همزة تركيبية على تطويل:
    # شيـٔا (ش+ي+ـ+ٔ+ا) يجب أن يطابق الإملاء الحديث شيئا بعد التطبيع
    uthmani_like = "شَيْـًٔا"
    assert normalize_arabic_search(uthmani_like) == normalize_arabic_search("شيئا")


def test_waw_dagger_alef_matches_modern_orthography():
    # الصلوٰة (رسم عثماني) تكافئ الصلاة (إملاء حديث)
    assert normalize_arabic_search("الصلوٰة") == normalize_arabic_search("الصلاة")


def test_hamzated_root_single_canonical_key():
    # كل صور كتابة الجذر المهموز تنتج مفتاحًا واحدًا (اصطلاح المدونة: الهمزة → ا)
    assert (
        normalize_root_input("سأل")
        == normalize_root_input("سءل")
        == normalize_root_input("سؤل")
        == "سال"
    )
    assert normalize_root_input("قرأ") == normalize_root_input("قرئ") == "قرا"


def test_hamzated_root_does_not_collide_with_weak_roots():
    # الجذر المهموز لا يتصادم مع جذور الواو والياء (الألف الخالصة ليست أصلًا)
    assert normalize_root_input("سول") == "سول"
    assert normalize_root_input("سيل") == "سيل"
    assert normalize_root_input("قري") == "قري"
    assert normalize_root_input("سؤل") != normalize_root_input("سول")
    assert normalize_root_input("قرئ") != normalize_root_input("قري")


def test_empty_after_normalization():
    assert normalize_root_input("123 - !") == ""


def test_display_text_untouched_principle():
    # الدالة مخصصة للبحث فقط؛ هذا الاختبار يوثق أنها تغيّر النص فعلاً
    # ولذلك يحرم تمريرها على نص العرض
    assert normalize_arabic_search("أ") != "أ"
