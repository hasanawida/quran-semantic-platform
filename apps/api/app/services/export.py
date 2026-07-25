"""خدمة التصدير وبيان الأصول (المرحلة H).

**لا يخرج من المنصة مخرَج بلا نسب.** كل تصدير يحمل:

  - بيان الأصول: الإصدار النشط ومصادره وبصماتها ومصادر التحليل الصرفي.
  - حالة المراجعة لكل عنصر (مستورد/معتمد/مختلف فيه…) صراحةً.
  - تنبيهًا علميًا لا يُحذف يوضح ما هو نص وما هو تحليل وما هو رأي.
  - بصمة المخرَج نفسه ليمكن الاستشهاد به والتحقق منه لاحقًا.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RecordStatus
from app.models.language import Root, RootDerivation, RootOccurrence
from app.models.morphology import MorphologySource
from app.models.project import Report, ReportVersion
from app.models.quran import Ayah, QuranTextVersion, Surah
from app.models.user import User
from app.services.project import ProjectService
from app.utils.arabic import normalize_root_input

EXPORT_NOTICE = (
    "مخرَج من منصة الاستقراء الدلالي. النص القرآني منقول من إصدار موثق "
    "ولا يُولَّد آليًا. التحليل الصرفي منسوب لمصادره وحالته مبيَّنة. "
    "الادعاءات آراء باحثين موثقة بأدلتها وليست أحكامًا شرعية. "
    "لا يُقتطع هذا التنبيه عند إعادة النشر."
)

DERIVATION_LABELS = {
    RootDerivation.BUNDLE_IMPORT: "بذر مباشر من حزمة مستوردة",
    RootDerivation.SINGLE_SOURCE: "مصدر صرفي واحد بلا شاهد ثانٍ",
    RootDerivation.SOURCE_AGREEMENT: "اتفاق مصدرين فأكثر",
    RootDerivation.HUMAN_DECISION: "قرار مراجعة بشري معتمد",
}


class ExportError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


class ExportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- بيان الأصول ------------------------------------------------------
    async def provenance(self) -> dict:
        version = (
            await self.session.execute(
                select(QuranTextVersion).where(QuranTextVersion.is_active.is_(True))
            )
        ).scalar_one_or_none()
        if version is None:
            raise ExportError("NO_ACTIVE_VERSION", "لا يوجد إصدار نص مفعَّل.")

        ayah_count = await self.session.scalar(
            select(func.count(Ayah.id)).where(Ayah.text_version_id == version.id)
        )
        surah_count = await self.session.scalar(select(func.count(Surah.number)))
        root_count = await self.session.scalar(select(func.count(Root.id)))
        occurrence_count = await self.session.scalar(
            select(func.count(RootOccurrence.id))
        )
        by_derivation = {
            DERIVATION_LABELS[value]: (
                await self.session.scalar(
                    select(func.count(RootOccurrence.id)).where(
                        RootOccurrence.derivation == value
                    )
                )
                or 0
            )
            for value in RootDerivation
        }
        sources = (
            await self.session.execute(
                select(MorphologySource).order_by(MorphologySource.code)
            )
        ).scalars()

        return {
            "text_version": {
                "version_code": version.version_code,
                "title": version.title,
                "riwayah": version.riwayah,
                "script_type": version.script_type,
                "counting_system": version.counting_system,
                "source_name": version.source_name,
                "source_reference": version.source_reference,
                "sha256": version.sha256_hash,
                "status": version.status.value,
                "is_validated": version.is_validated,
                "double_approved": bool(
                    version.approved_by_first and version.approved_by_second
                ),
            },
            "counts": {
                "surahs": surah_count or 0,
                "ayahs": ayah_count or 0,
                "roots": root_count or 0,
                "root_occurrences": occurrence_count or 0,
            },
            "occurrences_by_derivation": by_derivation,
            "morphology_sources": [
                {
                    "code": source.code,
                    "name": source.name,
                    "url": source.url,
                    "version": source.source_version,
                    "license": source.license_note,
                    "file_sha256": source.file_sha256,
                    "status": source.status.value,
                    "enabled": source.is_enabled,
                }
                for source in sources
            ],
            "notice": EXPORT_NOTICE,
        }

    @staticmethod
    def _seal(payload: dict) -> dict:
        """يضيف بصمة المخرَج إلى نفسه — يُحتسب على المحتوى بلا البصمة."""
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        payload = dict(payload)
        payload["export_sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
        return payload

    # ---- تصدير مواضع جذر --------------------------------------------------
    async def _root_rows(self, root_query: str) -> tuple[Root, list[dict]]:
        key = normalize_root_input(root_query)
        if not key:
            raise ExportError("INVALID_ROOT", "مدخل الجذر غير صالح.")
        root = (
            await self.session.execute(select(Root).where(Root.normalized_root == key))
        ).scalar_one_or_none()
        if root is None:
            raise ExportError("ROOT_NOT_FOUND", "لا يوجد جذر بهذا المدخل.")
        version_id = await self.session.scalar(
            select(QuranTextVersion.id).where(QuranTextVersion.is_active.is_(True))
        )
        if version_id is None:
            raise ExportError("NO_ACTIVE_VERSION", "لا يوجد إصدار نص مفعَّل.")

        rows = (
            await self.session.execute(
                select(
                    Ayah.surah_number,
                    Ayah.ayah_number,
                    Surah.arabic_name,
                    RootOccurrence.word_number,
                    RootOccurrence.is_highlight_safe,
                    RootOccurrence.derivation,
                    Ayah.uthmani_text,
                )
                .join(RootOccurrence, RootOccurrence.ayah_id == Ayah.id)
                .join(Surah, Surah.number == Ayah.surah_number)
                .where(
                    RootOccurrence.root_id == root.id,
                    Ayah.text_version_id == version_id,
                )
                .order_by(
                    Ayah.surah_number, Ayah.ayah_number, RootOccurrence.word_number
                )
            )
        ).all()
        return root, [
            {
                "surah_number": surah,
                "surah_name": surah_name,
                "ayah_number": ayah,
                "word_number": word,
                "highlight_safe": bool(safe),
                "derivation": DERIVATION_LABELS[derivation],
                "uthmani_text": text,
            }
            for surah, ayah, surah_name, word, safe, derivation, text in rows
        ]

    async def export_root(self, root_query: str) -> dict:
        root, rows = await self._root_rows(root_query)
        return self._seal(
            {
                "kind": "root_occurrences",
                "root": {
                    "display": root.display_root,
                    "normalized": root.normalized_root,
                    "status": root.status.value,
                    "confidence": root.confidence.value,
                },
                "occurrence_count": len(rows),
                "occurrences": rows,
                "provenance": await self.provenance(),
            }
        )

    async def export_root_csv(self, root_query: str) -> str:
        root, rows = await self._root_rows(root_query)
        buffer = io.StringIO()
        # تعليق البيان أولًا حتى لا ينفصل الجدول عن نسبه
        buffer.write(f"# الجذر: {root.display_root} ({root.normalized_root})\n")
        buffer.write(f"# الحالة: {root.status.value}\n")
        buffer.write(f"# تنبيه: {EXPORT_NOTICE}\n")
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(
            [
                "surah_number",
                "surah_name",
                "ayah_number",
                "word_number",
                "highlight_safe",
                "derivation",
                "uthmani_text",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["surah_number"],
                    row["surah_name"],
                    row["ayah_number"],
                    row["word_number"],
                    "1" if row["highlight_safe"] else "0",
                    row["derivation"],
                    row["uthmani_text"],
                ]
            )
        return buffer.getvalue()

    # ---- تصدير نسخة تقرير -------------------------------------------------
    async def export_report_version(
        self, version_id: uuid.UUID, user: User
    ) -> dict:
        version = await self.session.get(ReportVersion, version_id)
        if version is None:
            raise ExportError("VERSION_NOT_FOUND", "نسخة التقرير غير موجودة.")
        if version.status != RecordStatus.PUBLISHED:
            raise ExportError("NOT_PUBLISHED", "لا يُصدَّر إلا ما نُشر.")
        report = await self.session.get(Report, version.report_id)
        project_service = ProjectService(self.session)
        project = await project_service._require_project(report.project_id)
        await project_service.assert_can_read(project, user)

        snapshot = json.loads(version.content_snapshot)
        return self._seal(
            {
                "kind": "report_version",
                "report": {"id": str(report.id), "title": report.title},
                "version": {
                    "number": version.version_number,
                    "published_at": version.published_at.isoformat(),
                    "content_hash": version.content_hash,
                    "change_note": version.change_note,
                    "supersedes_id": (
                        str(version.supersedes_id) if version.supersedes_id else None
                    ),
                },
                "snapshot": snapshot,
                "provenance": await self.provenance(),
            }
        )

    async def export_report_version_markdown(
        self, version_id: uuid.UUID, user: User
    ) -> str:
        payload = await self.export_report_version(version_id, user)
        snapshot = payload["snapshot"]
        provenance = payload["provenance"]
        lines: list[str] = [
            f"# {payload['report']['title']}",
            "",
            f"**المشروع:** {snapshot['project']['title']}",
            f"**النسخة:** {payload['version']['number']} — "
            f"{payload['version']['published_at']}",
            f"**بصمة المحتوى:** `{payload['version']['content_hash']}`",
            "",
            "> " + EXPORT_NOTICE,
            "",
            "## الادعاءات المعتمدة",
            "",
        ]
        for index, claim in enumerate(snapshot["claims"], start=1):
            subject = claim["subject"]
            where = subject.get("root") or subject.get("lemma") or ""
            if subject.get("surah"):
                where = f"{subject['surah']}:{subject['ayah']}"
                if subject.get("word_number"):
                    where += f" الكلمة {subject['word_number']}"
            lines += [
                f"### {index}. {claim['claim_type']} — {where}",
                "",
                claim["statement"],
                "",
                f"- الحالة: {claim['status']} | الثقة: {claim['confidence']}",
                f"- الباحث: {claim['author']['display_name']}",
                f"- أدلة مؤيدة: {claim['supporting_count']} | "
                f"معارضة: {claim['opposing_count']}",
                "",
                "**الأدلة:**",
                "",
            ]
            for evidence in claim["evidence"]:
                source = evidence["source"]
                stance = {"supports": "مؤيد", "opposes": "معارض", "context": "سياق"}[
                    evidence["stance"]
                ]
                lines.append(
                    f"- [{stance}] {source['author']}، *{source['title']}*، "
                    f"{source['edition']} — {evidence['locator']}"
                )
            lines.append("")

        text_version = provenance["text_version"]
        lines += [
            "## بيان الأصول",
            "",
            f"- إصدار النص: {text_version['title']} "
            f"({text_version['version_code']}، {text_version['riwayah']})",
            f"- بصمة الإصدار: `{text_version['sha256']}`",
            f"- الآيات: {provenance['counts']['ayahs']} | "
            f"الجذور: {provenance['counts']['roots']}",
        ]
        for source in provenance["morphology_sources"]:
            lines.append(
                f"- مصدر صرفي: {source['name']} ({source['code']}) — "
                f"{source['license']} — بصمة `{source['file_sha256']}`"
            )
        lines += ["", f"**بصمة هذا المخرَج:** `{payload['export_sha256']}`", ""]
        return "\n".join(lines)
