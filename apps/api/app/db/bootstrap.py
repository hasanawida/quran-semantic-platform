"""حسابات تجريبية للتطوير فقط — تُنشأ عند الإقلاع في بيئة التطوير إن لم توجد.

تتيح تجربة سير المراجعة المزدوجة فورًا (مدير + مراجعان مستقلان).
لا تُنشأ إطلاقًا في بيئة الإنتاج.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionFactory
from app.models.enums import UserRole
from app.models.user import User, UserRoleAssignment

settings = get_settings()

DEV_PASSWORD = "demopass123"

# النطاق ‎.example‎ محجوز قياسيًا (RFC 2606) فلا يوجد على الإنترنت.
# ملاحظتان يفرضهما تحقق البريد في مخطط تسجيل الدخول، وإلا صارت الحسابات
# التجريبية غير قابلة للاستعمال (‎422‎) دون أن يكشف ذلك اختبار:
#   1) النطاق بلا نقطة مرفوض (admin@local).
#   2) النطاقات الخاصة ‎.test/.local/.localhost/.invalid‎ مرفوضة كذلك.
DEV_USERS = [
    (
        "admin@qsp.example",
        "المدير التقني",
        [UserRole.TECH_ADMIN, UserRole.TEXT_OFFICER],
    ),
    ("reviewer1@qsp.example", "المراجع الأول", [UserRole.QUALITY_MANAGER]),
    ("reviewer2@qsp.example", "المراجع الثاني", [UserRole.LINGUISTIC_REVIEWER]),
    ("sharia@qsp.example", "المراجع الشرعي", [UserRole.SHARIA_REVIEWER]),
]


async def bootstrap_dev_users() -> None:
    if settings.is_production:
        return
    async with SessionFactory() as session:
        existing = await session.scalar(select(User.id).limit(1))
        if existing is not None:
            return
        for email, name, roles in DEV_USERS:
            user = User(
                email=email,
                display_name=name,
                password_hash=hash_password(DEV_PASSWORD),
                is_active=True,
            )
            for role in roles:
                user.roles.append(UserRoleAssignment(role=role))
            session.add(user)
        await session.commit()
