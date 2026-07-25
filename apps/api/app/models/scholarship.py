"""نماذج المرحلة E — المصادر العلمية والاستشهادات والادعاءات.

تنفيذ مباشر لثلاثة بنود من سياسة السلامة العلمية:

  5. كل تحليل يجب أن يحمل مصدرًا وحالة مراجعة.
  8. لا تُدخل مصادر غير مرخصة أو مجهولة الطبعة.
  9. لا تُنسب أقوال إلى العلماء دون توثيق.

ومن ثم: **لا ادعاء بلا استشهاد، ولا استشهاد بلا مصدر متحقَّق منه.**
والمخالفة تُمنع في طبقة الخدمة لا في الواجهة.
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
from app.models.enums import ConfidenceLevel, RecordStatus, pg_enum

if TYPE_CHECKING:
    from app.models.language import Root
    from app.models.quran import Ayah


class WorkType(str, Enum):
    DICTIONARY = "dictionary"  # معجم
    TAFSIR = "tafsir"  # تفسير
    GRAMMAR = "grammar"  # نحو وصرف
    HADITH = "hadith"  # حديث
    QIRAAT = "qiraat"  # قراءات
    ARTICLE = "article"  # بحث محكَّم
    DATASET = "dataset"  # مدونة رقمية
    OTHER = "other"


class ClaimSubject(str, Enum):
    ROOT = "root"
    LEMMA = "lemma"
    WORD = "word"  # كلمة بعينها في آية
    AYAH = "ayah"


class ClaimType(str, Enum):
    SEMANTIC = "semantic"  # دعوى دلالية
    MORPHOLOGICAL = "morphological"  # دعوى صرفية
    USAGE = "usage"  # دعوى استعمال
    COMPARISON = "comparison"  # مقارنة بين مواضع


class CitationStance(str, Enum):
    SUPPORTS = "supports"  # يؤيد
    OPPOSES = "opposes"  # يعارض — يُحفظ ويُعرض ولا يُخفى
    CONTEXT = "context"  # سياق أو تفصيل


class SourceWork(UUIDMixin, TimestampMixin, Base):
    """مصدر علمي معروف الطبعة والرخصة.

    الطبعة والرخصة حقلان إلزاميان: مصدر مجهول الطبعة لا يُقبل، ومصدر بلا
    إذن أو رخصة لا يُستشهد به. التحقق من المصدر إجراء بشري منفصل عن
    إدخاله (لا يتحقق المُدخِل من إدخاله)."""

    __tablename__ = "source_works"
    __table_args__ = (
        CheckConstraint("length(edition) > 0", name="source_edition_required"),
        CheckConstraint("length(license_note) > 0", name="source_license_required"),
    )

    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    author: Mapped[str] = mapped_column(String(200), nullable=False)
    work_type: Mapped[WorkType] = mapped_column(
        pg_enum(WorkType, "work_type"), nullable=False, default=WorkType.OTHER
    )
    edition: Mapped[str] = mapped_column(String(200), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    language: Mapped[str] = mapped_column(String(40), nullable=False, default="ar")
    license_note: Mapped[str] = mapped_column(String(500), nullable=False)
    access_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    status: Mapped[RecordStatus] = mapped_column(
        pg_enum(RecordStatus, "record_status"),
        nullable=False,
        default=RecordStatus.DRAFT,
    )
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    citations: Mapped[list["Citation"]] = relationship(
        back_populates="source_work", cascade="all, delete-orphan"
    )

    @property
    def is_verified(self) -> bool:
        return self.status == RecordStatus.APPROVED and self.verified_by is not None


class Citation(UUIDMixin, TimestampMixin, Base):
    """استشهاد بموضع محدد داخل مصدر.

    `locator` إلزامي (جزء/صفحة/مادة) — «قال فلان» بلا موضع ليس توثيقًا.
    `quoted_text` محدود الطول عمدًا: النقل للاستشهاد لا لإعادة نشر المصدر."""

    __tablename__ = "citations"
    __table_args__ = (
        CheckConstraint("length(locator) > 0", name="citation_locator_required"),
        UniqueConstraint(
            "source_work_id", "locator", "quoted_text", name="uq_citation_position"
        ),
    )

    source_work_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_works.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    locator: Mapped[str] = mapped_column(String(200), nullable=False)
    quoted_text: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    paraphrase: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    source_work: Mapped["SourceWork"] = relationship(back_populates="citations")


class Claim(UUIDMixin, TimestampMixin, Base):
    """ادعاء بحثي عن جذر أو كلمة أو آية.

    دورة الحياة: مسودة → قيد المراجعة → (معتمد | مختلف فيه | مرفوض).
    الرفع إلى المراجعة ممنوع بلا استشهاد مؤيد واحد على الأقل من مصدر
    متحقَّق منه، والاعتماد يلزمه مراجعان مستقلان غير صاحب الادعاء."""

    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint("length(statement) > 0", name="claim_statement_required"),
        CheckConstraint(
            "word_number is null or word_number > 0", name="claim_word_number_positive"
        ),
    )

    statement: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[ClaimType] = mapped_column(
        pg_enum(ClaimType, "claim_type"), nullable=False, default=ClaimType.SEMANTIC
    )
    subject_type: Mapped[ClaimSubject] = mapped_column(
        pg_enum(ClaimSubject, "claim_subject"), nullable=False
    )
    root_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("roots.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    ayah_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ayahs.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    word_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lemma: Mapped[str | None] = mapped_column(String(120), nullable=True)

    status: Mapped[RecordStatus] = mapped_column(
        pg_enum(RecordStatus, "record_status"),
        nullable=False,
        default=RecordStatus.DRAFT,
    )
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        pg_enum(ConfidenceLevel, "confidence_level"),
        nullable=False,
        default=ConfidenceLevel.LOW,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_first: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_by_second: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    evidence: Mapped[list["ClaimCitation"]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )
    root: Mapped["Root | None"] = relationship()
    ayah: Mapped["Ayah | None"] = relationship()


class ClaimCitation(UUIDMixin, TimestampMixin, Base):
    """دليل مرتبط بادعاء، بموقفه منه.

    الأدلة المعارضة تُحفظ وتُعرض مع الادعاء — «الخلاف العلمي يُعرض ولا
    يُخفى» — ولا تمنع اعتماد الادعاء بل توثّقه."""

    __tablename__ = "claim_citations"
    __table_args__ = (
        UniqueConstraint("claim_id", "citation_id", name="uq_claim_citation"),
    )

    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    citation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("citations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    stance: Mapped[CitationStance] = mapped_column(
        pg_enum(CitationStance, "citation_stance"),
        nullable=False,
        default=CitationStance.SUPPORTS,
    )
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    claim: Mapped["Claim"] = relationship(back_populates="evidence")
    citation: Mapped["Citation"] = relationship()
