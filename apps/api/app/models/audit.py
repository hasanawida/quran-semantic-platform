import uuid

from sqlalchemy import JSON, BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# BIGINT في Postgres، INTEGER في SQLite (شرط عمل التزايد التلقائي في SQLite)
AuditPK = BigInteger().with_variant(Integer, "sqlite")


class AuditLog(TimestampMixin, Base):
    """سجل تدقيق ملحق-فقط (قسم 18). يمنع تعديله وحذفه عبر أحداث ORM
    (portable) وعبر محفّز قاعدة بيانات في Postgres (دفاع عميق، المرحلة J)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(AuditPK, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    old_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
