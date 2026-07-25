"""اختبارات المرحلة E — المصادر والاستشهادات والادعاءات.

تثبت القواعد العلمية لا الشكل: لا مصدر مجهول الطبعة، ولا يتحقق المُدخِل
من إدخاله، ولا ادعاء بلا دليل من مصدر متحقَّق منه، ولا يعتمد الباحث
ادعاءه، والدليل المعارض يُحفظ ويُعرض.
"""

import asyncio
import uuid

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import SessionFactory
from app.main import app
from app.models.enums import UserRole
from app.models.user import User, UserRoleAssignment


def client() -> TestClient:
    return TestClient(app)


def _make_user(*roles: UserRole, password: str = "scholarpass1") -> str:
    email = f"s{uuid.uuid4().hex[:8]}@example.com"

    async def _create():
        async with SessionFactory() as session:
            user = User(
                email=email,
                display_name="باحث",
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


def _source_body(**overrides) -> dict:
    body = {
        "code": f"lisan-{uuid.uuid4().hex[:6]}",
        "title": "لسان العرب",
        "author": "ابن منظور",
        "work_type": "dictionary",
        "edition": "دار صادر، بيروت، ط3 1414هـ",
        "license_note": "نسخة مطبوعة مملوكة للمكتبة، النقل بالاستشهاد المحدود",
        "publisher": "دار صادر",
        "publication_year": 1994,
        "language": "ar",
    }
    body.update(overrides)
    return body


def _verified_source(c: TestClient, author_token: str, verifier_token: str) -> str:
    created = c.post("/api/v1/sources", json=_source_body(), headers=_auth(author_token))
    assert created.status_code == 200, created.text
    source_id = created.json()["data"]["id"]
    verified = c.post(
        f"/api/v1/sources/{source_id}/verify", headers=_auth(verifier_token)
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["data"]["is_verified"] is True
    return source_id


def _citation(c: TestClient, token: str, source_id: str, locator: str) -> str:
    response = c.post(
        "/api/v1/citations",
        json={
            "source_work_id": source_id,
            "locator": locator,
            "quoted_text": "مادة (س أ ل) في المعجم",
            "paraphrase": "تلخيص المعنى المعجمي للمادة.",
        },
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


# ---- المصادر ------------------------------------------------------------
def test_source_without_edition_or_license_is_rejected():
    token = _make_user(UserRole.RESEARCHER)
    c = client()
    for missing in ("edition", "license_note"):
        body = _source_body()
        body[missing] = ""
        response = c.post("/api/v1/sources", json=body, headers=_auth(token))
        assert response.status_code == 422, (missing, response.text)


def test_adder_cannot_verify_their_own_source():
    token = _make_user(UserRole.QUALITY_MANAGER)
    c = client()
    created = c.post("/api/v1/sources", json=_source_body(), headers=_auth(token))
    source_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"
    assert created.json()["data"]["is_verified"] is False

    self_verify = c.post(f"/api/v1/sources/{source_id}/verify", headers=_auth(token))
    assert self_verify.status_code == 409
    assert self_verify.json()["error"]["code"] == "SELF_VERIFICATION_FORBIDDEN"


def test_researcher_cannot_verify_sources():
    author = _make_user(UserRole.RESEARCHER)
    other_researcher = _make_user(UserRole.RESEARCHER)
    c = client()
    created = c.post("/api/v1/sources", json=_source_body(), headers=_auth(author))
    source_id = created.json()["data"]["id"]
    response = c.post(
        f"/api/v1/sources/{source_id}/verify", headers=_auth(other_researcher)
    )
    assert response.status_code == 403


def test_rejected_source_records_its_reason():
    author = _make_user(UserRole.RESEARCHER)
    verifier = _make_user(UserRole.QUALITY_MANAGER)
    c = client()
    created = c.post("/api/v1/sources", json=_source_body(), headers=_auth(author))
    source_id = created.json()["data"]["id"]
    rejected = c.post(
        f"/api/v1/sources/{source_id}/reject",
        json={"reason": "الطبعة غير محددة بدقة ولا يمكن التحقق من ترقيم صفحاتها."},
        headers=_auth(verifier),
    )
    assert rejected.status_code == 200
    data = rejected.json()["data"]
    assert data["status"] == "rejected"
    assert "الطبعة" in data["rejection_reason"]
    assert data["is_verified"] is False


# ---- الاستشهادات --------------------------------------------------------
def test_citation_requires_a_locator_and_content():
    author = _make_user(UserRole.RESEARCHER)
    verifier = _make_user(UserRole.QUALITY_MANAGER)
    c = client()
    source_id = _verified_source(c, author, verifier)

    no_locator = c.post(
        "/api/v1/citations",
        json={"source_work_id": source_id, "locator": "", "quoted_text": "نص"},
        headers=_auth(author),
    )
    assert no_locator.status_code == 422

    empty = c.post(
        "/api/v1/citations",
        json={"source_work_id": source_id, "locator": "11/318"},
        headers=_auth(author),
    )
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "CITATION_EMPTY"


# ---- الادعاءات ----------------------------------------------------------
def test_claim_cannot_be_submitted_without_verified_evidence():
    author = _make_user(UserRole.RESEARCHER)
    verifier = _make_user(UserRole.QUALITY_MANAGER)
    c = client()

    claim = c.post(
        "/api/v1/claims",
        json={
            "statement": "الجذر (س ا ل) في القرآن يغلب فيه معنى الطلب لا الاستفهام المجرد.",
            "claim_type": "semantic",
            "subject_type": "root",
            "root": "سأل",
        },
        headers=_auth(author),
    )
    assert claim.status_code == 200, claim.text
    claim_id = claim.json()["data"]["id"]
    assert claim.json()["data"]["status"] == "draft"

    # بلا دليل أصلًا
    bare = c.post(f"/api/v1/claims/{claim_id}/submit", headers=_auth(author))
    assert bare.status_code == 409
    assert bare.json()["error"]["code"] == "EVIDENCE_REQUIRED"

    # دليل من مصدر غير متحقَّق منه لا يكفي
    unverified = c.post(
        "/api/v1/sources", json=_source_body(), headers=_auth(author)
    ).json()["data"]["id"]
    weak_citation = _citation(c, author, unverified, "11/318")
    c.post(
        f"/api/v1/claims/{claim_id}/evidence",
        json={"citation_id": weak_citation, "stance": "supports"},
        headers=_auth(author),
    )
    still_blocked = c.post(f"/api/v1/claims/{claim_id}/submit", headers=_auth(author))
    assert still_blocked.status_code == 409
    assert still_blocked.json()["error"]["code"] == "EVIDENCE_REQUIRED"

    # دليل من مصدر متحقَّق منه يفتح الطريق
    good_source = _verified_source(c, author, verifier)
    good_citation = _citation(c, author, good_source, "11/318")
    c.post(
        f"/api/v1/claims/{claim_id}/evidence",
        json={"citation_id": good_citation, "stance": "supports"},
        headers=_auth(author),
    )
    submitted = c.post(f"/api/v1/claims/{claim_id}/submit", headers=_auth(author))
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["status"] == "under_review"


def test_claim_needs_two_independent_reviewers_and_never_its_author():
    author = _make_user(UserRole.RESEARCHER, UserRole.LINGUISTIC_REVIEWER)
    verifier = _make_user(UserRole.QUALITY_MANAGER)
    reviewer_one = _make_user(UserRole.LINGUISTIC_REVIEWER)
    reviewer_two = _make_user(UserRole.SHARIA_REVIEWER)
    c = client()

    source_id = _verified_source(c, author, verifier)
    citation_id = _citation(c, author, source_id, "11/319")
    claim_id = c.post(
        "/api/v1/claims",
        json={
            "statement": "لفظ (سأل) في سورة البقرة يرد في سياق الطلب من الرسول لا الاعتراض.",
            "subject_type": "word",
            "surah": 2,
            "ayah": 108,
            "word_number": 4,
        },
        headers=_auth(author),
    ).json()["data"]["id"]
    c.post(
        f"/api/v1/claims/{claim_id}/evidence",
        json={"citation_id": citation_id, "stance": "supports"},
        headers=_auth(author),
    )
    c.post(f"/api/v1/claims/{claim_id}/submit", headers=_auth(author))

    # صاحب الادعاء لا يعتمده ولو كان مراجعًا لغويًا
    self_approve = c.post(
        f"/api/v1/claims/{claim_id}/approve", headers=_auth(author)
    )
    assert self_approve.status_code == 409
    assert self_approve.json()["error"]["code"] == "SELF_REVIEW_FORBIDDEN"

    first = c.post(f"/api/v1/claims/{claim_id}/approve", headers=_auth(reviewer_one))
    assert first.status_code == 200
    assert first.json()["data"]["status"] == "under_review"

    repeat = c.post(f"/api/v1/claims/{claim_id}/approve", headers=_auth(reviewer_one))
    assert repeat.status_code == 409
    assert repeat.json()["error"]["code"] == "SECOND_REVIEW_REQUIRED"

    second = c.post(f"/api/v1/claims/{claim_id}/approve", headers=_auth(reviewer_two))
    assert second.status_code == 200
    data = second.json()["data"]
    assert data["status"] == "approved"
    assert data["confidence"] == "high"
    assert data["approved_by_first"] != data["approved_by_second"]


def test_opposing_evidence_is_kept_and_shown():
    author = _make_user(UserRole.RESEARCHER)
    verifier = _make_user(UserRole.QUALITY_MANAGER)
    c = client()
    source_id = _verified_source(c, author, verifier)
    supporting = _citation(c, author, source_id, "11/320")
    opposing = _citation(c, author, source_id, "3/44")

    claim_id = c.post(
        "/api/v1/claims",
        json={
            "statement": "دعوى دلالية فيها خلاف بين المعاجم يستحق التوثيق الكامل.",
            "subject_type": "root",
            "root": "قرأ",
        },
        headers=_auth(author),
    ).json()["data"]["id"]
    c.post(
        f"/api/v1/claims/{claim_id}/evidence",
        json={"citation_id": supporting, "stance": "supports"},
        headers=_auth(author),
    )
    result = c.post(
        f"/api/v1/claims/{claim_id}/evidence",
        json={
            "citation_id": opposing,
            "stance": "opposes",
            "note": "المعجم ينص على معنى آخر في هذه المادة.",
        },
        headers=_auth(author),
    )
    assert result.status_code == 200
    data = result.json()["data"]
    assert data["supporting_count"] == 1
    assert data["opposing_count"] == 1
    stances = {e["stance"] for e in data["evidence"]}
    assert stances == {"supports", "opposes"}


def test_dispute_records_reason_and_marks_confidence():
    author = _make_user(UserRole.RESEARCHER)
    verifier = _make_user(UserRole.QUALITY_MANAGER)
    reviewer = _make_user(UserRole.SHARIA_REVIEWER)
    c = client()
    source_id = _verified_source(c, author, verifier)
    citation_id = _citation(c, author, source_id, "11/321")
    claim_id = c.post(
        "/api/v1/claims",
        json={
            "statement": "دعوى ستُحال إلى الخلاف بعد اعتراض مراجع مختص عليها.",
            "subject_type": "root",
            "root": "امن",
        },
        headers=_auth(author),
    ).json()["data"]["id"]
    c.post(
        f"/api/v1/claims/{claim_id}/evidence",
        json={"citation_id": citation_id, "stance": "supports"},
        headers=_auth(author),
    )
    c.post(f"/api/v1/claims/{claim_id}/submit", headers=_auth(author))

    disputed = c.post(
        f"/api/v1/claims/{claim_id}/dispute",
        json={"reason": "الاستشهاد لا يدل على المدَّعى، والمعنى في المصدر مقيد بسياق."},
        headers=_auth(reviewer),
    )
    assert disputed.status_code == 200
    data = disputed.json()["data"]
    assert data["status"] == "disputed"
    assert data["confidence"] == "disputed"
    assert "الاستشهاد" in data["resolution_note"]


def test_public_claim_listing_excludes_drafts():
    author = _make_user(UserRole.RESEARCHER)
    c = client()
    c.post(
        "/api/v1/claims",
        json={
            "statement": "مسودة ادعاء لا ينبغي أن تظهر في القائمة العامة إطلاقًا.",
            "subject_type": "root",
            "root": "كتب",
        },
        headers=_auth(author),
    )
    body = client().get("/api/v1/claims").json()
    assert body["success"] is True
    statuses = {
        item["status"]
        for group in ("approved", "disputed")
        for item in body["data"][group]["items"]
    }
    assert "draft" not in statuses
    assert "under_review" not in statuses
    assert "ليست نتائج" in body["data"]["notice"]


def test_draft_claim_is_private_to_its_author():
    author = _make_user(UserRole.RESEARCHER)
    stranger = _make_user(UserRole.RESEARCHER)
    c = client()
    claim_id = c.post(
        "/api/v1/claims",
        json={
            "statement": "مسودة خاصة بصاحبها لا يطلع عليها باحث آخر قبل المراجعة.",
            "subject_type": "root",
            "root": "علم",
        },
        headers=_auth(author),
    ).json()["data"]["id"]

    assert c.get(f"/api/v1/claims/{claim_id}", headers=_auth(author)).status_code == 200
    forbidden = c.get(f"/api/v1/claims/{claim_id}", headers=_auth(stranger))
    assert forbidden.status_code == 403
    assert c.get(f"/api/v1/claims/{claim_id}").status_code == 401


def test_claim_subject_must_resolve_to_real_data():
    author = _make_user(UserRole.RESEARCHER)
    c = client()
    unknown_root = c.post(
        "/api/v1/claims",
        json={
            "statement": "دعوى على جذر غير موجود في البيانات ينبغي أن تُرفض فورًا.",
            "subject_type": "root",
            "root": "زخذف",
        },
        headers=_auth(author),
    )
    assert unknown_root.status_code == 404
    assert unknown_root.json()["error"]["code"] == "ROOT_NOT_FOUND"

    unknown_ayah = c.post(
        "/api/v1/claims",
        json={
            "statement": "دعوى على آية غير موجودة في الإصدار المفعَّل ينبغي أن تُرفض.",
            "subject_type": "ayah",
            "surah": 112,
            "ayah": 99,
        },
        headers=_auth(author),
    )
    assert unknown_ayah.status_code == 404
    assert unknown_ayah.json()["error"]["code"] == "AYAH_NOT_FOUND"


def test_approved_claim_is_locked_against_silent_evidence_changes():
    author = _make_user(UserRole.RESEARCHER)
    verifier = _make_user(UserRole.QUALITY_MANAGER)
    reviewer_one = _make_user(UserRole.LINGUISTIC_REVIEWER)
    reviewer_two = _make_user(UserRole.SHARIA_REVIEWER)
    c = client()
    source_id = _verified_source(c, author, verifier)
    citation_id = _citation(c, author, source_id, "11/322")
    extra_citation = _citation(c, author, source_id, "11/323")

    claim_id = c.post(
        "/api/v1/claims",
        json={
            "statement": "دعوى ستُعتمد ثم يُحاول تغيير أدلتها بلا تصحيح موثق.",
            "subject_type": "root",
            "root": "حمد",
        },
        headers=_auth(author),
    ).json()["data"]["id"]
    c.post(
        f"/api/v1/claims/{claim_id}/evidence",
        json={"citation_id": citation_id, "stance": "supports"},
        headers=_auth(author),
    )
    c.post(f"/api/v1/claims/{claim_id}/submit", headers=_auth(author))
    c.post(f"/api/v1/claims/{claim_id}/approve", headers=_auth(reviewer_one))
    c.post(f"/api/v1/claims/{claim_id}/approve", headers=_auth(reviewer_two))

    locked = c.post(
        f"/api/v1/claims/{claim_id}/evidence",
        json={"citation_id": extra_citation, "stance": "supports"},
        headers=_auth(author),
    )
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "CLAIM_LOCKED"
