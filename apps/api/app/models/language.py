import uuid
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ConfidenceLevel, RecordStatus, pg_enum

if TYPE_CHECKING:
    from app.models.quran import Ayah


class Root(UUIDMixin, TimestampMixin, Base):
    """جذر لغوي. يحفظ بصيغة عرض وصيغة مطبّعة قانونية للبحث."""

    __tablename__ = "roots"
    __table_args__ = (
        CheckConstraint("root_length between 2 and 5", name="root_length_range"),
    )

    display_root: Mapped[str] = mapped_column(String(40), nullable=False)
    normalized_root: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )
    root_length: Mapped[int] = mapped_column(Integer, nullable=False)
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

    occurrences: Mapped[list["RootOccurrence"]] = relationship(
        back_populates="root", cascade="all, delete-orphan"
    )


class RootDerivation(str, Enum):
    """كيف نشأ هذا الموضع — يُعرض للباحث ولا يُخفى."""

    BUNDLE_IMPORT = "bundle_import"  # بذر أولي مباشر من الحزمة (قبل المرحلة D)
    SINGLE_SOURCE = "single_source"  # مصدر صرفي واحد، بلا شاهد ثانٍ
    SOURCE_AGREEMENT = "source_agreement"  # اتفاق مصدرين فأكثر
    HUMAN_DECISION = "human_decision"  # قرار مراجعة معتمد


class RootOccurrence(UUIDMixin, Base):
    """فهرس مواضع الجذر. يمثّل ظهور كلمة مشتقة من الجذر في موضع
    (آية + رقم كلمة). من المرحلة D فصاعدًا يُعاد بناؤه اشتقاقًا من
    `morphological_analyses` وقرارات المراجعة، لا يُكتب يدويًا."""

    __tablename__ = "root_occurrences"
    __table_args__ = (
        UniqueConstraint("root_id", "ayah_id", "word_number",
                         name="uq_occurrence_position"),
    )

    root_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ayah_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ayahs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    word_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # التمييز آمن فقط حين يتطابق عدّ الكلمات بين مصدر النص ومصدر الصرف
    is_highlight_safe: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    token_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tokens.id", ondelete="SET NULL"), nullable=True
    )
    derivation: Mapped[RootDerivation] = mapped_column(
        pg_enum(RootDerivation, "root_derivation"),
        nullable=False,
        default=RootDerivation.BUNDLE_IMPORT,
    )

    root: Mapped["Root"] = relationship(back_populates="occurrences")
    ayah: Mapped["Ayah"] = relationship()
