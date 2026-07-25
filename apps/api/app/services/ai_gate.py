"""بوابة الذكاء الاصطناعي (المرحلة I).

خارطة التنفيذ صريحة: **لا تبدأ قبل اكتمال سلامة البيانات والمراجعة**،
وتقتصر على التلخيص والمقارنة ضمن مواد مسترجعة وموثقة.

لذلك لا توجد في المنصة أي ميزة ذكاء اصطناعي بعد — الموجود هنا **البوابة**:
فحص آلي للشروط المسبقة يُظهر بالضبط ما الذي ينقص قبل السماح بتشغيلها.
تشغيل أي ميزة قبل اجتياز الفحص ممنوع في الخدمة لا في الواجهة.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import RecordStatus
from app.models.morphology import GoldenRootCase, MorphologySource
from app.models.quran import QuranTextVersion
from app.models.review import Dispute, DisputeStatus
from app.models.scholarship import SourceWork
from app.services.morphology import MorphologyService

settings = get_settings()


class AIDisabledError(Exception):
    def __init__(self, unmet: list[dict]) -> None:
        self.code = "AI_DISABLED"
        self.message = (
            "ميزات الذكاء الاصطناعي معطَّلة: لم تكتمل شروط سلامة البيانات "
            "والمراجعة المسبقة."
        )
        self.unmet = unmet


class AIGateService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def readiness(self) -> dict:
        checks: list[dict] = []

        version = (
            await self.session.execute(
                select(QuranTextVersion).where(QuranTextVersion.is_active.is_(True))
            )
        ).scalar_one_or_none()

        checks.append(
            {
                "key": "active_text_version",
                "title": "يوجد إصدار نص مفعَّل",
                "passed": version is not None,
                "detail": version.version_code if version else "لا إصدار مفعَّل",
            }
        )
        checks.append(
            {
                "key": "text_version_validated",
                "title": "الإصدار المفعَّل اجتاز التحقق البنيوي",
                "passed": bool(version and version.is_validated),
                "detail": "محقَّق" if version and version.is_validated else "غير محقَّق",
            }
        )
        double_approved = bool(
            version
            and version.approved_by_first
            and version.approved_by_second
            and version.approved_by_first != version.approved_by_second
        )
        checks.append(
            {
                "key": "text_version_double_approved",
                "title": "الإصدار المفعَّل اعتمده مراجعان مستقلان",
                "passed": double_approved,
                "detail": "معتمد بمراجعَين" if double_approved else "الاعتماد المزدوج ناقص",
            }
        )

        golden = await MorphologyService(self.session).golden_check()
        checks.append(
            {
                "key": "golden_cases",
                "title": "المواضع المرجعية كلها تمر",
                "passed": golden["total"] > 0 and golden["failed"] == 0,
                "detail": f"{golden['passed']}/{golden['total']} ناجح",
            }
        )

        # يجب فحص التعارضات كلها لا صفحة منها: صفحة واحدة محسومة لا تعني
        # أن الباقي محسوم، والبوابة تمرّ خطأً حينئذ.
        conflicts = await MorphologyService(self.session).list_conflicts(limit=100)
        while len(conflicts["items"]) < conflicts["total"]:
            more = await MorphologyService(self.session).list_conflicts(
                offset=len(conflicts["items"]), limit=100
            )
            if not more["items"]:
                break
            conflicts["items"].extend(more["items"])
        unresolved = sum(1 for item in conflicts["items"] if not item.get("resolved"))
        checks.append(
            {
                "key": "morphology_conflicts_resolved",
                "title": "لا تعارض صرفي بلا قرار",
                "passed": unresolved == 0,
                "detail": f"{unresolved} تعارضًا بلا قرار من {conflicts['total']}",
            }
        )

        sources_total = await self.session.scalar(
            select(func.count(MorphologySource.id))
        )
        sources_hashed = await self.session.scalar(
            select(func.count(MorphologySource.id)).where(
                MorphologySource.file_sha256.is_not(None)
            )
        )
        checks.append(
            {
                "key": "morphology_sources_attributed",
                "title": "كل مصدر صرفي منسوب ببصمة ملفه",
                "passed": bool(sources_total) and sources_total == sources_hashed,
                "detail": f"{sources_hashed or 0}/{sources_total or 0}",
            }
        )

        unverified_sources = await self.session.scalar(
            select(func.count(SourceWork.id)).where(
                SourceWork.status == RecordStatus.DRAFT
            )
        )
        checks.append(
            {
                "key": "scholarly_sources_reviewed",
                "title": "لا مصدر علمي عالق بلا تحقق",
                "passed": (unverified_sources or 0) == 0,
                "detail": f"{unverified_sources or 0} مصدرًا بلا تحقق",
            }
        )

        open_disputes = await self.session.scalar(
            select(func.count(Dispute.id)).where(
                Dispute.status != DisputeStatus.RESOLVED
            )
        )
        checks.append(
            {
                "key": "no_open_disputes",
                "title": "لا خلاف علمي مفتوح",
                "passed": (open_disputes or 0) == 0,
                "detail": f"{open_disputes or 0} خلافًا مفتوحًا",
            }
        )

        golden_total = await self.session.scalar(select(func.count(GoldenRootCase.id)))
        checks.append(
            {
                "key": "golden_cases_seeded",
                "title": "المواضع المرجعية محمَّلة",
                "passed": (golden_total or 0) > 0,
                "detail": f"{golden_total or 0} موضعًا",
            }
        )

        unmet = [check for check in checks if not check["passed"]]
        return {
            "ready": not unmet,
            "enabled": bool(getattr(settings, "ai_features_enabled", False))
            and not unmet,
            "checks": checks,
            "unmet": unmet,
            "policy": (
                "لا تبدأ ميزات الذكاء الاصطناعي قبل اكتمال سلامة البيانات "
                "والمراجعة، وتقتصر حين تبدأ على التلخيص والمقارنة ضمن مواد "
                "مسترجعة وموثقة، ولا تُنشر مخرجاتها بوصفها معتمدة."
            ),
        }

    async def require_enabled(self) -> None:
        """يُستدعى في مقدمة أي ميزة ذكاء اصطناعي مستقبلية."""
        status = await self.readiness()
        if not status["enabled"]:
            raise AIDisabledError(status["unmet"])
