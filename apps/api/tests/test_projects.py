"""اختبارات المرحلة F — المشاريع والتقارير ذات الإصدارات.

تثبت: خصوصية المشروع مفروضة خلفيًا، ولا يُنشر تقرير بلا ادعاء معتمد،
والنسخة المنشورة لقطة مبصومة لا تتغير بتغير الادعاءات بعدها.
"""

import asyncio
import json
import uuid

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import SessionFactory
from app.main import app
from app.models.enums import UserRole
from app.models.user import User, UserRoleAssignment


def client() -> TestClient:
    return TestClient(app)


def _make_user(*roles: UserRole, password: str = "projectpass1") -> tuple[str, str]:
    email = f"p{uuid.uuid4().hex[:8]}@example.com"

    async def _create():
        async with SessionFactory() as session:
            user = User(
                email=email,
                display_name="عضو",
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


def _approved_claim(c: TestClient, author_token: str, root: str) -> str:
    """ينشئ ادعاءً معتمدًا كاملًا: مصدر متحقَّق ← استشهاد ← رفع ← مراجعان."""
    _, verifier = _make_user(UserRole.QUALITY_MANAGER)
    _, reviewer_one = _make_user(UserRole.LINGUISTIC_REVIEWER)
    _, reviewer_two = _make_user(UserRole.SHARIA_REVIEWER)

    source = c.post(
        "/api/v1/sources",
        json={
            "code": f"src-{uuid.uuid4().hex[:8]}",
            "title": "معجم مقاييس اللغة",
            "author": "ابن فارس",
            "work_type": "dictionary",
            "edition": "دار الفكر، 1399هـ",
            "license_note": "نسخة مطبوعة، النقل بالاستشهاد المحدود",
        },
        headers=_auth(author_token),
    ).json()["data"]["id"]
    c.post(f"/api/v1/sources/{source}/verify", headers=_auth(verifier))

    citation = c.post(
        "/api/v1/citations",
        json={
            "source_work_id": source,
            "locator": "3/104",
            "paraphrase": "أصل المادة يدل على معنى جامع.",
        },
        headers=_auth(author_token),
    ).json()["data"]["id"]

    claim_id = c.post(
        "/api/v1/claims",
        json={
            "statement": f"دعوى دلالية موثقة عن الجذر {root} لأغراض اختبار التقارير.",
            "subject_type": "root",
            "root": root,
        },
        headers=_auth(author_token),
    ).json()["data"]["id"]
    c.post(
        f"/api/v1/claims/{claim_id}/evidence",
        json={"citation_id": citation, "stance": "supports"},
        headers=_auth(author_token),
    )
    c.post(f"/api/v1/claims/{claim_id}/submit", headers=_auth(author_token))
    c.post(f"/api/v1/claims/{claim_id}/approve", headers=_auth(reviewer_one))
    approved = c.post(f"/api/v1/claims/{claim_id}/approve", headers=_auth(reviewer_two))
    assert approved.json()["data"]["status"] == "approved", approved.text
    return claim_id


def test_private_project_is_invisible_to_strangers():
    _, owner = _make_user(UserRole.RESEARCHER)
    _, stranger = _make_user(UserRole.RESEARCHER)
    c = client()
    project_id = c.post(
        "/api/v1/projects",
        json={"title": "مشروع خاص", "visibility": "private"},
        headers=_auth(owner),
    ).json()["data"]["id"]

    assert c.get(f"/api/v1/projects/{project_id}", headers=_auth(owner)).status_code == 200
    blocked = c.get(f"/api/v1/projects/{project_id}", headers=_auth(stranger))
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "PROJECT_FORBIDDEN"

    listed = c.get("/api/v1/projects", headers=_auth(stranger)).json()["data"]
    assert project_id not in {p["id"] for p in listed}

    assert c.get(f"/api/v1/projects/{project_id}").status_code == 401


def test_member_gains_access_and_editor_can_add_claims():
    _, owner = _make_user(UserRole.RESEARCHER)
    member_id, member = _make_user(UserRole.RESEARCHER)
    c = client()
    project_id = c.post(
        "/api/v1/projects",
        json={"title": "مشروع بأعضاء", "visibility": "private"},
        headers=_auth(owner),
    ).json()["data"]["id"]

    assert c.get(f"/api/v1/projects/{project_id}", headers=_auth(member)).status_code == 403
    added = c.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": member_id, "role": "editor"},
        headers=_auth(owner),
    )
    assert added.status_code == 200
    assert c.get(f"/api/v1/projects/{project_id}", headers=_auth(member)).status_code == 200

    claim_id = _approved_claim(c, owner, "حمد")
    linked = c.post(
        f"/api/v1/projects/{project_id}/claims",
        json={"claim_id": claim_id},
        headers=_auth(member),
    )
    assert linked.status_code == 200
    assert claim_id in {item["claim_id"] for item in linked.json()["data"]["claims"]}


def test_viewer_cannot_edit_and_non_owner_cannot_manage_members():
    _, owner = _make_user(UserRole.RESEARCHER)
    viewer_id, viewer = _make_user(UserRole.RESEARCHER)
    outsider_id, _outsider = _make_user(UserRole.RESEARCHER)
    c = client()
    project_id = c.post(
        "/api/v1/projects", json={"title": "مشروع قراءة"}, headers=_auth(owner)
    ).json()["data"]["id"]
    c.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": viewer_id, "role": "viewer"},
        headers=_auth(owner),
    )
    claim_id = _approved_claim(c, owner, "علم")

    blocked = c.post(
        f"/api/v1/projects/{project_id}/claims",
        json={"claim_id": claim_id},
        headers=_auth(viewer),
    )
    assert blocked.status_code == 403

    member_attempt = c.post(
        f"/api/v1/projects/{project_id}/members",
        json={"user_id": outsider_id, "role": "editor"},
        headers=_auth(viewer),
    )
    assert member_attempt.status_code == 403


def test_report_cannot_publish_without_approved_claims():
    _, owner = _make_user(UserRole.RESEARCHER)
    c = client()
    project_id = c.post(
        "/api/v1/projects", json={"title": "مشروع بلا نتائج"}, headers=_auth(owner)
    ).json()["data"]["id"]
    report_id = c.post(
        f"/api/v1/projects/{project_id}/reports",
        json={"title": "تقرير مبكر"},
        headers=_auth(owner),
    ).json()["data"]["id"]

    # ادعاء مسودة غير معتمد
    draft_claim = c.post(
        "/api/v1/claims",
        json={
            "statement": "مسودة ادعاء غير معتمدة لا يجوز أن تدخل تقريرًا منشورًا.",
            "subject_type": "root",
            "root": "كتب",
        },
        headers=_auth(owner),
    ).json()["data"]["id"]
    c.post(
        f"/api/v1/projects/{project_id}/claims",
        json={"claim_id": draft_claim},
        headers=_auth(owner),
    )

    blocked = c.post(f"/api/v1/reports/{report_id}/publish", headers=_auth(owner))
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "NO_APPROVED_CLAIMS"


def test_published_version_is_an_immutable_hashed_snapshot():
    _, owner = _make_user(UserRole.RESEARCHER)
    c = client()
    project_id = c.post(
        "/api/v1/projects", json={"title": "مشروع تقرير"}, headers=_auth(owner)
    ).json()["data"]["id"]
    first_claim = _approved_claim(c, owner, "نور")
    c.post(
        f"/api/v1/projects/{project_id}/claims",
        json={"claim_id": first_claim},
        headers=_auth(owner),
    )
    report_id = c.post(
        f"/api/v1/projects/{project_id}/reports",
        json={"title": "تقرير الجذور الدلالية"},
        headers=_auth(owner),
    ).json()["data"]["id"]

    published = c.post(
        f"/api/v1/reports/{report_id}/publish",
        json={"change_note": "النشر الأول"},
        headers=_auth(owner),
    )
    assert published.status_code == 200, published.text
    versions = published.json()["data"]["versions"]
    assert len(versions) == 1
    v1 = versions[0]
    assert v1["version_number"] == 1
    assert len(v1["content_hash"]) == 64
    assert v1["claim_count"] == 1
    assert v1["supersedes_id"] is None

    # إعادة النشر بلا تغيير مرفوضة
    unchanged = c.post(f"/api/v1/reports/{report_id}/publish", headers=_auth(owner))
    assert unchanged.status_code == 409
    assert unchanged.json()["error"]["code"] == "NO_CHANGES"

    # ادعاء معتمد آخر ينتج نسخة ثانية تشير إلى الأولى
    second_claim = _approved_claim(c, owner, "رحم")
    c.post(
        f"/api/v1/projects/{project_id}/claims",
        json={"claim_id": second_claim},
        headers=_auth(owner),
    )
    second = c.post(
        f"/api/v1/reports/{report_id}/publish",
        json={"change_note": "إضافة دعوى ثانية"},
        headers=_auth(owner),
    )
    assert second.status_code == 200
    versions = second.json()["data"]["versions"]
    assert len(versions) == 2
    v2 = versions[1]
    assert v2["version_number"] == 2
    assert v2["supersedes_id"] == v1["id"]
    assert v2["content_hash"] != v1["content_hash"]

    # اللقطة الأولى لم تتغير: بصمتها متحققة ومحتواها ادعاء واحد
    snapshot = c.get(f"/api/v1/report-versions/{v1['id']}", headers=_auth(owner))
    assert snapshot.status_code == 200
    data = snapshot.json()["data"]
    assert data["hash_verified"] is True
    assert len(data["snapshot"]["claims"]) == 1
    assert data["snapshot"]["claims"][0]["id"] == first_claim
    assert "لا تتغير" in data["notice"]


def test_report_version_snapshot_is_json_and_self_contained():
    _, owner = _make_user(UserRole.RESEARCHER)
    c = client()
    project_id = c.post(
        "/api/v1/projects", json={"title": "مشروع لقطة"}, headers=_auth(owner)
    ).json()["data"]["id"]
    claim_id = _approved_claim(c, owner, "صبر")
    c.post(
        f"/api/v1/projects/{project_id}/claims",
        json={"claim_id": claim_id},
        headers=_auth(owner),
    )
    report_id = c.post(
        f"/api/v1/projects/{project_id}/reports",
        json={"title": "تقرير مستقل"},
        headers=_auth(owner),
    ).json()["data"]["id"]
    version_id = c.post(
        f"/api/v1/reports/{report_id}/publish", headers=_auth(owner)
    ).json()["data"]["versions"][0]["id"]

    data = c.get(
        f"/api/v1/report-versions/{version_id}", headers=_auth(owner)
    ).json()["data"]
    snapshot = data["snapshot"]
    # اللقطة تحمل نص الادعاء وأدلته ومصادرها بلا رجوع لجداول حية
    claim = snapshot["claims"][0]
    assert claim["statement"]
    assert claim["evidence"][0]["source"]["edition"]
    assert json.dumps(snapshot, ensure_ascii=False)


def test_oversight_role_can_read_any_project():
    _, owner = _make_user(UserRole.RESEARCHER)
    _, auditor = _make_user(UserRole.QUALITY_MANAGER)
    c = client()
    project_id = c.post(
        "/api/v1/projects",
        json={"title": "مشروع تحت الرقابة", "visibility": "private"},
        headers=_auth(owner),
    ).json()["data"]["id"]
    assert (
        c.get(f"/api/v1/projects/{project_id}", headers=_auth(auditor)).status_code
        == 200
    )
