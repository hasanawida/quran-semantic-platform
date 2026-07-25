"""اعتماديات المصادقة والتحكم بالصلاحيات (RBAC) في طبقة الخدمة.

الوثيقة (قسم 18): يعاد التحقق من الأدوار في الخدمة الخلفية، ولا يعتمد النظام
على إخفاء أزرار الواجهة.
"""

from __future__ import annotations

import uuid

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_session
from app.models.user import User
from app.services.auth import AuthService

# auto_error=False حتى نعيد خطأنا الموحد بدل خطأ FastAPI الافتراضي
_bearer = HTTPBearer(auto_error=False)


class AuthHTTPError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


async def get_current_user(
    request: Request,
    credentials=Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None:
        raise AuthHTTPError(401, "NOT_AUTHENTICATED", "المصادقة مطلوبة.")
    try:
        payload = decode_token(credentials.credentials, "access")
    except jwt.ExpiredSignatureError:
        raise AuthHTTPError(401, "TOKEN_EXPIRED", "انتهت صلاحية الرمز.") from None
    except jwt.InvalidTokenError:
        raise AuthHTTPError(401, "INVALID_TOKEN", "رمز غير صالح.") from None

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise AuthHTTPError(401, "INVALID_TOKEN", "رمز غير صالح.") from None

    user = await AuthService(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise AuthHTTPError(401, "USER_INACTIVE", "الحساب غير متاح.")
    return user


def require_roles(*roles: str):
    """يتحقق أن للمستخدم الحالي أحد الأدوار المطلوبة على الأقل."""

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if roles and not (user.role_values & set(roles)):
            raise AuthHTTPError(
                403,
                "FORBIDDEN",
                "لا تملك صلاحية تنفيذ هذا الإجراء.",
            )
        return user

    return _checker
