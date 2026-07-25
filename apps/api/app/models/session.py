"""جلسات التجديد — تدوير الرموز وإبطالها (المقترح 17).

المشكلة التي يحلها: رمز التجديد صالح أسبوعين ولا يمكن إبطاله. من سرقه
ملك الحساب طوال المدة، ولا يملك المستخدم ولا المدير قطعه.

الحل بثلاثة أجزاء:

  1. **تدوير:** كل استعمال يُصدر رمزًا جديدًا ويُبطل السابق فورًا.
  2. **كشف إعادة الاستعمال:** استعمال رمز مُبطل مؤشر سرقة — تُبطل
     **السلسلة كلها** ويُسجَّل الحدث في سجل التدقيق.
  3. **إنهاء الجلسات:** إبطال كل جلسات المستخدم بأمر واحد.

الرمز نفسه لا يُخزَّن — يُخزَّن معرّفه (`jti`) فقط، فتسريب قاعدة البيانات
لا يعطي رموزًا صالحة.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class RefreshSession(UUIDMixin, TimestampMixin, Base):
    """جلسة تجديد واحدة. السلسلة تربط الرموز المتعاقبة لجلسة واحدة."""

    __tablename__ = "refresh_sessions"
    __table_args__ = (
        Index("ix_refresh_sessions_chain", "chain_id"),
        Index("ix_refresh_sessions_user_active", "user_id", "revoked_at"),
    )

    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # كل تدوير يبقى في السلسلة نفسها، فيمكن إبطالها كاملة عند كشف سرقة
    chain_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    replaced_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(200), nullable=True)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None
