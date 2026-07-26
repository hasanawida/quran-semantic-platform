"""اختبارات المرحلة G — صندوق المراجعة والخلافات والتصحيحات.

تثبت: لا تكليف بمراجعة الذات ولا مع تضارب مصلحة، والخلاف يظهر ولا
يحسمه رافعه، والتصحيح يحفظ قبل/بعد ويُبطل اعتماد ما صُحّح.
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


def _make_user(*roles: UserRole, password: str = "reviewpass1") -> tuple[str, str]:
    email = f"g{uuid.uuid4().hex[:8]}@example.com"

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
            return str(user.id)

    user_id = asyncio.run(_create())
    token = client().post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["data"]["access_token"]
    return user_id, token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _claim(c: TestClient, author_token: str, root: str = "حمد") -> str:
    return c.post(
        "/api/v1/claims",
        json={
            "statement": f"دعوى دلالية عن الجذر {root} لأغراض اختبار صندوق المراجعة.",
            "subject_type": "root",
            "root": root,
        },
        headers=_auth(author_token),
    ).json()["data"]["id"]


def _approved_claim(c: TestClient, author_token: str, root: str) -> str:
    _, verifier = _make_user(UserRole.QUALITY_MANAGER)
    _, reviewer_one = _make_user(UserRole.LINGUISTIC_REVIEWER)
    _, reviewer_two = _make_user(UserRole.SHARIA_REVIEWER)
    source = c.post(
        "/api/v1/sources",
        json={
            "code": f"src-{uuid.uuid4().hex[:8]}",
            "title": "أساس البلاغة",
            "author": "الزمخشري",
            "work_type": "dictionary",
            "edition": "دار الكتب العلمية، 1419هـ",
            "license_note": "نسخة مطبوعة، النقل بالاستشهاد المحدود",
        },
        headers=_auth(author_token),
    ).json()["data"]["id"]
    c.post(f"/api/v1/sources/{source}/verify", headers=_auth(verifier))
    citation = c.post(
        "/api/v1/citations",
        json={"source_work_id": source, "locator": "1/55", "paraphrase": "تلخيص."},
        headers=_auth(author_token),
    ).json()["data"]["id"]
    claim_id = _claim(c, author_token, root)
    c.post(
        f"/api/v1/claims/{claim_id}/evidence",
        json={"citation_id": citation, "stance": "supports"},
        headers=_auth(author_token),
    )
    c.post(f"/api/v1/claims/{claim_id}/submit", headers=_auth(author_token))
    c.post(f"/api/v1/claims/{claim_id}/approve", headers=_auth(reviewer_one))
    c.post(f"/api/v1/claims/{claim_id}/approve", headers=_auth(reviewer_two))
    return claim_id


# ---- التكليفات ----------------------------------------------------------
def test_author_cannot_be_assigned_to_review_their_own_work():
    author_id, author = _make_user(UserRole.RESEARCHER, UserRole.LINGUISTIC_REVIEWER)
    _, manager = _make_user(UserRole.QUALITY_MANAGER)
    c = client()
    claim_id = _claim(c, author)

    blocked = c.post(
        "/api/v1/review/assignments",
        json={"target_type": "claim", "target_id": claim_id, "reviewer_id": author_id},
        headers=_auth(manager),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "SELF_REVIEW_FORBIDDEN"


def test_declared_conflict_of_interest_blocks_assignment():
    _, author = _make_user(UserRole.RESEARCHER)
    reviewer_id, reviewer = _make_user(UserRole.LINGUISTIC_REVIEWER)
    _, manager = _make_user(UserRole.QUALITY_MANAGER)
    c = client()
    claim_id = _claim(c, author, "علم")

    declared = c.post(
        "/api/v1/review/conflicts",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "details": "شاركت الباحث في إعداد مادة هذه الدعوى.",
        },
        headers=_auth(reviewer),
    )
    assert declared.status_code == 200

    blocked = c.post(
        "/api/v1/review/assignments",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "reviewer_id": reviewer_id,
        },
        headers=_auth(manager),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "CONFLICT_OF_INTEREST"


def test_assignment_lifecycle_and_queue():
    _, author = _make_user(UserRole.RESEARCHER)
    reviewer_id, reviewer = _make_user(UserRole.LINGUISTIC_REVIEWER)
    _, manager = _make_user(UserRole.QUALITY_MANAGER)
    c = client()
    claim_id = _claim(c, author, "كتب")

    assignment = c.post(
        "/api/v1/review/assignments",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "reviewer_id": reviewer_id,
        },
        headers=_auth(manager),
    )
    assert assignment.status_code == 200
    assignment_id = assignment.json()["data"]["id"]
    assert assignment.json()["data"]["status"] == "pending"

    queue = c.get("/api/v1/review/assignments/mine", headers=_auth(reviewer)).json()
    assert assignment_id in {a["id"] for a in queue["data"]}

    # لا يكمله غير المكلَّف
    stranger_id, stranger = _make_user(UserRole.LINGUISTIC_REVIEWER)
    assert stranger_id
    not_mine = c.post(
        f"/api/v1/review/assignments/{assignment_id}/respond",
        json={"accept": True},
        headers=_auth(stranger),
    )
    assert not_mine.status_code == 403

    # لا يكتمل قبل القبول
    early = c.post(
        f"/api/v1/review/assignments/{assignment_id}/complete", headers=_auth(reviewer)
    )
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "NOT_ACCEPTED"

    accepted = c.post(
        f"/api/v1/review/assignments/{assignment_id}/respond",
        json={"accept": True},
        headers=_auth(reviewer),
    )
    assert accepted.json()["data"]["status"] == "accepted"
    done = c.post(
        f"/api/v1/review/assignments/{assignment_id}/complete", headers=_auth(reviewer)
    )
    assert done.json()["data"]["status"] == "completed"


def test_declining_an_assignment_requires_a_reason():
    _, author = _make_user(UserRole.RESEARCHER)
    reviewer_id, reviewer = _make_user(UserRole.SHARIA_REVIEWER)
    _, manager = _make_user(UserRole.QUALITY_MANAGER)
    c = client()
    claim_id = _claim(c, author, "صبر")
    assignment_id = c.post(
        "/api/v1/review/assignments",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "reviewer_id": reviewer_id,
        },
        headers=_auth(manager),
    ).json()["data"]["id"]

    bare = c.post(
        f"/api/v1/review/assignments/{assignment_id}/respond",
        json={"accept": False},
        headers=_auth(reviewer),
    )
    assert bare.status_code == 422
    assert bare.json()["error"]["code"] == "REASON_REQUIRED"

    declined = c.post(
        f"/api/v1/review/assignments/{assignment_id}/respond",
        json={"accept": False, "reason": "التخصص خارج مجالي."},
        headers=_auth(reviewer),
    )
    assert declined.json()["data"]["status"] == "declined"
    assert declined.json()["data"]["decline_reason"]


# ---- الخلافات -----------------------------------------------------------
def test_dispute_marks_the_claim_and_is_visible_to_everyone_signed_in():
    _, author = _make_user(UserRole.RESEARCHER)
    _, reviewer = _make_user(UserRole.LINGUISTIC_REVIEWER)
    _, bystander = _make_user(UserRole.RESEARCHER)
    c = client()
    claim_id = _approved_claim(c, author, "نور")

    raised = c.post(
        "/api/v1/review/disputes",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "reason": "الاستشهاد المرفق لا يدل على عموم الدعوى ويحتاج تقييدًا.",
        },
        headers=_auth(reviewer),
    )
    assert raised.status_code == 200, raised.text
    dispute_id = raised.json()["data"]["id"]

    claim = c.get(f"/api/v1/claims/{claim_id}", headers=_auth(author)).json()["data"]
    assert claim["status"] == "disputed"
    assert claim["confidence"] == "disputed"

    listed = c.get("/api/v1/review/disputes", headers=_auth(bystander)).json()["data"]
    assert dispute_id in {d["id"] for d in listed}


def test_author_cannot_dispute_their_own_work_and_raiser_cannot_arbitrate():
    author_id, author = _make_user(UserRole.RESEARCHER, UserRole.LINGUISTIC_REVIEWER)
    _, arbiter = _make_user(UserRole.ARBITRATION_COMMITTEE)
    _, raiser = _make_user(UserRole.LINGUISTIC_REVIEWER, UserRole.QUALITY_MANAGER)
    assert author_id
    c = client()
    claim_id = _approved_claim(c, author, "رحم")

    self_dispute = c.post(
        "/api/v1/review/disputes",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "reason": "أعترض على دعواي بنفسي بدل تصحيحها بتصحيح موثق.",
        },
        headers=_auth(author),
    )
    assert self_dispute.status_code == 409
    assert self_dispute.json()["error"]["code"] == "SELF_DISPUTE_FORBIDDEN"

    dispute_id = c.post(
        "/api/v1/review/disputes",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "reason": "الدعوى تحتاج شواهد أوسع من موضع واحد في المعجم.",
        },
        headers=_auth(raiser),
    ).json()["data"]["id"]

    self_resolve = c.post(
        f"/api/v1/review/disputes/{dispute_id}/resolve",
        json={"resolution": "أحسم الخلاف الذي رفعته بنفسي وهذا ممنوع."},
        headers=_auth(raiser),
    )
    assert self_resolve.status_code == 409
    assert self_resolve.json()["error"]["code"] == "SELF_ARBITRATION_FORBIDDEN"

    resolved = c.post(
        f"/api/v1/review/disputes/{dispute_id}/resolve",
        json={"resolution": "تُقيَّد الدعوى بسياق الآيات المكية وتُعاد للمراجعة."},
        headers=_auth(arbiter),
    )
    assert resolved.status_code == 200
    data = resolved.json()["data"]
    assert data["status"] == "resolved"
    assert data["resolution"]
    assert data["resolved_by"]


def test_owner_cannot_arbitrate_a_dispute_on_their_own_work():
    """الثغرة التي كشفها تدقيق مواصفة «لا اعتماد ذاتي».

    كان `resolve_dispute` يستثني **رافع** الخلاف وحده. فصاحبُ الادعاء إن
    حمل دور التحكيم رفع وسم «مختلف فيه» عن عمله بنفسه — اعتمادٌ ذاتي
    دخل من باب الخلاف لا من باب الاعتماد، ولم يكشفه اختبار."""
    _, author = _make_user(
        UserRole.RESEARCHER,
        UserRole.LINGUISTIC_REVIEWER,
        UserRole.ARBITRATION_COMMITTEE,
    )
    _, raiser = _make_user(UserRole.LINGUISTIC_REVIEWER, UserRole.QUALITY_MANAGER)
    c = client()
    claim_id = _approved_claim(c, author, "سجد")

    dispute_id = c.post(
        "/api/v1/review/disputes",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "reason": "الشاهد المعجمي لا يحتمل التعميم الوارد في الدعوى.",
        },
        headers=_auth(raiser),
    ).json()["data"]["id"]

    own = c.post(
        f"/api/v1/review/disputes/{dispute_id}/resolve",
        json={"resolution": "أحسم الخلاف على ادعائي أنا وأرفع الوسم عنه."},
        headers=_auth(author),
    )
    assert own.status_code == 409
    assert own.json()["error"]["code"] == "SELF_ARBITRATION_FORBIDDEN"


# ---- التصحيحات ----------------------------------------------------------
def test_owner_cannot_approve_a_correction_of_their_own_work():
    """وأختها: `approve_correction` كان يستثني **مقترح** التصحيح وحده.

    فلو اقترح غيري تصحيحًا على ادعائي اعتمدتُه أنا — وأنا صاحبه. والتصحيح
    يُبطل الاعتماد ويعيد إلى المراجعة، فالباب يمسّ حال العمل لا حاشيته."""
    _, author = _make_user(UserRole.RESEARCHER, UserRole.QUALITY_MANAGER)
    _, proposer = _make_user(UserRole.LINGUISTIC_REVIEWER)
    c = client()
    claim_id = _approved_claim(c, author, "شكر")

    correction_id = c.post(
        "/api/v1/review/corrections",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "description": "العبارة تعمّم بلا شاهد، وتُقيَّد بموضعها في المعجم.",
            "new_statement": "الجذر في هذا الموضع بمعنى مقيَّد بسياق الآية ومحدود بما دلّ عليه الدليل.",
        },
        headers=_auth(proposer),
    ).json()["data"]["id"]

    own = c.post(
        f"/api/v1/review/corrections/{correction_id}/approve",
        json={},
        headers=_auth(author),
    )
    assert own.status_code == 409
    assert own.json()["error"]["code"] == "SELF_REVIEW_FORBIDDEN"


def test_correction_keeps_before_and_after_and_voids_prior_approval():
    _, author = _make_user(UserRole.RESEARCHER)
    _, proposer = _make_user(UserRole.LINGUISTIC_REVIEWER)
    _, approver = _make_user(UserRole.QUALITY_MANAGER)
    c = client()
    claim_id = _approved_claim(c, author, "قرأ")
    before_claim = c.get(f"/api/v1/claims/{claim_id}", headers=_auth(author)).json()["data"]
    assert before_claim["status"] == "approved"
    assert before_claim["approved_by_first"] and before_claim["approved_by_second"]

    proposed = c.post(
        "/api/v1/review/corrections",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "description": "تقييد الدعوى بسياقها ورفع التعميم غير المؤيد بالدليل.",
            "new_statement": "دعوى مصححة مقيَّدة بسياقها ومحدودة بما دلّ عليه الدليل فعلًا.",
        },
        headers=_auth(proposer),
    )
    assert proposed.status_code == 200, proposed.text
    correction_id = proposed.json()["data"]["id"]
    assert proposed.json()["data"]["before"]["status"] == "approved"

    # لا يعتمد التصحيحَ مقترحُه
    self_approve = c.post(
        f"/api/v1/review/corrections/{correction_id}/approve", headers=_auth(proposer)
    )
    assert self_approve.status_code == 409
    assert self_approve.json()["error"]["code"] == "SELF_REVIEW_FORBIDDEN"

    # لا يُطبَّق قبل الاعتماد
    early = c.post(
        f"/api/v1/review/corrections/{correction_id}/apply", headers=_auth(approver)
    )
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "NOT_APPROVED"

    c.post(
        f"/api/v1/review/corrections/{correction_id}/approve", headers=_auth(approver)
    )
    applied = c.post(
        f"/api/v1/review/corrections/{correction_id}/apply", headers=_auth(approver)
    )
    assert applied.status_code == 200
    data = applied.json()["data"]
    assert data["status"] == "applied"
    assert data["before"]["status"] == "approved"
    assert data["after"]["status"] == "under_review"

    after_claim = c.get(f"/api/v1/claims/{claim_id}", headers=_auth(author)).json()["data"]
    assert after_claim["statement"].startswith("دعوى مصححة")
    assert after_claim["status"] == "under_review"
    assert after_claim["approved_by_first"] is None
    assert after_claim["approved_by_second"] is None

    # سجل التصحيحات يكشف نص المسودة السابق، فهو للمراجعين لا لكل مسجَّل
    assert (
        c.get(
            f"/api/v1/review/corrections/claim/{claim_id}", headers=_auth(author)
        ).status_code
        == 403
    )
    history = c.get(
        f"/api/v1/review/corrections/claim/{claim_id}", headers=_auth(approver)
    ).json()["data"]
    assert len(history) == 1
    assert history[0]["before"]["statement"] != history[0]["after"]["statement"]


def test_correction_of_a_claim_requires_the_corrected_text():
    _, author = _make_user(UserRole.RESEARCHER)
    _, proposer = _make_user(UserRole.LINGUISTIC_REVIEWER)
    c = client()
    claim_id = _claim(c, author, "سأل")
    response = c.post(
        "/api/v1/review/corrections",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "description": "وصف تصحيح بلا نص مصحَّح ينبغي أن يُرفض.",
        },
        headers=_auth(proposer),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NEW_STATEMENT_REQUIRED"


def test_review_thread_gathers_comments_disputes_and_assignments():
    _, author = _make_user(UserRole.RESEARCHER)
    reviewer_id, reviewer = _make_user(UserRole.LINGUISTIC_REVIEWER)
    _, manager = _make_user(UserRole.QUALITY_MANAGER)
    c = client()
    # ادعاء مرفوع للمراجعة: الخلاف لا يُرفع على مسودة
    claim_id = _approved_claim(c, author, "امن")
    c.post(
        "/api/v1/review/assignments",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "reviewer_id": reviewer_id,
        },
        headers=_auth(manager),
    )
    c.post(
        "/api/v1/review/comments",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "body": "يلزم توثيق الدعوى بمعجم ثانٍ.",
        },
        headers=_auth(reviewer),
    )
    c.post(
        "/api/v1/review/disputes",
        json={
            "target_type": "claim",
            "target_id": claim_id,
            "reason": "الدعوى معممة بلا دليل كافٍ على العموم.",
        },
        headers=_auth(reviewer),
    )

    assert (
        c.get(
            f"/api/v1/review/threads/claim/{claim_id}", headers=_auth(author)
        ).status_code
        == 403
    )
    thread = c.get(
        f"/api/v1/review/threads/claim/{claim_id}", headers=_auth(manager)
    ).json()["data"]
    assert len(thread["comments"]) == 1
    assert len(thread["disputes"]) == 1
    assert len(thread["assignments"]) == 1
    assert thread["comments"][0]["author"]


def test_only_authorised_roles_manage_the_review_box():
    _, researcher = _make_user(UserRole.RESEARCHER)
    other_id, _other = _make_user(UserRole.RESEARCHER)
    c = client()
    claim_id = _claim(c, researcher, "بصر")

    assert (
        c.post(
            "/api/v1/review/assignments",
            json={
                "target_type": "claim",
                "target_id": claim_id,
                "reviewer_id": other_id,
            },
            headers=_auth(researcher),
        ).status_code
        == 403
    )
    assert (
        c.post(
            "/api/v1/review/disputes",
            json={
                "target_type": "claim",
                "target_id": claim_id,
                "reason": "اعتراض من دور غير مخوَّل بالمراجعة العلمية.",
            },
            headers=_auth(researcher),
        ).status_code
        == 403
    )
    assert c.get("/api/v1/review/disputes").status_code == 401
