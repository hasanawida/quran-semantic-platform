"""آلة حالة إدارة إصدارات النص القرآني (قسم 10 من الوثيقة).

المسار: استيراد → تحقق بنيوي → مراجعتان مستقلتان (اعتماد مزدوج) → تفعيل.
قواعد صارمة: لا يعتمد مراجع عمله (SELF_REVIEW_FORBIDDEN)، ويلزم مراجعان
مختلفان (SECOND_REVIEW_REQUIRED)، وإصدار نشط واحد فقط يُبدَّل ذريًا.
"""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.audit import record_audit
from app.db.base import utcnow
from app.models.enums import RecordStatus
from app.models.quran import Ayah, QuranTextVersion
from app.utils.arabic import normalize_arabic_search

# الأدوار المؤهَّلة لاعتماد إصدار نص (مراجعون مستقلون)
APPROVER_ROLES = {
    "text_officer",
    "tech_admin",
    "quality_manager",
    "linguistic_reviewer",
    "sharia_reviewer",
}

FULL_MUSHAF_AYAH_COUNT = 6236
FULL_MUSHAF_SURAH_COUNT = 114


class VersionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


class TextVersionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, version_id: uuid.UUID) -> QuranTextVersion | None:
        return await self.session.get(QuranTextVersion, version_id)

    async def _require(self, version_id: uuid.UUID) -> QuranTextVersion:
        version = await self.get(version_id)
        if version is None:
            raise VersionError("VERSION_NOT_FOUND", "الإصدار غير موجود.")
        return version

    async def list_versions(self) -> list[dict]:
        rows = (
            await self.session.execute(
                select(QuranTextVersion).order_by(QuranTextVersion.created_at)
            )
        ).scalars()
        return [self._to_dict(v) for v in rows]

    @staticmethod
    def _to_dict(v: QuranTextVersion) -> dict:
        return {
            "id": str(v.id),
            "version_code": v.version_code,
            "title": v.title,
            "riwayah": v.riwayah,
            "script_type": v.script_type,
            "counting_system": v.counting_system,
            "status": v.status.value,
            "is_active": bool(v.is_active),
            "is_validated": v.is_validated,
            "approved_by_first": str(v.approved_by_first) if v.approved_by_first else None,
            "approved_by_second": str(v.approved_by_second) if v.approved_by_second else None,
            "activation_reason": v.activation_reason,
        }

    # ---- استيراد ----------------------------------------------------------
    async def import_version(
        self, meta: dict, ayahs: list[tuple[int, int, str]], actor_id: uuid.UUID
    ) -> QuranTextVersion:
        exists = await self.session.scalar(
            select(QuranTextVersion.id).where(
                QuranTextVersion.version_code == meta["version_code"]
            )
        )
        if exists:
            raise VersionError("VERSION_CONFLICT", "رمز الإصدار مستخدم بالفعل.")

        # بصمة على النص المتسلسل — تُثبت سلامة المحتوى
        digest = hashlib.sha256(
            "\n".join(f"{s}|{a}|{t}" for s, a, t in ayahs).encode("utf-8")
        ).hexdigest()

        version = QuranTextVersion(
            version_code=meta["version_code"],
            title=meta["title"],
            riwayah=meta["riwayah"],
            script_type=meta["script_type"],
            counting_system=meta["counting_system"],
            source_name=meta["source_name"],
            source_reference=meta.get("source_reference"),
            sha256_hash=digest,
            status=RecordStatus.IMPORTED,
            is_active=None,
        )
        self.session.add(version)
        await self.session.flush()

        self.session.add_all(
            [
                Ayah(
                    text_version_id=version.id,
                    surah_number=s,
                    ayah_number=a,
                    uthmani_text=t,
                    text_hash=hashlib.sha256(t.encode("utf-8")).hexdigest(),
                    # مفتاح البحث يُشتق هنا لا يُترك فارغًا: كان هذا المسار
                    # — وهو المسار الرسمي للاستيراد — يهمله، فأي إصدار
                    # يُستورد ويُفعَّل عبره يجعل البحث يعيد صفرًا **صامتًا
                    # بلا رسالة خطأ**. والتطبيع للبحث وحده ولا يمسّ
                    # `uthmani_text` المعروض.
                    plain_search_text=normalize_arabic_search(t),
                )
                for s, a, t in ayahs
            ]
        )
        record_audit(
            self.session,
            action="version_import",
            entity_type="quran_text_version",
            entity_id=version.id,
            actor_id=actor_id,
            new_data={"version_code": meta["version_code"], "ayahs": len(ayahs)},
        )
        await self.session.commit()
        await self.session.refresh(version)
        return version

    # ---- تحقق بنيوي -------------------------------------------------------
    async def validate(
        self, version_id: uuid.UUID, actor_id: uuid.UUID, require_full: bool = True
    ) -> dict:
        version = await self._require(version_id)
        issues: list[str] = []

        pairs = (
            await self.session.execute(
                select(Ayah.surah_number, Ayah.ayah_number)
                .where(Ayah.text_version_id == version.id)
                .order_by(Ayah.surah_number, Ayah.ayah_number)
            )
        ).all()
        total = len(pairs)
        surahs_present = {s for s, _ in pairs}

        # تسلسل الآيات داخل كل سورة يبدأ من 1 بلا فجوات
        by_surah: dict[int, list[int]] = {}
        for s, a in pairs:
            by_surah.setdefault(s, []).append(a)
        for s, nums in by_surah.items():
            expected = list(range(1, len(nums) + 1))
            if sorted(nums) != expected:
                issues.append(f"تسلسل آيات غير صحيح في السورة {s}")

        # إصدار بلا مفاتيح بحث يعمل تمامًا في العرض ويعيد صفرًا في البحث
        # بلا أي إنذار — وهو أسوأ أنواع العطب. فيُكشف هنا لا عند المستعمل.
        blind = await self.session.scalar(
            select(func.count())
            .select_from(Ayah)
            .where(
                Ayah.text_version_id == version.id,
                (Ayah.plain_search_text.is_(None))
                | (func.trim(Ayah.plain_search_text) == ""),
            )
        )
        if blind:
            issues.append(
                f"{blind} آية بلا مفتاح بحث (plain_search_text) — "
                "البحث سيعيد صفرًا صامتًا في هذا الإصدار"
            )

        if require_full:
            if total != FULL_MUSHAF_AYAH_COUNT:
                issues.append(
                    f"عدد الآيات {total} لا يطابق المصحف الكامل "
                    f"({FULL_MUSHAF_AYAH_COUNT})"
                )
            if len(surahs_present) != FULL_MUSHAF_SURAH_COUNT:
                issues.append(
                    f"عدد السور {len(surahs_present)} لا يطابق "
                    f"{FULL_MUSHAF_SURAH_COUNT}"
                )

        ok = not issues
        version.is_validated = ok
        record_audit(
            self.session,
            action="version_validate",
            entity_type="quran_text_version",
            entity_id=version.id,
            actor_id=actor_id,
            new_data={"ok": ok, "issues": issues, "ayah_count": total},
        )
        await self.session.commit()
        return {"ok": ok, "issues": issues, "ayah_count": total}

    # ---- مقارنة إصدارين ---------------------------------------------------
    async def compare(self, a_id: uuid.UUID, b_id: uuid.UUID) -> dict:
        await self._require(a_id)
        await self._require(b_id)

        async def _map(vid: uuid.UUID) -> dict[tuple[int, int], str]:
            rows = (
                await self.session.execute(
                    select(Ayah.surah_number, Ayah.ayah_number, Ayah.uthmani_text)
                    .where(Ayah.text_version_id == vid)
                )
            ).all()
            return {(s, a): t for s, a, t in rows}

        a_map = await _map(a_id)
        b_map = await _map(b_id)
        a_keys, b_keys = set(a_map), set(b_map)

        missing_in_b = sorted(a_keys - b_keys)
        extra_in_b = sorted(b_keys - a_keys)
        text_diffs = [
            {"surah": s, "ayah": a}
            for (s, a) in sorted(a_keys & b_keys)
            if a_map[(s, a)] != b_map[(s, a)]
        ]
        return {
            "missing_in_b": [{"surah": s, "ayah": a} for s, a in missing_in_b],
            "extra_in_b": [{"surah": s, "ayah": a} for s, a in extra_in_b],
            "text_differences": text_diffs,
            "identical": not (missing_in_b or extra_in_b or text_diffs),
        }

    # ---- اعتماد مزدوج -----------------------------------------------------
    async def approve(
        self, version_id: uuid.UUID, reviewer_id: uuid.UUID
    ) -> QuranTextVersion:
        version = await self._require(version_id)
        if not version.is_validated:
            raise VersionError(
                "NOT_VALIDATED", "يجب اجتياز التحقق البنيوي قبل الاعتماد."
            )
        if version.status in (RecordStatus.APPROVED, RecordStatus.PUBLISHED):
            raise VersionError("ALREADY_APPROVED", "الإصدار معتمد بالفعل.")

        if version.approved_by_first is None:
            version.approved_by_first = reviewer_id
            action = "version_approve_first"
        else:
            if version.approved_by_first == reviewer_id:
                raise VersionError(
                    "SELF_REVIEW_FORBIDDEN",
                    "لا يجوز أن يعتمد المراجع نفسه مرتين؛ يلزم مراجع ثانٍ مستقل.",
                )
            version.approved_by_second = reviewer_id
            version.status = RecordStatus.APPROVED
            version.approved_at = utcnow()
            action = "version_approve_second"

        record_audit(
            self.session,
            action=action,
            entity_type="quran_text_version",
            entity_id=version.id,
            actor_id=reviewer_id,
        )
        await self.session.commit()
        await self.session.refresh(version)
        return version

    async def publish(
        self, version_id: uuid.UUID, actor_id: uuid.UUID
    ) -> QuranTextVersion:
        version = await self._require(version_id)
        if version.status != RecordStatus.APPROVED:
            raise VersionError(
                "SECOND_REVIEW_REQUIRED",
                "لا يُنشر إلا إصدار اجتاز الاعتماد المزدوج.",
            )
        version.status = RecordStatus.PUBLISHED
        record_audit(
            self.session,
            action="version_publish",
            entity_type="quran_text_version",
            entity_id=version.id,
            actor_id=actor_id,
        )
        await self.session.commit()
        await self.session.refresh(version)
        return version

    # ---- تفعيل ذري --------------------------------------------------------
    async def activate(
        self, version_id: uuid.UUID, actor_id: uuid.UUID, reason: str
    ) -> QuranTextVersion:
        version = await self._require(version_id)

        if version.status not in (RecordStatus.APPROVED, RecordStatus.PUBLISHED):
            raise VersionError(
                "SECOND_REVIEW_REQUIRED",
                "لا يُفعَّل إلا إصدار معتمد أو منشور.",
            )
        if not (version.approved_by_first and version.approved_by_second):
            raise VersionError(
                "SECOND_REVIEW_REQUIRED", "يلزم اعتماد مراجعين مستقلين."
            )
        if version.approved_by_first == version.approved_by_second:
            raise VersionError(
                "SELF_REVIEW_FORBIDDEN", "المراجعان يجب أن يكونا مختلفين."
            )
        if not reason or not reason.strip():
            raise VersionError("REASON_REQUIRED", "سبب التفعيل مطلوب.")

        # إلغاء تفعيل جميع الإصدارات الأخرى ثم تفعيل هذا — ضمن معاملة واحدة.
        # (is_active يخزَّن True أو NULL؛ الفهرس الفريد يضمن نشطًا واحدًا)
        await self.session.execute(
            update(QuranTextVersion)
            .where(QuranTextVersion.id != version.id)
            .values(is_active=None)
        )
        version.is_active = True
        version.activated_by = actor_id
        version.activation_reason = reason.strip()
        record_audit(
            self.session,
            action="version_activate",
            entity_type="quran_text_version",
            entity_id=version.id,
            actor_id=actor_id,
            reason=reason.strip(),
        )
        await self.session.commit()
        await self.session.refresh(version)
        return version

    async def active_version_id(self) -> uuid.UUID | None:
        return await self.session.scalar(
            select(QuranTextVersion.id).where(QuranTextVersion.is_active.is_(True))
        )

    async def count_ayahs(self, version_id: uuid.UUID) -> int:
        return await self.session.scalar(
            select(func.count(Ayah.id)).where(Ayah.text_version_id == version_id)
        )
