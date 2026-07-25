"""اختبارات آلة حالة إصدارات النص: الاعتماد المزدوج، منع الاعتماد الذاتي،
والتفعيل الذري لإصدار واحد."""

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


def _make_user(*roles: UserRole, password: str = "workerpass1") -> tuple[str, str]:
    email = f"v{uuid.uuid4().hex[:8]}@example.com"

    async def _create():
        async with SessionFactory() as session:
            user = User(
                email=email,
                display_name="عامل",
                password_hash=hash_password(password),
                is_active=True,
            )
            for r in roles:
                user.roles.append(UserRoleAssignment(role=r))
            session.add(user)
            await session.commit()

    asyncio.run(_create())
    c = client()
    token = c.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["data"]["access_token"]
    return email, token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _import_small(c: TestClient, token: str, code: str) -> str:
    body = {
        "version_code": code,
        "title": "إصدار اختبار",
        "riwayah": "حفص",
        "script_type": "عثماني",
        "counting_system": "كوفي",
        "source_name": "اختبار",
        "ayahs": [
            {"surah": 1, "ayah": 1, "text": "نص الآية الأولى"},
            {"surah": 1, "ayah": 2, "text": "نص الآية الثانية"},
        ],
    }
    resp = c.post("/api/v1/admin/quran-versions/import", json=body, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def test_import_requires_role():
    c = client()
    _, researcher = _make_user(UserRole.RESEARCHER)
    resp = c.post(
        "/api/v1/admin/quran-versions/import",
        json={
            "version_code": "x",
            "title": "t",
            "riwayah": "r",
            "script_type": "s",
            "counting_system": "c",
            "source_name": "n",
            "ayahs": [{"surah": 1, "ayah": 1, "text": "x"}],
        },
        headers=_auth(researcher),
    )
    assert resp.status_code == 403


def test_full_lifecycle_double_review_and_atomic_activation():
    c = client()
    _, officer = _make_user(UserRole.TEXT_OFFICER)
    _, rev1 = _make_user(UserRole.QUALITY_MANAGER)
    _, rev2 = _make_user(UserRole.LINGUISTIC_REVIEWER)

    vid = _import_small(c, officer, f"lifecycle-{uuid.uuid4().hex[:6]}")

    # لا يُعتمد قبل التحقق
    pre = c.post(f"/api/v1/admin/quran-versions/{vid}/approve", headers=_auth(rev1))
    assert pre.status_code == 409
    assert pre.json()["error"]["code"] == "NOT_VALIDATED"

    # تحقق (بنية صغيرة لا مصحف كامل)
    val = c.post(
        f"/api/v1/admin/quran-versions/{vid}/validate",
        json={"require_full": False},
        headers=_auth(officer),
    )
    assert val.status_code == 200
    assert val.json()["data"]["ok"] is True

    # اعتماد أول
    a1 = c.post(f"/api/v1/admin/quran-versions/{vid}/approve", headers=_auth(rev1))
    assert a1.json()["data"]["status"] == "imported"

    # المراجع نفسه لا يعتمد ثانية — منع الاعتماد الذاتي
    self_review = c.post(
        f"/api/v1/admin/quran-versions/{vid}/approve", headers=_auth(rev1)
    )
    assert self_review.status_code == 409
    assert self_review.json()["error"]["code"] == "SELF_REVIEW_FORBIDDEN"

    # لا يُفعَّل قبل الاعتماد الثاني
    early = c.post(
        f"/api/v1/admin/quran-versions/{vid}/activate",
        json={"reason": "تجربة"},
        headers=_auth(officer),
    )
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "SECOND_REVIEW_REQUIRED"

    # اعتماد ثانٍ مستقل
    a2 = c.post(f"/api/v1/admin/quran-versions/{vid}/approve", headers=_auth(rev2))
    assert a2.json()["data"]["status"] == "approved"

    # تفعيل بلا سبب مرفوض
    no_reason = c.post(
        f"/api/v1/admin/quran-versions/{vid}/activate",
        json={"reason": "  "},
        headers=_auth(officer),
    )
    assert no_reason.status_code == 422

    # تفعيل صحيح
    act = c.post(
        f"/api/v1/admin/quran-versions/{vid}/activate",
        json={"reason": "اجتاز المراجعة المزدوجة"},
        headers=_auth(officer),
    )
    assert act.status_code == 200
    assert act.json()["data"]["is_active"] is True

    # الإصدار الأصلي (المبذور) لم يعد نشطًا — إصدار نشط واحد فقط
    meta = c.get("/api/v1/meta").json()["data"]
    assert meta["data_release"].startswith("lifecycle-")

    # استعادة الإصدار المبذور نشطًا حتى لا تتأثر بقية الاختبارات
    async def _restore():
        from sqlalchemy import select, update

        from app.models.quran import QuranTextVersion

        async with SessionFactory() as session:
            await session.execute(update(QuranTextVersion).values(is_active=None))
            seeded = (
                await session.execute(
                    select(QuranTextVersion).where(
                        QuranTextVersion.version_code == "tanzil-uthmani-qac04"
                    )
                )
            ).scalar_one()
            seeded.is_active = True
            await session.commit()

    asyncio.run(_restore())


def test_compare_detects_differences():
    c = client()
    _, officer = _make_user(UserRole.TEXT_OFFICER)
    v1 = _import_small(c, officer, f"cmp-a-{uuid.uuid4().hex[:6]}")

    # إصدار ثانٍ باختلاف نصي وآية زائدة
    body = {
        "version_code": f"cmp-b-{uuid.uuid4().hex[:6]}",
        "title": "إصدار ب",
        "riwayah": "حفص",
        "script_type": "عثماني",
        "counting_system": "كوفي",
        "source_name": "اختبار",
        "ayahs": [
            {"surah": 1, "ayah": 1, "text": "نص مختلف"},
            {"surah": 1, "ayah": 2, "text": "نص الآية الثانية"},
            {"surah": 1, "ayah": 3, "text": "آية زائدة"},
        ],
    }
    v2 = c.post(
        "/api/v1/admin/quran-versions/import", json=body, headers=_auth(officer)
    ).json()["data"]["id"]

    result = c.post(
        f"/api/v1/admin/quran-versions/{v1}/compare",
        json={"other_version_id": v2},
        headers=_auth(officer),
    ).json()["data"]
    assert result["identical"] is False
    assert {"surah": 1, "ayah": 1} in result["text_differences"]
    assert {"surah": 1, "ayah": 3} in result["extra_in_b"]
