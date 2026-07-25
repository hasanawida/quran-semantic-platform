"""نماذج المرحلة F — المشاريع البحثية والتقارير ذات الإصدارات.

سياسة السلامة العلمية (بند 10): «يجب حفظ سجل الإصدارات والتصحيحات».

  - المشروع وعاء عمل خاص بأعضائه، والخصوصية تُفرض في طبقة الخدمة.
  - التقرير لا يُنشر إلا من ادعاءات معتمدة: المسودة ليست نتيجة.
  - نسخة التقرير المنشورة **غير قابلة للتعديل**؛ التصحيح نسخة جديدة
    تشير إلى ما قبلها، فيبقى ما نُشر قابلًا للمراجعة والاستشهاد.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import RecordStatus, pg_enum

if TYPE_CHECKING:
    from app.models.scholarship import Claim


class ProjectVisibility(str, Enum):
    PRIVATE = "private"  # الأعضاء فقط
    INTERNAL = "internal"  # كل مستخدم مسجَّل
    PUBLIC = "public"  # للعموم


class ProjectRole(str, Enum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("length(title) > 0", name="project_title_required"),
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[ProjectVisibility] = mapped_column(
        pg_enum(ProjectVisibility, "project_visibility"),
        nullable=False,
        default=ProjectVisibility.PRIVATE,
    )
    status: Mapped[RecordStatus] = mapped_column(
        pg_enum(RecordStatus, "record_status"),
        nullable=False,
        default=RecordStatus.DRAFT,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    members: Mapped[list["ProjectMember"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    claims: Mapped[list["ProjectClaim"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectMember(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[ProjectRole] = mapped_column(
        pg_enum(ProjectRole, "project_role"),
        nullable=False,
        default=ProjectRole.VIEWER,
    )
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    project: Mapped["Project"] = relationship(back_populates="members")


class ProjectClaim(UUIDMixin, TimestampMixin, Base):
    """ضم ادعاء إلى مشروع. الادعاء يبقى مملوكًا لصاحبه وحالته مستقلة."""

    __tablename__ = "project_claims"
    __table_args__ = (
        UniqueConstraint("project_id", "claim_id", name="uq_project_claim"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    ordering: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    project: Mapped["Project"] = relationship(back_populates="claims")
    claim: Mapped["Claim"] = relationship()


class Report(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("length(title) > 0", name="report_title_required"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    versions: Mapped[list["ReportVersion"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class ReportVersion(UUIDMixin, TimestampMixin, Base):
    """نسخة تقرير منشورة ببصمة محتواها.

    `content_snapshot` لقطة كاملة من الادعاءات وأدلتها لحظة النشر: التقرير
    لا يتغير معناه لاحقًا بتغير الادعاءات، ويبقى قابلًا للاستشهاد.
    `content_hash` بصمة اللقطة، و`supersedes_id` يربط التصحيح بما صحّحه."""

    __tablename__ = "report_versions"
    __table_args__ = (
        UniqueConstraint("report_id", "version_number", name="uq_report_version"),
        CheckConstraint("version_number > 0", name="report_version_positive"),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[RecordStatus] = mapped_column(
        pg_enum(RecordStatus, "record_status"),
        nullable=False,
        default=RecordStatus.PUBLISHED,
    )
    published_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    change_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("report_versions.id"), nullable=True
    )

    report: Mapped["Report"] = relationship(back_populates="versions")
