"""خدمة جلسات التجديد: تدوير، وكشف إعادة استعمال، وإنهاء الجلسات.

القاعدة الحاكمة: **رمز التجديد يُستعمل مرة واحدة.** استعماله مرتين ليس
خطأ عابرًا — هو إمّا سرقة وإمّا خلل في العميل، وكلاهما يوجب قطع السلسلة
لا تجاهلها. الاحتياط هنا مقصود: قطع جلسة مستخدم صادق أهون من إبقاء جلسة
سارق مفتوحة.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.audit import record_audit
from app.db.base import utcnow
from app.models.session import RefreshSession

settings = get_settings()


def _as_utc(value: datetime) -> datetime:
    """SQLite يعيد الأزمنة بلا منطقة زمنية؛ تُعامَل UTC عند المقارنة.

    بدون هذا تنفجر المقارنة بـ«offset-naive vs offset-aware» في التطوير
    وتعمل في Postgres — وهو أسوأ أنواع الأخطاء: يظهر في بيئة دون أخرى."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class SessionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


class RefreshSessionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def open(
        self,
        user_id: uuid.UUID,
        jti: str,
        chain_id: uuid.UUID | None = None,
        user_agent: str | None = None,
    ) -> RefreshSession:
        """يفتح جلسة جديدة (تسجيل دخول) أو حلقة جديدة في سلسلة قائمة."""
        record = RefreshSession(
            jti=jti,
            user_id=user_id,
            chain_id=chain_id or uuid.uuid4(),
            expires_at=utcnow()
            + timedelta(days=settings.refresh_token_ttl_days),
            user_agent=(user_agent or None),
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def rotate(
        self, jti: str, user_id: uuid.UUID, new_jti: str, user_agent: str | None
    ) -> RefreshSession:
        """يستبدل رمزًا برمز جديد في السلسلة نفسها.

        يرمي `TOKEN_REUSED` عند استعمال رمز مُبطل — وقد أُبطلت السلسلة
        كلها قبل رمي الخطأ."""
        record = await self.session.scalar(
            select(RefreshSession).where(RefreshSession.jti == jti)
        )
        if record is None:
            # رمز موقَّع صحيحًا لكن لا جلسة له: أُبطلت سلسلته أو حُذفت
            raise SessionError(
                "SESSION_NOT_FOUND", "الجلسة غير معروفة أو أُنهيت."
            )
        if record.user_id != user_id:
            raise SessionError("SESSION_MISMATCH", "الجلسة لا تعود لهذا الحساب.")

        if record.revoked_at is not None:
            # **كشف إعادة استعمال:** الرمز مُبطل ومع ذلك استُعمل.
            await self.revoke_chain(
                record.chain_id, reason="reuse_detected", actor_id=user_id
            )
            await self.session.commit()
            raise SessionError(
                "TOKEN_REUSED",
                "استُعمل رمز تجديد مُبطل. أُنهيت الجلسة كلها احتياطًا؛ "
                "سجّل الدخول من جديد.",
            )

        if _as_utc(record.expires_at) <= utcnow():
            record.revoked_at = utcnow()
            record.revoked_reason = "expired"
            await self.session.commit()
            raise SessionError("SESSION_EXPIRED", "انتهت صلاحية الجلسة.")

        record.revoked_at = utcnow()
        record.revoked_reason = "rotated"
        record.replaced_by = new_jti
        return await self.open(
            user_id, new_jti, chain_id=record.chain_id, user_agent=user_agent
        )

    async def revoke_chain(
        self,
        chain_id: uuid.UUID,
        reason: str,
        actor_id: uuid.UUID | None = None,
    ) -> int:
        result = await self.session.execute(
            update(RefreshSession)
            .where(
                RefreshSession.chain_id == chain_id,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=utcnow(), revoked_reason=reason)
        )
        record_audit(
            self.session,
            action="refresh_chain_revoke",
            entity_type="refresh_session",
            entity_id=chain_id,
            actor_id=actor_id,
            new_data={"reason": reason, "revoked": result.rowcount},
            reason=reason,
        )
        return result.rowcount or 0

    async def revoke_all_for_user(
        self, user_id: uuid.UUID, reason: str = "user_logout_all"
    ) -> int:
        """إنهاء كل جلسات المستخدم — «تسجيل الخروج من كل الأجهزة»."""
        result = await self.session.execute(
            update(RefreshSession)
            .where(
                RefreshSession.user_id == user_id,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=utcnow(), revoked_reason=reason)
        )
        record_audit(
            self.session,
            action="refresh_sessions_revoke_all",
            entity_type="user",
            entity_id=user_id,
            actor_id=user_id,
            new_data={"reason": reason, "revoked": result.rowcount},
        )
        await self.session.commit()
        return result.rowcount or 0

    async def list_active(self, user_id: uuid.UUID) -> list[dict]:
        rows = (
            await self.session.execute(
                select(RefreshSession)
                .where(
                    RefreshSession.user_id == user_id,
                    RefreshSession.revoked_at.is_(None),
                )
                .order_by(RefreshSession.created_at.desc())
            )
        ).scalars()
        return [
            {
                "chain_id": str(row.chain_id),
                "created_at": row.created_at.isoformat(),
                "expires_at": row.expires_at.isoformat(),
                "user_agent": row.user_agent,
            }
            for row in rows
        ]
