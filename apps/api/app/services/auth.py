from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password, verify_password
from app.db.audit import record_audit
from app.models.enums import UserRole
from app.models.user import User, UserRoleAssignment


class AuthError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def register(
        self, email: str, display_name: str, password: str
    ) -> User:
        email = email.lower()
        if await self.get_by_email(email):
            raise AuthError("EMAIL_TAKEN", "البريد مستخدم بالفعل.")
        user = User(
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
            is_active=True,
        )
        # الدور الأساسي للمستخدم المسجَّل: باحث. الأدوار الأعلى يمنحها المدير.
        user.roles.append(UserRoleAssignment(role=UserRole.RESEARCHER))
        self.session.add(user)
        await self.session.flush()
        record_audit(
            self.session,
            action="user_register",
            entity_type="user",
            entity_id=user.id,
            actor_id=user.id,
            new_data={"email": email, "roles": ["researcher"]},
        )
        await self.session.commit()
        await self.session.refresh(user, ["roles"])
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.get_by_email(email)
        # تحقق ثابت الزمن نسبيًا: نتحقق دائمًا لتفادي كشف وجود البريد
        stored = user.password_hash if user else (
            "scrypt$16384$8$1$" + "A" * 24 + "$" + "A" * 43
        )
        ok = verify_password(password, stored)
        if not user or not ok:
            raise AuthError("INVALID_CREDENTIALS", "بريد أو كلمة مرور غير صحيحة.")
        if not user.is_active:
            raise AuthError("USER_INACTIVE", "الحساب معطّل.")
        return user

    async def grant_role(
        self, target: User, role: UserRole, actor_id: uuid.UUID
    ) -> None:
        if role.value in target.role_values:
            return
        target.roles.append(UserRoleAssignment(role=role))
        record_audit(
            self.session,
            action="role_grant",
            entity_type="user",
            entity_id=target.id,
            actor_id=actor_id,
            new_data={"role": role.value},
        )
        await self.session.commit()
