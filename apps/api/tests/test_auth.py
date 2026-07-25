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


def _register(c: TestClient, email: str, password: str = "strongpass1") -> dict:
    return c.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "باحث", "password": password},
    ).json()


def test_register_returns_tokens_and_researcher_role():
    c = client()
    body = _register(c, f"u{uuid.uuid4().hex[:8]}@example.com")
    assert body["success"] is True
    assert body["data"]["user"]["roles"] == ["researcher"]
    assert body["data"]["access_token"]
    assert body["data"]["refresh_token"]


def test_duplicate_email_conflict():
    c = client()
    email = f"dup{uuid.uuid4().hex[:8]}@example.com"
    _register(c, email)
    resp = c.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "آخر", "password": "strongpass1"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_TAKEN"


def test_login_success_and_failure():
    c = client()
    email = f"log{uuid.uuid4().hex[:8]}@example.com"
    _register(c, email, "mypassword9")
    good = c.post("/api/v1/auth/login", json={"email": email, "password": "mypassword9"})
    assert good.status_code == 200
    bad = c.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_me_requires_auth():
    c = client()
    assert c.get("/api/v1/auth/me").status_code == 401
    email = f"me{uuid.uuid4().hex[:8]}@example.com"
    token = _register(c, email)["data"]["access_token"]
    resp = c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == email


def test_refresh_issues_new_access_token():
    c = client()
    email = f"rf{uuid.uuid4().hex[:8]}@example.com"
    refresh = _register(c, email)["data"]["refresh_token"]
    resp = c.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"]
    # رمز الوصول لا يصلح للتحديث
    access = _register(c, f"rf2{uuid.uuid4().hex[:8]}@example.com")["data"]["access_token"]
    assert c.post("/api/v1/auth/refresh", json={"refresh_token": access}).status_code == 401


def test_weak_password_rejected():
    c = client()
    resp = c.post(
        "/api/v1/auth/register",
        json={"email": f"w{uuid.uuid4().hex[:8]}@example.com", "display_name": "x", "password": "short"},
    )
    assert resp.status_code == 422


def test_dev_bootstrap_accounts_can_actually_log_in():
    """الحسابات التجريبية يجب أن تجتاز تحقق البريد في مخطط تسجيل الدخول.

    بريد بنطاق بلا نقطة (admin@local) يُرفض بـ 422 فتصير الحسابات
    التجريبية غير قابلة للاستعمال دون أن يكشف ذلك أي اختبار."""
    from app.db.bootstrap import DEV_PASSWORD, DEV_USERS
    from app.schemas.auth import LoginRequest

    for email, _name, _roles in DEV_USERS:
        LoginRequest(email=email, password=DEV_PASSWORD)


def _make_admin(email: str, password: str = "adminpass1") -> uuid.UUID:
    async def _create():
        async with SessionFactory() as session:
            user = User(
                email=email,
                display_name="مدير",
                password_hash=hash_password(password),
                is_active=True,
            )
            user.roles.append(UserRoleAssignment(role=UserRole.TECH_ADMIN))
            session.add(user)
            await session.commit()
            return user.id

    return asyncio.run(_create())


def test_grant_role_requires_admin():
    c = client()
    # مستخدم عادي لا يملك منح الأدوار
    normal_email = f"n{uuid.uuid4().hex[:8]}@example.com"
    normal = _register(c, normal_email)
    normal_token = normal["data"]["access_token"]
    normal_id = normal["data"]["user"]["id"]
    resp = c.post(
        f"/api/v1/admin/users/{normal_id}/roles",
        json={"role": "linguistic_reviewer"},
        headers={"Authorization": f"Bearer {normal_token}"},
    )
    assert resp.status_code == 403

    # المدير يمنح الدور
    admin_email = f"a{uuid.uuid4().hex[:8]}@example.com"
    _make_admin(admin_email)
    admin_token = c.post(
        "/api/v1/auth/login", json={"email": admin_email, "password": "adminpass1"}
    ).json()["data"]["access_token"]
    granted = c.post(
        f"/api/v1/admin/users/{normal_id}/roles",
        json={"role": "linguistic_reviewer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert granted.status_code == 200
    assert "linguistic_reviewer" in granted.json()["data"]["roles"]


# ---- تدوير رموز التجديد وإبطالها (المقترح 17) --------------------------
def test_refresh_token_is_single_use_and_rotates():
    """الرمز يُستعمل مرة واحدة، ويُصدر خلفًا له في السلسلة نفسها."""
    c = client()
    email = f"rot{uuid.uuid4().hex[:8]}@example.com"
    first = _register(c, email)["data"]["refresh_token"]

    rotated = c.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert rotated.status_code == 200
    second = rotated.json()["data"]["refresh_token"]
    assert second != first

    # الرمز الجديد يعمل
    assert (
        c.post("/api/v1/auth/refresh", json={"refresh_token": second}).status_code
        == 200
    )


def test_reusing_a_rotated_token_kills_the_whole_chain():
    """إعادة استعمال رمز مُبطل مؤشر سرقة: تُقطع السلسلة كلها.

    الاحتياط مقصود — قطع جلسة مستخدم صادق أهون من إبقاء جلسة سارق."""
    c = client()
    email = f"reuse{uuid.uuid4().hex[:8]}@example.com"
    first = _register(c, email)["data"]["refresh_token"]
    second = c.post(
        "/api/v1/auth/refresh", json={"refresh_token": first}
    ).json()["data"]["refresh_token"]

    # استعمال الرمز القديم مرة ثانية
    replay = c.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "TOKEN_REUSED"

    # والرمز «السليم» الذي كان بيد المستخدم صار مبطلًا أيضًا
    after = c.post("/api/v1/auth/refresh", json={"refresh_token": second})
    assert after.status_code == 401
    assert after.json()["error"]["code"] in {"TOKEN_REUSED", "SESSION_NOT_FOUND"}


def test_user_can_list_and_end_all_sessions():
    c = client()
    email = f"sess{uuid.uuid4().hex[:8]}@example.com"
    registered = _register(c, email)["data"]
    access = registered["access_token"]
    refresh = registered["refresh_token"]
    headers = {"Authorization": f"Bearer {access}"}

    # جلسة ثانية بتسجيل دخول آخر
    c.post("/api/v1/auth/login", json={"email": email, "password": "strongpass1"})

    listed = c.get("/api/v1/auth/sessions", headers=headers).json()["data"]
    assert len(listed) >= 2
    assert all(item["chain_id"] and item["expires_at"] for item in listed)

    revoked = c.post("/api/v1/auth/sessions/revoke-all", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["data"]["revoked"] >= 2

    # لا يعمل أي رمز تجديد بعد الإنهاء
    dead = c.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert dead.status_code == 401
    assert c.get("/api/v1/auth/sessions", headers=headers).json()["data"] == []


def test_refresh_token_without_a_session_is_refused():
    """رمز موقَّع صحيحًا لكن بلا جلسة (أُنهيت أو لم تُفتح) لا يُقبل."""
    from app.core.security import create_refresh_token

    c = client()
    email = f"ghost{uuid.uuid4().hex[:8]}@example.com"
    user_id = _register(c, email)["data"]["user"]["id"]
    orphan = create_refresh_token(uuid.UUID(user_id))

    response = c.post("/api/v1/auth/refresh", json={"refresh_token": orphan})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"
