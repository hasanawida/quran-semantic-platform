"""فرض مبدأ «سجل التدقيق ملحق-فقط» في طبقة ORM (portable عبر SQLite/Postgres).

يمنع أي UPDATE أو DELETE على صفوف AuditLog. في Postgres يُضاف محفّز قاعدة
بيانات كدفاع عميق (المرحلة J)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


class AuditLogImmutableError(Exception):
    pass


@event.listens_for(Session, "before_flush")
def _block_audit_mutations(session: Session, _flush_context, _instances) -> None:
    for obj in session.dirty:
        if isinstance(obj, AuditLog) and session.is_modified(obj):
            raise AuditLogImmutableError("سجل التدقيق ملحق-فقط: لا يسمح بالتعديل.")
    for obj in session.deleted:
        if isinstance(obj, AuditLog):
            raise AuditLogImmutableError("سجل التدقيق ملحق-فقط: لا يسمح بالحذف.")


def record_audit(
    session: Any,
    *,
    action: str,
    entity_type: str,
    entity_id: str | uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    old_data: dict | None = None,
    new_data: dict | None = None,
    reason: str | None = None,
    request_id: str | None = None,
) -> AuditLog:
    """يضيف قيد تدقيق إلى الجلسة (يُحفظ ضمن معاملة الاستدعاء)."""
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        actor_id=actor_id,
        old_data=old_data,
        new_data=new_data,
        reason=reason,
        request_id=request_id,
    )
    session.add(entry)
    return entry
