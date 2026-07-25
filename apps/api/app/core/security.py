"""أدوات الأمان: تجزئة كلمة المرور (scrypt من المكتبة القياسية) وJWT.

لا تعتمد على مكتبات تجزئة ثنائية خارجية (تفاديًا لمشاكل عجلات Python 3.14).
scrypt خوارزمية قوية مقاومة للعتاد، متوفرة في hashlib.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import get_settings

settings = get_settings()

# معاملات scrypt (توازن بين الأمان والأداء)
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 32


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text.encode("ascii"))


def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("كلمة المرور يجب ألا تقل عن 8 محارف.")
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_DKLEN,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64e(salt)}${_b64e(derived)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_b64d(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_b64d(hash_b64)),
        )
        return hmac.compare_digest(derived, _b64d(hash_b64))
    except (ValueError, TypeError):
        return False


def _encode(payload: dict[str, Any], ttl: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    body = {
        **payload,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(body, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID, roles: list[str]) -> str:
    return _encode(
        {"sub": str(user_id), "roles": roles},
        timedelta(minutes=settings.access_token_ttl_minutes),
        "access",
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    return _encode(
        {"sub": str(user_id)},
        timedelta(days=settings.refresh_token_ttl_days),
        "refresh",
    )


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """يفكّ الترميز ويتحقق من النوع والصلاحية. يرمي jwt.InvalidTokenError عند الفشل."""
    payload = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("نوع الرمز غير متوقع.")
    return payload
