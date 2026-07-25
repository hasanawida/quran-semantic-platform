"""نماذج المرحلة D — الصرف متعدد المصادر (قسم 11 من الوثيقة).

المبدأ الحاكم: **الكلمة ملك النص، والتحليل ملك مصدره.**

  - `Token` ترميز المنصة نفسها لكلمات الآية، مشتق من نص الإصدار الموثق
    وحده. لا يأتي من مصدر صرفي، ولا يُعاد تركيب الآية منه.
  - `MorphologicalAnalysis` تحليل مقطع صرفي منسوب لمصدر بعينه، محفوظ
    حرفيًا كما ورد. تعدد المصادر مسموح، والاختلاف يُظهر لا يُخفى.
  - `TokenRootDecision` قرار بشري معلَّل يحسم اختلاف المصادر، باعتماد
    مراجع ثانٍ مستقل (لا يعتمد المقترِح قراره).
  - `GoldenRootCase` مواضع مرجعية تثبت أن خط الاشتقاق لم ينحرف.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ConfidenceLevel, RecordStatus, pg_enum

if TYPE_CHECKING:
    from app.models.language import Root
    from app.models.quran import Ayah


class MorphologySource(UUIDMixin, TimestampMixin, Base):
    """مصدر تحليل صرفي خارجي، ببصمة ملفه ورخصته وحالته العلمية."""

    __tablename__ = "morphology_sources"

    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    license_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notice: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[RecordStatus] = mapped_column(
        pg_enum(RecordStatus, "record_status"),
        nullable=False,
        default=RecordStatus.IMPORTED,
    )
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        pg_enum(ConfidenceLevel, "confidence_level"),
        nullable=False,
        default=ConfidenceLevel.MACHINE_ONLY,
    )
    # مصدر معطَّل يبقى محفوظًا للتتبع لكنه لا يشارك في اشتقاق المواضع
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    analyses: Mapped[list["MorphologicalAnalysis"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class Token(UUIDMixin, Base):
    """كلمة في آية وفق ترميز المنصة الموثق.

    المصدر الوحيد للترميز هو نص الإصدار (`Ayah.uthmani_text`): تقسيم على
    الفراغ مع إسقاط ما لا يحمل حرفًا عربيًا (علامات الوقف المستقلة).
    `char_start`/`char_end` مواضع في نص الآية نفسه، فيبقى التمييز مربوطًا
    بالنص الموثق لا بإعادة تركيبه."""

    __tablename__ = "tokens"
    __table_args__ = (
        UniqueConstraint("ayah_id", "word_number"),
        CheckConstraint("word_number > 0", name="token_word_number_positive"),
        CheckConstraint("char_end > char_start", name="token_char_span_valid"),
    )

    ayah_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ayahs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    word_number: Mapped[int] = mapped_column(Integer, nullable=False)
    surface_text: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(200), nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)

    ayah: Mapped["Ayah"] = relationship()


class MorphologicalAnalysis(UUIDMixin, Base):
    """تحليل مقطع صرفي واحد من مصدر واحد.

    `form_source` و`features` محفوظان حرفيًا كما وردا في المصدر (شرط رخصة
    المدونة: لا تعديل). الحقول المشتقة (pos/lemma/root) للفهرسة والعرض.

    `token_id` يُملأ فقط حين يتطابق ترميز المنصة مع عدّ كلمات المصدر لتلك
    الآية؛ وإلا بقي فارغًا: التحليل محفوظ ومنسوب، لكن ربطه بكلمة بعينها
    غير مؤكد فلا يُدَّعى."""

    __tablename__ = "morphological_analyses"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "ayah_id", "word_number", "segment_number",
            name="uq_analysis_source_position",
        ),
        CheckConstraint("word_number > 0", name="analysis_word_number_positive"),
        CheckConstraint("segment_number > 0", name="analysis_segment_number_positive"),
        Index("ix_analyses_position", "ayah_id", "word_number", "segment_number"),
        Index("ix_analyses_root", "root_id"),
        Index("ix_analyses_search", "pos", "aspect", "verb_form"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("morphology_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ayah_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ayahs.id", ondelete="CASCADE"), nullable=False
    )
    word_number: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    token_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tokens.id", ondelete="SET NULL"), nullable=True, index=True
    )

    form_source: Mapped[str] = mapped_column(String(200), nullable=False)
    tag: Mapped[str] = mapped_column(String(16), nullable=False)
    features: Mapped[str] = mapped_column(String(400), nullable=False)
    pos: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_stem: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lemma: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lemma_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # أبعاد مفهرسة مستخرجة من `features` — فهرسة للأصل لا تعديل له.
    # القيمة الفارغة تعني «لم يوسمها المصدر»، لا «غير موجودة».
    aspect: Mapped[str | None] = mapped_column(String(8), nullable=True)
    verb_form: Mapped[str | None] = mapped_column(String(6), nullable=True)
    voice: Mapped[str | None] = mapped_column(String(4), nullable=True)
    mood: Mapped[str | None] = mapped_column(String(8), nullable=True)
    person: Mapped[str | None] = mapped_column(String(1), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(1), nullable=True)
    grammatical_number: Mapped[str | None] = mapped_column(String(1), nullable=True)
    case_marking: Mapped[str | None] = mapped_column(String(4), nullable=True)
    definiteness: Mapped[str | None] = mapped_column(String(8), nullable=True)
    nominal_form: Mapped[str | None] = mapped_column(String(6), nullable=True)
    root_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("roots.id", ondelete="RESTRICT"), nullable=True
    )
    source_root_text: Mapped[str | None] = mapped_column(String(40), nullable=True)

    source: Mapped["MorphologySource"] = relationship(back_populates="analyses")
    root: Mapped["Root | None"] = relationship()
    token: Mapped["Token | None"] = relationship()


class TokenRootDecision(UUIDMixin, TimestampMixin, Base):
    """قرار بشري في جذر كلمة، يحسم اختلاف المصادر أو يصحّح مصدرًا واحدًا.

    القرار لا ينفذ إلا باعتماد مراجع ثانٍ مختلف عن مقترحه (قسم 13)."""

    __tablename__ = "token_root_decisions"
    __table_args__ = (
        UniqueConstraint("ayah_id", "word_number", name="uq_decision_position"),
        CheckConstraint("word_number > 0", name="decision_word_number_positive"),
    )

    ayah_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ayahs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    word_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # مجموعة الجذور المقررة فارغة = «لا جذر لهذه الكلمة»
    rationale: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[RecordStatus] = mapped_column(
        pg_enum(RecordStatus, "record_status"),
        nullable=False,
        default=RecordStatus.UNDER_REVIEW,
    )
    proposed_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    roots: Mapped[list["TokenRootDecisionRoot"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan", lazy="selectin"
    )


class TokenRootDecisionRoot(Base):
    """جذر ضمن قرار — كلمة واحدة قد تحمل أكثر من جذر (يٰبْنَؤُمَّ = بنو + أمم)."""

    __tablename__ = "token_root_decision_roots"

    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("token_root_decisions.id", ondelete="CASCADE"), primary_key=True
    )
    root_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roots.id", ondelete="RESTRICT"), primary_key=True
    )

    decision: Mapped["TokenRootDecision"] = relationship(back_populates="roots")
    root: Mapped["Root"] = relationship()


class GoldenRootCase(UUIDMixin, TimestampMixin, Base):
    """موضع مرجعي يثبت أن خط الاشتقاق يعطي الجذر المتوقع.

    ليس حكمًا علميًا مستقلًا: هو لقطة موثقة تكشف انحراف الترميز أو الاستيراد
    أو الاشتقاق عند أي تعديل لاحق. `expected_roots` مفاتيح مطبَّعة مفصولة
    بفواصل، والقيمة الفارغة تعني «لا جذر»."""

    __tablename__ = "golden_root_cases"
    __table_args__ = (
        UniqueConstraint("surah_number", "ayah_number", "word_number",
                         name="uq_golden_position"),
    )

    surah_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ayah_number: Mapped[int] = mapped_column(Integer, nullable=False)
    word_number: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_roots: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    citation: Mapped[str] = mapped_column(String(300), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    @property
    def expected_set(self) -> set[str]:
        return {r for r in self.expected_roots.split(",") if r}
