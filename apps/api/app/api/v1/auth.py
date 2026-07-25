from __future__ import annotations

import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.api.response import ok
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.db.session import get_session
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import (
    GrantRoleRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
)
from app.services.auth import AuthError, AuthService
from app.services.sessions import RefreshSessionService, SessionError

router = APIRouter(tags=["Auth"])


def _tokens(user: User) -> dict:
    """يصدر زوج الرموز ويعيد معرّف رمز التجديد ليُسجَّل جلسةً."""
    roles = sorted(user.role_values)
    refresh = create_refresh_token(user.id)
    return {
        "access_token": create_access_token(user.id, roles),
        "refresh_token": refresh,
        "token_type": "bearer",
        "_refresh_jti": decode_token(refresh, "refresh")["jti"],
    }


async def _issue(
    user: User, session: AsyncSession, request: Request, chain_id=None
) -> dict:
    """يصدر الرموز ويفتح جلسة تجديد مرتبطة بها."""
    tokens = _tokens(user)
    jti = tokens.pop("_refresh_jti")
    await RefreshSessionService(session).open(
        user.id,
        jti,
        chain_id=chain_id,
        user_agent=request.headers.get("user-agent", "")[:200] or None,
    )
    await session.commit()
    return tokens


def _session_error(exc: SessionError) -> HTTPException:
    # كشف إعادة الاستعمال يُبلَّغ 401 لا 409: العميل يجب أن يعيد الدخول
    return HTTPException(
        status_code=401, detail={"code": exc.code, "message": exc.message}
    )


def _user_out(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "roles": sorted(user.role_values),
    }


def _auth_error(exc: AuthError) -> HTTPException:
    status = 409 if exc.code == "EMAIL_TAKEN" else 401
    return HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message})


@router.post("/auth/register")
async def register(
    request: Request,
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        user = await AuthService(session).register(
            body.email, body.display_name, body.password
        )
    except AuthError as exc:
        raise _auth_error(exc) from None
    return ok(
        request,
        {"user": _user_out(user), **(await _issue(user, session, request))},
    )


@router.post("/auth/login")
async def login(
    request: Request,
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        user = await AuthService(session).authenticate(body.email, body.password)
    except AuthError as exc:
        raise _auth_error(exc) from None
    return ok(
        request,
        {"user": _user_out(user), **(await _issue(user, session, request))},
    )


@router.post("/auth/refresh")
async def refresh(
    request: Request,
    body: RefreshRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        payload = decode_token(body.refresh_token, "refresh")
        user_id = uuid.UUID(payload["sub"])
        jti = payload["jti"]
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_TOKEN", "message": "رمز تحديث غير صالح."},
        ) from None
    user = await AuthService(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail={"code": "USER_INACTIVE", "message": "الحساب غير متاح."},
        )

    # التدوير: الرمز يُستعمل مرة واحدة، ويُبطل فور إصدار خلفه
    tokens = _tokens(user)
    new_jti = tokens.pop("_refresh_jti")
    try:
        await RefreshSessionService(session).rotate(
            jti,
            user.id,
            new_jti,
            request.headers.get("user-agent", "")[:200] or None,
        )
    except SessionError as exc:
        raise _session_error(exc) from None
    await session.commit()
    return ok(request, tokens)


@router.get("/auth/sessions")
async def list_sessions(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """الجلسات المفتوحة لحساب المستخدم."""
    return ok(request, await RefreshSessionService(session).list_active(user.id))


@router.post("/auth/sessions/revoke-all")
async def revoke_all_sessions(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """إنهاء كل الجلسات — «الخروج من كل الأجهزة»."""
    revoked = await RefreshSessionService(session).revoke_all_for_user(user.id)
    return ok(request, {"revoked": revoked})


@router.get("/auth/me")
async def me(request: Request, user: User = Depends(get_current_user)):
    return ok(request, _user_out(user))


@router.post("/admin/users/{user_id}/roles")
async def grant_role(
    request: Request,
    user_id: uuid.UUID,
    body: GrantRoleRequest,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(require_roles(UserRole.TECH_ADMIN.value)),
):
    try:
        role = UserRole(body.role)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "دور غير معروف."},
        ) from None
    target = await AuthService(session).get_by_id(user_id)
    if target is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "USER_NOT_FOUND", "message": "المستخدم غير موجود."},
        )
    await AuthService(session).grant_role(target, role, actor.id)
    await session.refresh(target, ["roles"])
    return ok(request, _user_out(target))
