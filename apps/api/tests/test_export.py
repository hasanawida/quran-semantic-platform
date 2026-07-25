"""اختبارات المرحلة H — التصدير وبيان الأصول.

تثبت: لا مخرَج بلا نسب، والبيان يحمل بصمات المصادر وحالة المراجعة،
والتصدير يخضع لخصوصية المشروع نفسها.
"""

import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import SessionFactory
from app.main import app
from app.models.enums import UserRole
from app.models.user import User, UserRoleAssignment
from app.services.export import EXPORT_NOTICE
from app.services.morphology import MorphologyService, load_morphology_bundle


def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def registered_morphology_source():
    """يسجّل المصدر الصرفي وحده (بلا استيراد تحليل) حتى يبقى بيان الأصول
    قابلًا للاختبار مستقلًا عن ترتيب وحدات الاختبار."""

    async def _register():
        bundle = load_morphology_bundle()
        async with SessionFactory() as session:
            await MorphologyService(session).upsert_source(bundle["meta"])
            await session.commit()

    asyncio.run(_register())
    yield


def _make_user(*roles: UserRole, password: str = "exportpass1") -> tuple[str, str]:
    email = f"x{uuid.uuid4().hex[:8]}@example.com"

    async def _create():
        async with SessionFactory() as session:
            user = User(
                email=email,
                display_name="مصدِّر",
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


def _published_report(c: TestClient, owner_token: str) -> str:
    _, verifier = _make_user(UserRole.QUALITY_MANAGER)
    _, reviewer_one = _make_user(UserRole.LINGUISTIC_REVIEWER)
    _, reviewer_two = _make_user(UserRole.SHARIA_REVIEWER)
    source = c.post(
        "/api/v1/sources",
        json={
            "code": f"src-{uuid.uuid4().hex[:8]}",
            "title": "المفردات في غريب القرآن",
            "author": "الراغب الأصفهاني",
            "work_type": "dictionary",
            "edition": "دار القلم، ط1 1412هـ",
            "license_note": "نسخة مطبوعة، النقل بالاستشهاد المحدود",
        },
        headers=_auth(owner_token),
    ).json()["data"]["id"]
    c.post(f"/api/v1/sources/{source}/verify", headers=_auth(verifier))
    citation = c.post(
        "/api/v1/citations",
        json={"source_work_id": source, "locator": "ص 414", "paraphrase": "تلخيص."},
        headers=_auth(owner_token),
    ).json()["data"]["id"]
    claim_id = c.post(
        "/api/v1/claims",
        json={
            "statement": "دعوى دلالية موثقة تُصدَّر ضمن تقرير لاختبار بيان الأصول.",
            "subject_type": "root",
            "root": "فرق",
        },
        headers=_auth(owner_token),
    ).json()["data"]["id"]
    c.post(
        f"/api/v1/claims/{claim_id}/evidence",
        json={"citation_id": citation, "stance": "supports"},
        headers=_auth(owner_token),
    )
    c.post(f"/api/v1/claims/{claim_id}/submit", headers=_auth(owner_token))
    c.post(f"/api/v1/claims/{claim_id}/approve", headers=_auth(reviewer_one))
    c.post(f"/api/v1/claims/{claim_id}/approve", headers=_auth(reviewer_two))

    project_id = c.post(
        "/api/v1/projects", json={"title": "مشروع تصدير"}, headers=_auth(owner_token)
    ).json()["data"]["id"]
    c.post(
        f"/api/v1/projects/{project_id}/claims",
        json={"claim_id": claim_id},
        headers=_auth(owner_token),
    )
    report_id = c.post(
        f"/api/v1/projects/{project_id}/reports",
        json={"title": "تقرير قابل للتصدير"},
        headers=_auth(owner_token),
    ).json()["data"]["id"]
    published = c.post(
        f"/api/v1/reports/{report_id}/publish", headers=_auth(owner_token)
    )
    return published.json()["data"]["versions"][0]["id"]


def test_provenance_is_public_and_complete():
    body = client().get("/api/v1/export/provenance").json()
    assert body["success"] is True
    data = body["data"]
    assert data["text_version"]["version_code"]
    assert len(data["text_version"]["sha256"]) == 64
    assert data["counts"]["ayahs"] == 6236
    assert data["counts"]["surahs"] == 114
    assert data["notice"] == EXPORT_NOTICE
    # المصدر الصرفي مذكور برخصته وبصمة ملفه
    codes = {s["code"] for s in data["morphology_sources"]}
    assert "qac-0.4" in codes
    qac = next(s for s in data["morphology_sources"] if s["code"] == "qac-0.4")
    assert qac["license"]
    assert len(qac["file_sha256"]) == 64
    # الاشتقاق مبيَّن لا مخفي
    assert sum(data["occurrences_by_derivation"].values()) == data["counts"][
        "root_occurrences"
    ]


def test_root_export_carries_provenance_and_its_own_hash():
    body = client().get("/api/v1/export/roots/ع ص ر").json()["data"]
    assert body["kind"] == "root_occurrences"
    assert body["root"]["normalized"] == "عصر"
    assert body["root"]["status"] == "imported"
    assert body["occurrence_count"] == 5
    assert len(body["export_sha256"]) == 64
    assert body["provenance"]["notice"] == EXPORT_NOTICE
    # كل موضع يحمل كيفية اشتقاقه
    assert all(occurrence["derivation"] for occurrence in body["occurrences"])


def test_root_csv_export_keeps_the_notice_inside_the_file():
    response = client().get("/api/v1/export/roots/ع ص ر/csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    text = response.text
    assert "# تنبيه:" in text
    assert "surah_number,surah_name,ayah_number" in text
    assert text.count("\n") >= 6


def test_unknown_root_export_is_404():
    response = client().get("/api/v1/export/roots/زخذف")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ROOT_NOT_FOUND"


def test_report_export_json_and_markdown_include_sources_and_notice():
    _, owner = _make_user(UserRole.RESEARCHER)
    c = client()
    version_id = _published_report(c, owner)

    payload = c.get(
        f"/api/v1/export/report-versions/{version_id}", headers=_auth(owner)
    )
    assert payload.status_code == 200, payload.text
    data = payload.json()["data"]
    assert data["kind"] == "report_version"
    assert len(data["export_sha256"]) == 64
    assert data["provenance"]["text_version"]["sha256"]
    assert data["snapshot"]["claims"]

    markdown = c.get(
        f"/api/v1/export/report-versions/{version_id}/markdown", headers=_auth(owner)
    )
    assert markdown.status_code == 200
    assert "text/markdown" in markdown.headers["content-type"]
    text = markdown.text
    assert "## بيان الأصول" in text
    assert "الراغب الأصفهاني" in text
    assert EXPORT_NOTICE in text
    assert "بصمة هذا المخرَج" in text


def test_report_export_respects_project_privacy():
    _, owner = _make_user(UserRole.RESEARCHER)
    _, stranger = _make_user(UserRole.RESEARCHER)
    c = client()
    version_id = _published_report(c, owner)

    assert (
        c.get(
            f"/api/v1/export/report-versions/{version_id}", headers=_auth(stranger)
        ).status_code
        == 403
    )
    assert c.get(f"/api/v1/export/report-versions/{version_id}").status_code == 401
