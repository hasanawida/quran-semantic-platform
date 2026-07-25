"""سجل التدقيق ملحق-فقط: يُرفض التعديل والحذف."""

import asyncio

import pytest

from app.db.audit import AuditLogImmutableError, record_audit
from app.db.session import SessionFactory
from app.models.audit import AuditLog


def test_audit_insert_then_block_update_and_delete():
    async def _run():
        # إدراج قيد تدقيق
        async with SessionFactory() as session:
            entry = record_audit(
                session,
                action="test_action",
                entity_type="test_entity",
                reason="اختبار",
            )
            await session.commit()
            entry_id = entry.id

        # محاولة تعديل → مرفوضة
        async with SessionFactory() as session:
            obj = await session.get(AuditLog, entry_id)
            obj.reason = "محاولة تعديل"
            with pytest.raises(AuditLogImmutableError):
                await session.commit()

        # محاولة حذف → مرفوضة
        async with SessionFactory() as session:
            obj = await session.get(AuditLog, entry_id)
            await session.delete(obj)
            with pytest.raises(AuditLogImmutableError):
                await session.commit()

    asyncio.run(_run())
