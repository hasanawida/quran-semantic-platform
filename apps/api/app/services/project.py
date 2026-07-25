"""خدمة المشاريع والتقارير (المرحلة F).

القواعد المفروضة هنا:

  1. المشروع الخاص لا يُقرأ ولا يُعدَّل إلا لأعضائه — يُفرض في الخدمة
     لا في الواجهة (سياسة الصلاحيات: التحقق خلفيّ دائمًا).
  2. لا يُنشر تقرير بلا ادعاء معتمد واحد على الأقل، ولا تُدرج فيه ادعاءات
     غير معتمدة: المسودة ليست نتيجة (سياسة 4).
  3. النسخة المنشورة غير قابلة للتعديل؛ التصحيح نسخة جديدة تشير إلى
     سابقتها فيبقى سجل الإصدارات كاملًا (سياسة 10).
"""

from __future__ import annotations

import hashlib
import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.audit import record_audit
from app.db.base import utcnow
from app.models.enums import RecordStatus
from app.models.project import (
    Project,
    ProjectClaim,
    ProjectMember,
    ProjectRole,
    ProjectVisibility,
    Report,
    ReportVersion,
)
from app.models.quran import QuranTextVersion
from app.models.scholarship import Claim
from app.models.user import User
from app.services.scholarship import ScholarshipService

# أدوار المنصة التي تطّلع على كل المشاريع لأغراض المراجعة والجودة
OVERSIGHT_ROLES = {"quality_manager", "tech_admin", "arbitration_committee"}


class ProjectError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---- صلاحيات ---------------------------------------------------------
    async def _require_project(self, project_id: uuid.UUID) -> Project:
        project = await self.session.get(Project, project_id)
        if project is None:
            raise ProjectError("PROJECT_NOT_FOUND", "المشروع غير موجود.")
        return project

    async def _member_role(
        self, project_id: uuid.UUID, user_id: uuid.UUID
    ) -> ProjectRole | None:
        return await self.session.scalar(
            select(ProjectMember.role).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )

    async def assert_can_read(self, project: Project, user: User) -> None:
        if project.visibility == ProjectVisibility.PUBLIC:
            return
        if project.owner_id == user.id:
            return
        if user.role_values & OVERSIGHT_ROLES:
            return
        if project.visibility == ProjectVisibility.INTERNAL:
            return
        if await self._member_role(project.id, user.id) is not None:
            return
        raise ProjectError("PROJECT_FORBIDDEN", "هذا المشروع خاص بأعضائه.")

    async def assert_can_edit(self, project: Project, user: User) -> None:
        if project.owner_id == user.id:
            return
        role = await self._member_role(project.id, user.id)
        if role in (ProjectRole.OWNER, ProjectRole.EDITOR):
            return
        raise ProjectError(
            "PROJECT_FORBIDDEN", "لا تملك صلاحية التعديل في هذا المشروع."
        )

    # ---- المشاريع --------------------------------------------------------
    @staticmethod
    def _project_dict(project: Project, members: list[dict]) -> dict:
        return {
            "id": str(project.id),
            "title": project.title,
            "description": project.description,
            "visibility": project.visibility.value,
            "status": project.status.value,
            "owner_id": str(project.owner_id),
            "members": members,
        }

    async def _members(self, project_id: uuid.UUID) -> list[dict]:
        rows = (
            await self.session.execute(
                select(ProjectMember, User.display_name)
                .join(User, User.id == ProjectMember.user_id)
                .where(ProjectMember.project_id == project_id)
                .order_by(ProjectMember.created_at)
            )
        ).all()
        return [
            {
                "user_id": str(member.user_id),
                "display_name": name,
                "role": member.role.value,
            }
            for member, name in rows
        ]

    async def create_project(self, data: dict, actor_id: uuid.UUID) -> dict:
        title = str(data.get("title", "")).strip()
        if not title:
            raise ProjectError("TITLE_REQUIRED", "عنوان المشروع مطلوب.")
        project = Project(
            title=title,
            description=(data.get("description") or None),
            visibility=ProjectVisibility(
                data.get("visibility", ProjectVisibility.PRIVATE.value)
            ),
            owner_id=actor_id,
        )
        self.session.add(project)
        await self.session.flush()
        self.session.add(
            ProjectMember(
                project_id=project.id,
                user_id=actor_id,
                role=ProjectRole.OWNER,
                added_by=actor_id,
            )
        )
        record_audit(
            self.session,
            action="project_create",
            entity_type="project",
            entity_id=project.id,
            actor_id=actor_id,
            new_data={"title": title, "visibility": project.visibility.value},
        )
        await self.session.commit()
        await self.session.refresh(project)
        return self._project_dict(project, await self._members(project.id))

    async def get_project(self, project_id: uuid.UUID, user: User) -> dict:
        project = await self._require_project(project_id)
        await self.assert_can_read(project, user)
        data = self._project_dict(project, await self._members(project.id))
        data["claims"] = await self._project_claims(project.id)
        return data

    async def list_projects(self, user: User) -> list[dict]:
        """يعيد ما يحق للمستخدم رؤيته فقط — لا تسريب عناوين المشاريع الخاصة."""
        member_project_ids = set(
            (
                await self.session.execute(
                    select(ProjectMember.project_id).where(
                        ProjectMember.user_id == user.id
                    )
                )
            ).scalars()
        )
        projects = (
            await self.session.execute(select(Project).order_by(Project.created_at.desc()))
        ).scalars()
        visible = []
        oversight = bool(user.role_values & OVERSIGHT_ROLES)
        for project in projects:
            allowed = (
                project.visibility != ProjectVisibility.PRIVATE
                or project.owner_id == user.id
                or project.id in member_project_ids
                or oversight
            )
            if allowed:
                visible.append(
                    self._project_dict(project, await self._members(project.id))
                )
        return visible

    async def add_member(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        role: str,
        actor: User,
    ) -> dict:
        project = await self._require_project(project_id)
        if project.owner_id != actor.id:
            member_role = await self._member_role(project.id, actor.id)
            if member_role != ProjectRole.OWNER:
                raise ProjectError(
                    "PROJECT_FORBIDDEN", "إدارة الأعضاء لمالك المشروع."
                )
        target = await self.session.get(User, user_id)
        if target is None:
            raise ProjectError("USER_NOT_FOUND", "المستخدم غير موجود.")
        existing = await self.session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == user_id,
            )
        )
        if existing is not None:
            existing.role = ProjectRole(role)
        else:
            self.session.add(
                ProjectMember(
                    project_id=project.id,
                    user_id=user_id,
                    role=ProjectRole(role),
                    added_by=actor.id,
                )
            )
        record_audit(
            self.session,
            action="project_member_set",
            entity_type="project",
            entity_id=project.id,
            actor_id=actor.id,
            new_data={"user_id": str(user_id), "role": role},
        )
        await self.session.commit()
        return self._project_dict(project, await self._members(project.id))

    # ---- ادعاءات المشروع -------------------------------------------------
    async def _project_claims(self, project_id: uuid.UUID) -> list[dict]:
        rows = (
            await self.session.execute(
                select(ProjectClaim.claim_id, ProjectClaim.ordering, Claim.status)
                .join(Claim, Claim.id == ProjectClaim.claim_id)
                .where(ProjectClaim.project_id == project_id)
                .order_by(ProjectClaim.ordering, ProjectClaim.created_at)
            )
        ).all()
        return [
            {"claim_id": str(claim_id), "ordering": ordering, "status": status.value}
            for claim_id, ordering, status in rows
        ]

    async def add_claim(
        self, project_id: uuid.UUID, claim_id: uuid.UUID, actor: User
    ) -> dict:
        project = await self._require_project(project_id)
        await self.assert_can_edit(project, actor)
        claim = await self.session.get(Claim, claim_id)
        if claim is None:
            raise ProjectError("CLAIM_NOT_FOUND", "الادعاء غير موجود.")
        exists = await self.session.scalar(
            select(ProjectClaim.id).where(
                ProjectClaim.project_id == project.id,
                ProjectClaim.claim_id == claim.id,
            )
        )
        if exists:
            raise ProjectError("CLAIM_ALREADY_IN_PROJECT", "الادعاء مضاف بالفعل.")
        count = await self.session.scalar(
            select(func.count(ProjectClaim.id)).where(
                ProjectClaim.project_id == project.id
            )
        )
        self.session.add(
            ProjectClaim(
                project_id=project.id,
                claim_id=claim.id,
                added_by=actor.id,
                ordering=(count or 0) + 1,
            )
        )
        record_audit(
            self.session,
            action="project_claim_add",
            entity_type="project",
            entity_id=project.id,
            actor_id=actor.id,
            new_data={"claim_id": str(claim.id)},
        )
        await self.session.commit()
        return await self.get_project(project.id, actor)

    # ---- التقارير --------------------------------------------------------
    async def create_report(
        self, project_id: uuid.UUID, title: str, summary: str | None, actor: User
    ) -> dict:
        project = await self._require_project(project_id)
        await self.assert_can_edit(project, actor)
        if not title.strip():
            raise ProjectError("TITLE_REQUIRED", "عنوان التقرير مطلوب.")
        report = Report(
            project_id=project.id,
            title=title.strip(),
            summary=(summary or None),
            created_by=actor.id,
        )
        self.session.add(report)
        await self.session.flush()
        record_audit(
            self.session,
            action="report_create",
            entity_type="report",
            entity_id=report.id,
            actor_id=actor.id,
            new_data={"project_id": str(project.id), "title": report.title},
        )
        await self.session.commit()
        return await self.get_report(report.id, actor)

    async def _require_report(self, report_id: uuid.UUID) -> Report:
        report = await self.session.get(Report, report_id)
        if report is None:
            raise ProjectError("REPORT_NOT_FOUND", "التقرير غير موجود.")
        return report

    async def get_report(self, report_id: uuid.UUID, user: User) -> dict:
        report = await self._require_report(report_id)
        project = await self._require_project(report.project_id)
        await self.assert_can_read(project, user)
        versions = (
            await self.session.execute(
                select(ReportVersion)
                .where(ReportVersion.report_id == report.id)
                .order_by(ReportVersion.version_number)
            )
        ).scalars().all()
        return {
            "id": str(report.id),
            "project_id": str(report.project_id),
            "title": report.title,
            "summary": report.summary,
            "created_by": str(report.created_by),
            "versions": [
                {
                    "id": str(version.id),
                    "version_number": version.version_number,
                    "content_hash": version.content_hash,
                    "claim_count": version.claim_count,
                    "status": version.status.value,
                    "published_at": version.published_at.isoformat(),
                    "published_by": str(version.published_by),
                    "change_note": version.change_note,
                    "supersedes_id": (
                        str(version.supersedes_id) if version.supersedes_id else None
                    ),
                }
                for version in versions
            ],
        }

    async def publish_report_version(
        self, report_id: uuid.UUID, actor: User, change_note: str | None = None
    ) -> dict:
        report = await self._require_report(report_id)
        project = await self._require_project(report.project_id)
        await self.assert_can_edit(project, actor)

        claim_ids = [
            row[0]
            for row in (
                await self.session.execute(
                    select(ProjectClaim.claim_id)
                    .join(Claim, Claim.id == ProjectClaim.claim_id)
                    .where(
                        ProjectClaim.project_id == project.id,
                        Claim.status == RecordStatus.APPROVED,
                    )
                    .order_by(ProjectClaim.ordering)
                )
            ).all()
        ]
        if not claim_ids:
            raise ProjectError(
                "NO_APPROVED_CLAIMS",
                "لا يُنشر تقرير بلا ادعاء معتمد واحد على الأقل — "
                "المسودة وما هو قيد المراجعة ليست نتائج.",
            )

        scholarship = ScholarshipService(self.session)
        # اللقطة تحمل إصدار النص وبصمته: التقرير يستشهد بنص بعينه، ولو
        # فُعّل إصدار آخر لاحقًا وجب أن يبقى معلومًا أيَّ نص كان يقصد.
        version = (
            await self.session.execute(
                select(QuranTextVersion).where(QuranTextVersion.is_active.is_(True))
            )
        ).scalar_one_or_none()
        snapshot = {
            "report": {"id": str(report.id), "title": report.title},
            "project": {"id": str(project.id), "title": project.title},
            "text_version": (
                {
                    "version_code": version.version_code,
                    "title": version.title,
                    "riwayah": version.riwayah,
                    "sha256": version.sha256_hash,
                    "status": version.status.value,
                }
                if version
                else None
            ),
            "claims": [await scholarship.get_claim(cid) for cid in claim_ids],
        }
        payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        content_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        last = (
            await self.session.execute(
                select(ReportVersion)
                .where(ReportVersion.report_id == report.id)
                .order_by(ReportVersion.version_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if last is not None and last.content_hash == content_hash:
            raise ProjectError(
                "NO_CHANGES", "لا جديد في المحتوى منذ النسخة الأخيرة."
            )

        version = ReportVersion(
            report_id=report.id,
            version_number=(last.version_number + 1) if last else 1,
            content_snapshot=payload,
            content_hash=content_hash,
            claim_count=len(claim_ids),
            status=RecordStatus.PUBLISHED,
            published_by=actor.id,
            published_at=utcnow(),
            change_note=(change_note or None),
            supersedes_id=last.id if last else None,
        )
        self.session.add(version)
        record_audit(
            self.session,
            action="report_publish_version",
            entity_type="report",
            entity_id=report.id,
            actor_id=actor.id,
            new_data={
                "version_number": version.version_number,
                "content_hash": content_hash,
                "claims": len(claim_ids),
            },
            reason=change_note,
        )
        await self.session.commit()
        return await self.get_report(report.id, actor)

    async def get_report_version(
        self, version_id: uuid.UUID, user: User
    ) -> dict:
        version = await self.session.get(ReportVersion, version_id)
        if version is None:
            raise ProjectError("VERSION_NOT_FOUND", "نسخة التقرير غير موجودة.")
        report = await self._require_report(version.report_id)
        project = await self._require_project(report.project_id)
        await self.assert_can_read(project, user)
        snapshot = json.loads(version.content_snapshot)
        recomputed = hashlib.sha256(
            version.content_snapshot.encode("utf-8")
        ).hexdigest()
        return {
            "id": str(version.id),
            "report_id": str(version.report_id),
            "version_number": version.version_number,
            "published_at": version.published_at.isoformat(),
            "content_hash": version.content_hash,
            "hash_verified": recomputed == version.content_hash,
            "change_note": version.change_note,
            "snapshot": snapshot,
            "notice": (
                "لقطة محفوظة لحظة النشر ببصمتها. لا تتغير بتغير الادعاءات "
                "لاحقًا؛ التصحيح يصدر نسخة جديدة تشير إلى هذه."
            ),
        }
