"""نماذج المرحلة G — صندوق المراجعة والخلافات والتصحيحات.

سياسة السلامة العلمية (بند 6 و10): «الخلاف العلمي يُعرض ولا يُخفى»،
و«يجب حفظ سجل الإصدارات والتصحيحات».

  - التكليف بالمراجعة لا يقع على صاحب العمل ولا على من أقرّ بتضارب مصلحة.
  - الخلاف يبقى مفتوحًا ظاهرًا حتى تحسمه جهة مخوَّلة بتعليل.
  - التصحيح يحفظ «قبل» و«بعد» ولا يمحو الأصل.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import pg_enum


class ReviewTarget(str, Enum):
    """الكيانات القابلة للمراجعة. النص القرآني نفسه له مساره الخاص
    (آلة حالة الإصدارات) ولا يُراجع بهذا الصندوق."""

    CLAIM = "claim"
    SOURCE_WORK = "source_work"
    ROOT_DECISION = "root_decision"
    REPORT_VERSION = "report_version"


class AssignmentStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    COMPLETED = "completed"


class DisputeStatus(str, Enum):
    OPEN = "open"
    UNDER_ARBITRATION = "under_arbitration"
    RESOLVED = "resolved"
    WITHDRAWN = "withdrawn"


class CorrectionStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"


class ReviewAssignment(UUIDMixin, TimestampMixin, Base):
    """تكليف مراجع بمراجعة كيان بعينه."""

    __tablename__ = "review_assignments"
    __table_args__ = (
        UniqueConstraint(
            "target_type", "target_id", "reviewer_id", name="uq_assignment_target"
        ),
        Index("ix_assignment_target", "target_type", "target_id"),
    )

    target_type: Mapped[ReviewTarget] = mapped_column(
        pg_enum(ReviewTarget, "review_target"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        pg_enum(AssignmentStatus, "assignment_status"),
        nullable=False,
        default=AssignmentStatus.PENDING,
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decline_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReviewComment(UUIDMixin, TimestampMixin, Base):
    """تعليق مراجعة موثق. لا يُحذف؛ يُعلَّم مُعالَجًا."""

    __tablename__ = "review_comments"
    __table_args__ = (
        CheckConstraint("length(body) > 0", name="comment_body_required"),
        Index("ix_comment_target", "target_type", "target_id"),
    )

    target_type: Mapped[ReviewTarget] = mapped_column(
        pg_enum(ReviewTarget, "review_target"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Dispute(UUIDMixin, TimestampMixin, Base):
    """خلاف علمي موثق يبقى ظاهرًا حتى يُحسم بتعليل."""

    __tablename__ = "disputes"
    __table_args__ = (
        CheckConstraint("length(reason) > 0", name="dispute_reason_required"),
        Index("ix_dispute_target", "target_type", "target_id"),
    )

    target_type: Mapped[ReviewTarget] = mapped_column(
        pg_enum(ReviewTarget, "review_target"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    raised_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DisputeStatus] = mapped_column(
        pg_enum(DisputeStatus, "dispute_status"),
        nullable=False,
        default=DisputeStatus.OPEN,
    )
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Correction(UUIDMixin, TimestampMixin, Base):
    """تصحيح موثق: يحفظ «قبل» و«بعد» ولا يمحو الأصل."""

    __tablename__ = "corrections"
    __table_args__ = (
        CheckConstraint("length(description) > 0", name="correction_desc_required"),
        Index("ix_correction_target", "target_type", "target_id"),
    )

    target_type: Mapped[ReviewTarget] = mapped_column(
        pg_enum(ReviewTarget, "review_target"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    before_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    after_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CorrectionStatus] = mapped_column(
        pg_enum(CorrectionStatus, "correction_status"),
        nullable=False,
        default=CorrectionStatus.PROPOSED,
    )
    proposed_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dispute_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("disputes.id"), nullable=True
    )
