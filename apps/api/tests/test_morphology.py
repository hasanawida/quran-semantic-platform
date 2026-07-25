"""اختبارات المرحلة D — الصرف متعدد المصادر.

النطاق محصور بسور قليلة ليبقى زمن الاختبار قصيرًا، والبيانات المبذورة
تغطي المصحف كاملًا فتبقى الفحوص المرجعية شاملة.
"""

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.security import hash_password
from app.db.session import SessionFactory
from app.main import app
from app.models.enums import RecordStatus, UserRole
from app.models.language import Root, RootDerivation, RootOccurrence
from app.models.morphology import (
    MorphologicalAnalysis,
    MorphologySource,
    Token,
    TokenRootDecision,
)
from app.models.quran import Ayah, Surah
from app.models.user import User, UserRoleAssignment
from app.services.morphology import (
    MorphologyError,
    MorphologyService,
    load_morphology_bundle,
)
from app.utils.arabic import tokenize_ayah

SCOPE = {1, 2, 20, 112, 113, 114}


def client() -> TestClient:
    return TestClient(app)


def _run(coro_factory):
    async def _wrapper():
        async with SessionFactory() as session:
            return await coro_factory(session)

    return asyncio.run(_wrapper())


@pytest.fixture(scope="module", autouse=True)
def pipeline():
    """يشغّل خط المرحلة D على نطاق محدود مرة واحدة للوحدة."""
    bundle = load_morphology_bundle()
    _run(lambda s: MorphologyService(s).tokenize_version(surahs=SCOPE))
    _run(lambda s: MorphologyService(s).import_bundle(bundle, surahs=SCOPE))
    _run(lambda s: MorphologyService(s).rebuild_occurrences(surahs=SCOPE))
    _run(lambda s: MorphologyService(s).seed_golden_cases())
    yield


def _make_user(*roles: UserRole, password: str = "morphpass1") -> str:
    email = f"m{uuid.uuid4().hex[:8]}@example.com"

    async def _create():
        async with SessionFactory() as session:
            user = User(
                email=email,
                display_name="مراجع",
                password_hash=hash_password(password),
                is_active=True,
            )
            for role in roles:
                user.roles.append(UserRoleAssignment(role=role))
            session.add(user)
            await session.commit()

    asyncio.run(_create())
    return client().post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---- الترميز ------------------------------------------------------------
def test_tokens_slice_back_to_the_ayah_text_exactly():
    """كل كلمة تقطع من نص الآية بمواضعها فتعيد النص نفسه — لا إعادة تركيب."""

    async def _check(session):
        ayahs = (
            await session.execute(
                select(Ayah.id, Ayah.uthmani_text).where(Ayah.surah_number == 112)
            )
        ).all()
        checked = 0
        for ayah_id, text in ayahs:
            tokens = (
                await session.execute(
                    select(Token).where(Token.ayah_id == ayah_id).order_by(Token.word_number)
                )
            ).scalars().all()
            assert [t.word_number for t in tokens] == list(range(1, len(tokens) + 1))
            for token in tokens:
                assert text[token.char_start : token.char_end] == token.surface_text
                checked += 1
        return checked

    assert _run(_check) > 0


def test_tokenizer_skips_standalone_waqf_marks():
    text = "وَلَا تُسْـَٔلُ ۖ عَنْ أَصْحَـٰبِ"
    words = [w for _s, _e, w in tokenize_ayah(text)]
    assert words == ["وَلَا", "تُسْـَٔلُ", "عَنْ", "أَصْحَـٰبِ"]


# ---- فصل البسملة --------------------------------------------------------
def test_basmala_is_separated_from_first_ayah():
    async def _check(session):
        first_of_baqarah = await session.scalar(
            select(Ayah.uthmani_text).where(
                Ayah.surah_number == 2, Ayah.ayah_number == 1
            )
        )
        fatiha_first = await session.scalar(
            select(Ayah.uthmani_text).where(
                Ayah.surah_number == 1, Ayah.ayah_number == 1
            )
        )
        ikhlas_first = await session.scalar(
            select(Ayah.uthmani_text).where(
                Ayah.surah_number == 112, Ayah.ayah_number == 1
            )
        )
        surahs = {
            number: basmala
            for number, basmala in (
                await session.execute(select(Surah.number, Surah.basmala_text))
            ).all()
        }
        return first_of_baqarah, fatiha_first, ikhlas_first, surahs

    baqarah, fatiha, ikhlas, surahs = _run(_check)
    # الآية الأولى من البقرة حروف مقطعة وحدها
    assert len(tokenize_ayah(baqarah)) == 1
    assert "بِسْمِ" not in baqarah
    # البسملة في الفاتحة آية مستقلة فتبقى نصًا للآية
    assert "بِسْمِ" in fatiha
    assert ikhlas.startswith("قُلْ")
    # لا بسملة لبراءة، والفاتحة بسملتها آية لا بيان سورة
    assert surahs[9] is None
    assert surahs[1] is None
    assert surahs[2] is not None and "بِسْمِ" in surahs[2]
    assert sum(1 for v in surahs.values() if v) == 112


# ---- الاستيراد والاشتقاق ------------------------------------------------
def test_import_links_tokens_only_where_alignment_holds():
    async def _check(session):
        source = await session.scalar(
            select(MorphologySource).where(MorphologySource.code == "qac-0.4")
        )
        assert source is not None
        assert source.file_sha256 and len(source.file_sha256) == 64
        assert source.status == RecordStatus.IMPORTED

        # 2:181 آية غير محاذية (المدونة تعد «بَعْدَ مَا» كلمة واحدة)
        misaligned_id = await session.scalar(
            select(Ayah.id).where(Ayah.surah_number == 2, Ayah.ayah_number == 181)
        )
        unlinked = await session.scalar(
            select(func.count(MorphologicalAnalysis.id)).where(
                MorphologicalAnalysis.ayah_id == misaligned_id,
                MorphologicalAnalysis.token_id.is_(None),
            )
        )
        total = await session.scalar(
            select(func.count(MorphologicalAnalysis.id)).where(
                MorphologicalAnalysis.ayah_id == misaligned_id
            )
        )
        # 112:1 آية محاذية
        aligned_id = await session.scalar(
            select(Ayah.id).where(Ayah.surah_number == 112, Ayah.ayah_number == 1)
        )
        aligned_unlinked = await session.scalar(
            select(func.count(MorphologicalAnalysis.id)).where(
                MorphologicalAnalysis.ayah_id == aligned_id,
                MorphologicalAnalysis.token_id.is_(None),
            )
        )
        return unlinked, total, aligned_unlinked

    unlinked, total, aligned_unlinked = _run(_check)
    assert total > 0
    assert unlinked == total  # لا يُربط شيء في آية غير محاذية
    assert aligned_unlinked == 0


def test_misaligned_ayah_occurrences_are_never_highlight_safe():
    async def _check(session):
        ayah_id = await session.scalar(
            select(Ayah.id).where(Ayah.surah_number == 2, Ayah.ayah_number == 181)
        )
        return (
            await session.execute(
                select(RootOccurrence.word_number, RootOccurrence.is_highlight_safe)
                .where(RootOccurrence.ayah_id == ayah_id)
            )
        ).all()

    rows = _run(_check)
    assert rows, "يجب أن تبقى المواضع محفوظة رغم تعذر المحاذاة"
    assert all(safe is False for _w, safe in rows)


def test_derivation_is_recorded_as_single_source():
    async def _check(session):
        ayah_id = await session.scalar(
            select(Ayah.id).where(Ayah.surah_number == 112, Ayah.ayah_number == 1)
        )
        return (
            await session.execute(
                select(RootOccurrence.derivation, RootOccurrence.is_highlight_safe)
                .where(RootOccurrence.ayah_id == ayah_id)
            )
        ).all()

    rows = _run(_check)
    assert rows
    assert all(d == RootDerivation.SINGLE_SOURCE for d, _ in rows)
    assert all(safe for _d, safe in rows)


def test_word_with_two_distinct_roots_keeps_both():
    """يٰبْنَؤُمَّ (20:94) الكلمة الوحيدة بجذرين — لا يُفرض جذر واحد للكلمة."""

    async def _check(session):
        ayah_id = await session.scalar(
            select(Ayah.id).where(Ayah.surah_number == 20, Ayah.ayah_number == 94)
        )
        return set(
            (
                await session.execute(
                    select(Root.normalized_root)
                    .join(RootOccurrence, RootOccurrence.root_id == Root.id)
                    .where(
                        RootOccurrence.ayah_id == ayah_id,
                        RootOccurrence.word_number == 2,
                    )
                )
            ).scalars()
        )

    assert _run(_check) == {"بني", "امم"}


def test_rebuild_never_wipes_ayahs_that_have_no_analyses():
    """إعادة اشتقاق نطاق لم يُستورد تحليله يجب ألا تمحو مواضعه المبذورة."""

    async def _count(session):
        return await session.scalar(
            select(func.count(RootOccurrence.id))
            .join(Ayah, Ayah.id == RootOccurrence.ayah_id)
            .where(Ayah.surah_number == 55)
        )

    before = _run(_count)
    assert before > 0
    result = _run(lambda s: MorphologyService(s).rebuild_occurrences(surahs={55}))
    assert result["ayahs_rebuilt"] == 0
    assert result["ayahs_untouched"] > 0
    assert _run(_count) == before


def test_rebuild_is_deterministic():
    async def _positions(session):
        return set(
            (
                await session.execute(
                    select(
                        RootOccurrence.root_id,
                        RootOccurrence.ayah_id,
                        RootOccurrence.word_number,
                    )
                    .join(Ayah, Ayah.id == RootOccurrence.ayah_id)
                    .where(Ayah.surah_number == 112)
                )
            ).all()
        )

    before = _run(_positions)
    _run(lambda s: MorphologyService(s).rebuild_occurrences(surahs={112}))
    assert _run(_positions) == before


# ---- التعارض بين المصادر والقرارات --------------------------------------
def _fixture_conflict() -> tuple[uuid.UUID, uuid.UUID]:
    """يضيف مصدرًا اختباريًا يخالف المدونة في جذر كلمة واحدة (113:1:1)."""

    async def _create(session):
        ayah_id = await session.scalar(
            select(Ayah.id).where(Ayah.surah_number == 113, Ayah.ayah_number == 1)
        )
        other_root = await session.scalar(
            select(Root.id).where(Root.normalized_root == "كون")
        )
        source = MorphologySource(
            code="test-fixture",
            name="مصدر اختباري (لا يُبذر في الإنتاج)",
            license_note="اختبار فقط",
        )
        session.add(source)
        await session.flush()
        session.add(
            MorphologicalAnalysis(
                source_id=source.id,
                ayah_id=ayah_id,
                word_number=1,
                segment_number=1,
                form_source="test",
                tag="V",
                features="STEM|POS:V",
                pos="V",
                is_stem=True,
                root_id=other_root,
            )
        )
        await session.commit()
        return source.id, ayah_id

    return _run(_create)


def _drop_fixture(source_id: uuid.UUID) -> None:
    async def _cleanup(session):
        await session.execute(
            delete(MorphologicalAnalysis).where(
                MorphologicalAnalysis.source_id == source_id
            )
        )
        await session.execute(
            delete(MorphologySource).where(MorphologySource.id == source_id)
        )
        await session.execute(
            delete(TokenRootDecision).where(
                TokenRootDecision.ayah_id.in_(
                    select(Ayah.id).where(Ayah.surah_number == 113)
                )
            )
        )
        await session.commit()

    _run(_cleanup)
    _run(lambda s: MorphologyService(s).rebuild_occurrences(surahs={113}))


def test_conflict_blocks_derivation_until_a_decision_is_approved():
    source_id, ayah_id = _fixture_conflict()
    try:
        # التعارض يظهر ولا يُحسم آليًا
        conflicts = _run(lambda s: MorphologyService(s).list_conflicts(limit=50))
        positions = {
            (c["surah_number"], c["ayah_number"], c["word_number"])
            for c in conflicts["items"]
        }
        assert (113, 1, 1) in positions
        assert all(c["resolved"] is False for c in conflicts["items"])

        result = _run(lambda s: MorphologyService(s).rebuild_occurrences(surahs={113}))
        assert result["unresolved_conflicts"] >= 1

        async def _roots_at_word(session):
            return set(
                (
                    await session.execute(
                        select(Root.normalized_root)
                        .join(RootOccurrence, RootOccurrence.root_id == Root.id)
                        .where(
                            RootOccurrence.ayah_id == ayah_id,
                            RootOccurrence.word_number == 1,
                        )
                    )
                ).scalars()
            )

        assert _run(_roots_at_word) == set(), "الكلمة المتنازع عليها لا تُنسب لجذر"

        # قرار بشري باعتماد مراجع ثانٍ يحسم التعارض
        proposer = _make_user(UserRole.LINGUISTIC_REVIEWER)
        approver = _make_user(UserRole.QUALITY_MANAGER)
        c = client()
        proposed = c.post(
            "/api/v1/admin/morphology/decisions",
            json={
                "surah": 113,
                "ayah": 1,
                "word_number": 1,
                "roots": ["قول"],
                "rationale": "الكلمة «قل» فعل أمر من القول، والمصدر الاختباري واهم.",
            },
            headers=_auth(proposer),
        )
        assert proposed.status_code == 200, proposed.text
        decision_id = proposed.json()["data"]["id"]
        assert proposed.json()["data"]["status"] == "under_review"

        # لا يعتمد المقترِح قراره
        self_approve = c.post(
            f"/api/v1/admin/morphology/decisions/{decision_id}/approve",
            headers=_auth(proposer),
        )
        assert self_approve.status_code == 409
        assert self_approve.json()["error"]["code"] == "SELF_REVIEW_FORBIDDEN"

        approved = c.post(
            f"/api/v1/admin/morphology/decisions/{decision_id}/approve",
            json={"note": "موافق"},
            headers=_auth(approver),
        )
        assert approved.status_code == 200
        assert approved.json()["data"]["status"] == "approved"

        rebuilt = _run(lambda s: MorphologyService(s).rebuild_occurrences(surahs={113}))
        assert rebuilt["human_decision"] >= 1
        assert _run(_roots_at_word) == {"قول"}

        async def _derivation(session):
            return await session.scalar(
                select(RootOccurrence.derivation).where(
                    RootOccurrence.ayah_id == ayah_id, RootOccurrence.word_number == 1
                )
            )

        assert _run(_derivation) == RootDerivation.HUMAN_DECISION
    finally:
        _drop_fixture(source_id)


def test_disabled_source_is_excluded_from_derivation():
    source_id, ayah_id = _fixture_conflict()
    try:
        async def _disable(session):
            source = await session.get(MorphologySource, source_id)
            source.is_enabled = False
            await session.commit()

        _run(_disable)
        result = _run(lambda s: MorphologyService(s).rebuild_occurrences(surahs={113}))
        assert result["unresolved_conflicts"] == 0

        async def _roots_at_word(session):
            return set(
                (
                    await session.execute(
                        select(Root.normalized_root)
                        .join(RootOccurrence, RootOccurrence.root_id == Root.id)
                        .where(
                            RootOccurrence.ayah_id == ayah_id,
                            RootOccurrence.word_number == 1,
                        )
                    )
                ).scalars()
            )

        assert _run(_roots_at_word) == {"قول"}
    finally:
        _drop_fixture(source_id)


def test_decision_requires_a_rationale_and_a_known_root():
    token = _make_user(UserRole.LINGUISTIC_REVIEWER)
    c = client()
    short_rationale = c.post(
        "/api/v1/admin/morphology/decisions",
        json={"surah": 113, "ayah": 1, "word_number": 1, "roots": ["قول"], "rationale": "قصير"},
        headers=_auth(token),
    )
    assert short_rationale.status_code == 422

    unknown_root = c.post(
        "/api/v1/admin/morphology/decisions",
        json={
            "surah": 113,
            "ayah": 1,
            "word_number": 1,
            "roots": ["زخذف"],
            "rationale": "تعليل كافٍ الطول لاختبار جذر غير موجود.",
        },
        headers=_auth(token),
    )
    assert unknown_root.status_code == 404
    assert unknown_root.json()["error"]["code"] == "ROOT_NOT_FOUND"

    out_of_range = c.post(
        "/api/v1/admin/morphology/decisions",
        json={
            "surah": 113,
            "ayah": 1,
            "word_number": 99,
            "roots": ["قول"],
            "rationale": "تعليل كافٍ الطول لاختبار رقم كلمة خارج النطاق.",
        },
        headers=_auth(token),
    )
    assert out_of_range.status_code == 404
    assert out_of_range.json()["error"]["code"] == "WORD_NOT_FOUND"


# ---- المواضع المرجعية ---------------------------------------------------
def test_golden_cases_all_pass():
    result = _run(lambda s: MorphologyService(s).golden_check())
    # معيار القبول: تغطية 100+ موضعًا تشمل كل نمط صرفي
    assert result["total"] >= 100, f"تغطية ناقصة: {result['total']}"
    assert result["failed"] == 0, result["failures"]
    # كل موضع منسوب لموضعه في المصدر — مرساة بلا استشهاد لا تُثبت شيئًا
    assert all(case["citation"] for case in result["cases"])


def test_golden_cases_cover_every_morphological_pattern():
    """المراسي تغطي أنماط الصرف كلها، لا الجذور السالمة وحدها."""
    result = _run(lambda s: MorphologyService(s).golden_check())
    notes = " ".join(case["note"] or "" for case in result["cases"])
    for pattern in ("مهموز", "أجوف", "ناقص", "مضعّف", "مثال", "رباعي"):
        assert pattern in notes, f"نمط غير مغطى: {pattern}"
    for anchor in ("سوابق", "لواحق", "بلا جذر", "غير محاذية", "بجذرين", "البسملة"):
        assert anchor in notes, f"مرساة غائبة: {anchor}"
    # المراسي موزَّعة على المصحف لا مكدَّسة في أوله
    surahs = {case["surah_number"] for case in result["cases"]}
    assert len(surahs) >= 30, f"تغطية ضيقة: {len(surahs)} سورة"


# ---- المسارات -----------------------------------------------------------
def test_public_ayah_analysis_separates_sources():
    body = client().get("/api/v1/morphology/ayahs/112/1").json()
    assert body["success"] is True
    data = body["data"]
    assert data["uthmani_text"].startswith("قُلْ")
    assert data["word_count"] == 4
    first = data["words"][0]
    assert first["surface_text"] == "قُلْ"
    assert "qac-0.4" in first["analyses_by_source"]
    segments = first["analyses_by_source"]["qac-0.4"]
    assert segments[0]["root"] is not None
    assert segments[0]["pos_label"]
    assert first["root_agreement"] == "single_source"
    assert "منسوب" in data["notice"]

    # «هُوَ» ضمير محلَّل بلا جذر — يجب تمييزه عن كلمة بلا تحليل
    pronoun = data["words"][1]
    assert pronoun["analyses_by_source"]
    assert pronoun["root_agreement"] == "no_root"
    assert pronoun["analyses_by_source"]["qac-0.4"][0]["pos_label"] == "ضمير"


def test_public_ayah_analysis_unknown_ayah_404():
    response = client().get("/api/v1/morphology/ayahs/112/9")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AYAH_NOT_FOUND"


def test_admin_morphology_requires_authorised_role():
    c = client()
    assert c.get("/api/v1/admin/morphology/status").status_code == 401

    researcher = _make_user(UserRole.RESEARCHER)
    assert (
        c.get("/api/v1/admin/morphology/status", headers=_auth(researcher)).status_code
        == 403
    )
    assert (
        c.post("/api/v1/admin/morphology/import", headers=_auth(researcher)).status_code
        == 403
    )
    # الباحث لا يقترح قرار جذر ولا يعتمده
    assert (
        c.post(
            "/api/v1/admin/morphology/decisions",
            json={
                "surah": 113,
                "ayah": 1,
                "word_number": 1,
                "roots": ["قول"],
                "rationale": "محاولة من دور غير مخوَّل بالقرار اللغوي.",
            },
            headers=_auth(researcher),
        ).status_code
        == 403
    )

    officer = _make_user(UserRole.TEXT_OFFICER)
    status = c.get("/api/v1/admin/morphology/status", headers=_auth(officer))
    assert status.status_code == 200
    data = status.json()["data"]
    assert data["tokens"] > 0
    assert data["analyses"] > 0
    assert any(s["code"] == "qac-0.4" for s in data["sources"])


def test_import_refuses_before_tokenization():
    """حماية ترتيب الخطوات: لا استيراد بلا ترميز."""

    async def _check(session):
        service = MorphologyService(session)
        version_id = await service._active_version_id()
        ayah_ids = [
            row[0] for row in await service._ayah_rows(version_id, {109})
        ]
        await session.execute(delete(Token).where(Token.ayah_id.in_(ayah_ids)))
        await session.commit()
        bundle = load_morphology_bundle()
        with pytest.raises(MorphologyError) as exc:
            await service.import_bundle(bundle, surahs={109})
        return exc.value.code

    assert _run(_check) == "NOT_TOKENIZED"


def test_char_offsets_reproduce_the_ayah_text_byte_for_byte():
    """المواضع تعيد بناء نص الآية حرفًا بحرف.

    هذا هو العقد الذي تعتمد عليه واجهة التحليل الصرفي: تعرض النص الموثق
    وتضع الأزرار فوقه بالمواضع، بدل أن تعيد تركيبه من الكلمات — فذلك
    يُسقط علامات الوقف ورموز نهاية الآية (خرق للبند 2 من سياسة السلامة).
    """

    async def _check(session):
        rows = (
            await session.execute(
                select(Ayah.id, Ayah.uthmani_text).where(
                    Ayah.surah_number.in_(sorted(SCOPE))
                )
            )
        ).all()
        checked = 0
        for ayah_id, text in rows:
            tokens = (
                await session.execute(
                    select(Token.char_start, Token.char_end, Token.surface_text)
                    .where(Token.ayah_id == ayah_id)
                    .order_by(Token.char_start)
                )
            ).all()
            rebuilt = []
            cursor = 0
            for start, end, surface in tokens:
                assert text[start:end] == surface
                rebuilt.append(text[cursor:start])
                rebuilt.append(text[start:end])
                cursor = end
            rebuilt.append(text[cursor:])
            assert "".join(rebuilt) == text, f"اختلاف في الآية {ayah_id}"
            checked += 1
        return checked

    assert _run(_check) > 300


def test_waqf_marks_survive_the_offset_round_trip():
    """آية 2:2 فيها علامتا وقف بين الكلمات — لا يجوز أن تسقطا."""

    async def _check(session):
        row = (
            await session.execute(
                select(Ayah.id, Ayah.uthmani_text).where(
                    Ayah.surah_number == 2, Ayah.ayah_number == 2
                )
            )
        ).first()
        ayah_id, text = row
        tokens = (
            await session.execute(
                select(Token.char_start, Token.char_end)
                .where(Token.ayah_id == ayah_id)
                .order_by(Token.char_start)
            )
        ).all()
        gaps = []
        cursor = 0
        for start, end in tokens:
            gaps.append(text[cursor:start])
            cursor = end
        gaps.append(text[cursor:])
        return "".join(gaps), text

    gaps, text = _run(_check)
    assert "ۛ" in text
    # علامتا الوقف تقعان بين الكلمات، فتخرجان في الفجوات لا في الكلمات
    assert gaps.count("ۛ") == 2


# ---- البحث بالصيغة الصرفية ----------------------------------------------
def test_feature_parser_matches_the_source_strings():
    """التفكيك يقرأ ما في المصدر ولا يخمّن ما ليس فيه."""
    from app.utils.morphology_tags import parse_features

    verb = parse_features("STEM|POS:V|IMPF|(X)|LEM:x|ROOT:Hyy|3MS")
    assert verb["aspect"] == "IMPF"
    assert verb["verb_form"] == "X"
    assert (verb["person"], verb["gender"], verb["grammatical_number"]) == (
        "3",
        "M",
        "S",
    )
    assert verb["voice"] is None  # المصدر لم يوسمه، فلا يُفترض

    passive = parse_features("STEM|POS:V|PERF|PASS|LEM:x|ROOT:sAl|3MS")
    assert passive["voice"] == "PASS"
    assert passive["aspect"] == "PERF"

    noun = parse_features("STEM|POS:ADJ|LEM:x|ROOT:Alm|MS|INDEF|NOM")
    assert noun["case_marking"] == "NOM"
    assert noun["definiteness"] == "INDEF"
    assert noun["aspect"] is None

    # السوابق واللواحق بلا أبعاد صرفية
    assert not any(parse_features("PREFIX|w:CONJ+").values())
    assert not any(parse_features("SUFFIX|PRON:3MP").values())


def test_search_by_verb_form():
    """كل صيغ استفعل (الوزن X) — البحث الذي لم يكن ممكنًا قبل الفهرسة."""
    body = client().get("/api/v1/morphology/search?pos=V&verb_form=X&limit=50").json()
    assert body["success"] is True
    data = body["data"]
    assert data["total"] > 0
    for item in data["items"]:
        assert item["pos"] == "V"
        # السمات الحرفية تُعرض كما وردت وتؤكد الترشيح
        assert "(X)" in item["features"]
    assert "منقول" in data["notice"]


def test_search_combines_root_with_dimensions():
    """جذر (س ا ل): أفعاله في نطاق الاختبار كلها مجردة عند المصدر."""
    data = client().get(
        "/api/v1/morphology/search?pos=V&root=سأل&limit=50"
    ).json()["data"]
    assert data["total"] > 0
    assert all(item["root"] for item in data["items"])

    # ترشيح لا يتحقق يعطي صفرًا لا خطأً
    empty = client().get(
        "/api/v1/morphology/search?pos=V&verb_form=X&root=سأل"
    ).json()["data"]
    assert empty["total"] == 0
    assert empty["items"] == []


def test_search_passive_verbs_and_verbatim_features():
    data = client().get(
        "/api/v1/morphology/search?pos=V&voice=PASS&limit=20"
    ).json()["data"]
    assert data["total"] > 0
    for item in data["items"]:
        assert "PASS" in item["features"]


def test_search_form_one_is_translated_not_stored():
    """الوزن المجرد لا يوسمه المصدر: غيابه هو علامته، ويُترجم في الاستعلام."""
    data = client().get(
        "/api/v1/morphology/search?pos=V&verb_form=I&limit=20"
    ).json()["data"]
    assert data["total"] > 0
    for item in data["items"]:
        assert item["pos"] == "V"
        # لا وزن مزيد في السمات الحرفية
        assert not any(f"({roman})" in item["features"] for roman in
                       ("II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"))


def test_search_requires_at_least_one_filter():
    response = client().get("/api/v1/morphology/search")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_FILTERS"

    unknown = client().get("/api/v1/morphology/search?root=زخذف")
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "ROOT_NOT_FOUND"


def test_search_dimensions_are_served_from_one_source():
    data = client().get("/api/v1/morphology/dimensions").json()["data"]
    keys = {d["key"] for d in data["dimensions"]}
    assert {"pos", "aspect", "verb_form", "voice", "case_marking"} <= keys
    aspect = next(d for d in data["dimensions"] if d["key"] == "aspect")
    assert {v["value"] for v in aspect["values"]} == {"PERF", "IMPF", "IMPV"}
    assert all(v["label"] for d in data["dimensions"] for v in d["values"])


def test_parsed_dimensions_match_the_source_token_counts_exactly():
    """تكافؤ صارم: عدد ما فُهرس = عدد ما ورد في المصدر، لا زيادة ولا نقص.

    هذا أقوى ضمان لصحة الفهرسة: لو أسقط المفكّك رمزًا أو اخترع قيمة،
    اختلّ العدد فورًا. يُحسب من حزمة المصدر نفسها لا من القاعدة."""
    from app.utils.morphology_tags import parse_features

    bundle = load_morphology_bundle()
    scope = sorted(SCOPE)

    expected: dict[str, int] = {}
    parsed_counts: dict[str, int] = {}
    for segment in bundle["segments"]:
        if segment[0] not in SCOPE:
            continue
        features = segment[6]
        tokens = set(features.split("|"))
        # المتوقع: عدّ الرموز الخام في المصدر
        for name, vocabulary in (
            ("aspect", {"PERF", "IMPF", "IMPV"}),
            ("voice", {"ACT", "PASS"}),
            ("case_marking", {"NOM", "ACC", "GEN"}),
            ("nominal_form", {"PCPL", "VN"}),
        ):
            if tokens & vocabulary:
                expected[name] = expected.get(name, 0) + 1
        if any(t.startswith("MOOD:") for t in tokens):
            expected["mood"] = expected.get("mood", 0) + 1
        if any(t.startswith("(") and t.endswith(")") for t in tokens):
            expected["verb_form"] = expected.get("verb_form", 0) + 1

        # الفعلي: ما أنتجه المفكّك
        for name, value in parse_features(features).items():
            if value is not None:
                parsed_counts[name] = parsed_counts.get(name, 0) + 1

    for dimension in ("aspect", "voice", "case_marking", "nominal_form", "mood", "verb_form"):
        assert parsed_counts.get(dimension, 0) == expected.get(dimension, 0), (
            f"{dimension}: فُهرس {parsed_counts.get(dimension, 0)} "
            f"مقابل {expected.get(dimension, 0)} في المصدر"
        )
    assert scope  # النطاق غير فارغ


def test_verbatim_features_column_is_never_modified_by_indexing():
    """الفهرسة لا تمس العمود الحرفي — شرط رخصة المدونة: لا تعديل للملف."""
    bundle = load_morphology_bundle()
    by_position = {
        (s[0], s[1], s[2], s[3]): s[6] for s in bundle["segments"] if s[0] in SCOPE
    }

    async def _check(session):
        rows = (
            await session.execute(
                select(
                    Ayah.surah_number,
                    Ayah.ayah_number,
                    MorphologicalAnalysis.word_number,
                    MorphologicalAnalysis.segment_number,
                    MorphologicalAnalysis.features,
                )
                .join(Ayah, Ayah.id == MorphologicalAnalysis.ayah_id)
                .where(Ayah.surah_number.in_([112, 113, 114]))
            )
        ).all()
        return rows

    rows = _run(_check)
    assert rows
    for surah, ayah, word, segment, features in rows:
        assert features == by_position[(surah, ayah, word, segment)]


# ---- إطار محوّلات المصادر (الشاهد الثاني) --------------------------------
def test_source_adapter_refuses_a_bundle_without_a_licence():
    """لا تُبنى حزمة مصدر بلا رخصة معلنة — الضابط في الإطار لا المحوّل."""
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.insert(
        0, str(_Path(__file__).resolve().parents[3] / "scripts" / "import-quran")
    )
    from source_adapter import AdapterError, SourceMeta, build_bundle

    incomplete = SourceMeta(
        source_code="test",
        name="مصدر اختباري",
        url="https://example.org",
        source_version="1",
        license="   ",  # فراغ لا يُقبل
        notice="اختبار",
        provides_roots=False,
    )
    with pytest.raises(AdapterError) as exc:
        build_bundle(
            meta=incomplete,
            reader=lambda: [],
            source_files=[],
            out_path=_Path("unused.json.gz"),
        )
    assert "رخصة" in str(exc.value)


def test_source_adapter_rejects_incomplete_coverage():
    """مصدر لا يغطي المصحف كاملًا يوقف البناء بدل أن يُنتج حزمة ناقصة."""
    import sys as _sys
    import tempfile
    from pathlib import Path as _Path

    _sys.path.insert(
        0, str(_Path(__file__).resolve().parents[3] / "scripts" / "import-quran")
    )
    from source_adapter import AdapterError, SourceMeta, SourceSegment, build_bundle

    meta = SourceMeta(
        source_code="partial",
        name="مصدر جزئي",
        url="https://example.org",
        source_version="1",
        license="رخصة اختبارية",
        notice="اختبار",
        provides_roots=False,
    )
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as handle:
        handle.write(b"source")
        source_file = _Path(handle.name)

    def _reader():
        # آية واحدة فقط — تغطية ناقصة
        return [
            SourceSegment(
                surah=1, ayah=1, word=1, segment=1,
                form="x", tag="N", features="STEM|POS:N", pos="N",
            )
        ]

    with pytest.raises(AdapterError) as exc:
        build_bundle(
            meta=meta,
            reader=_reader,
            source_files=[source_file],
            out_path=_Path(tempfile.gettempdir()) / "partial.json.gz",
        )
    assert "الآيات" in str(exc.value)
    source_file.unlink(missing_ok=True)


def test_source_adapter_refuses_a_root_claim_it_cannot_back():
    """مصدر يُعلن أنه يشهد على الجذور ثم لا يُنتج جذرًا — يوقف البناء.

    قرار اللجنة في 2026-07-25: أقوى المرشحين لشاهد ثانٍ (MASAQ) مدونة
    بشرية كاملة **بلا حقل جذر**. فلو مرّ إعلانٌ لا تسنده البيانات لظهر
    في الواجهة «اتفاق على الجذور» لا وجود له."""
    import sys as _sys
    import tempfile
    from pathlib import Path as _Path

    _sys.path.insert(
        0, str(_Path(__file__).resolve().parents[3] / "scripts" / "import-quran")
    )
    from source_adapter import AdapterError, SourceMeta, SourceSegment, build_bundle

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as handle:
        handle.write(b"source")
        source_file = _Path(handle.name)

    claims_roots = SourceMeta(
        source_code="claims",
        name="مصدر يدّعي الجذور",
        url="https://example.org",
        source_version="1",
        license="رخصة اختبارية",
        notice="اختبار",
        provides_roots=True,  # الإعلان
    )

    def _reader():
        # ولا جذر واحد في البيانات — نقيض الإعلان
        return [
            SourceSegment(
                surah=1, ayah=1, word=1, segment=1,
                form="x", tag="N", features="STEM|POS:N", pos="N",
            )
        ]

    with pytest.raises(AdapterError) as exc:
        build_bundle(
            meta=claims_roots,
            reader=_reader,
            source_files=[source_file],
            out_path=_Path(tempfile.gettempdir()) / "claims.json.gz",
        )
    # يقف عند التناقض قبل أن يبلغ فحص التغطية
    assert "الجذور" in str(exc.value)
    source_file.unlink(missing_ok=True)
