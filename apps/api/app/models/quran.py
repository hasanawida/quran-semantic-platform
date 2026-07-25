import uuid
from datetime import datetime

from sqlalchemy import (
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
from app.models.enums import RecordStatus, pg_enum


class QuranTextVersion(UUIDMixin, TimestampMixin, Base):
    """إصدار نص قرآني موثق (قسم 10). يفعَّل إصدار واحد فقط في كل سياق."""

    __tablename__ = "quran_text_versions"
    __table_args__ = (
        # إصدار نشط واحد فقط: يخزَّن is_active كـ True أو NULL (لا False أبدًا).
        # فهرس فريد على عمود nullable يسمح بعدد NULL لا نهائي وقيمة True واحدة —
        # سلوك محمول عبر SQLite وPostgres. الانضباط (True/NULL) يفرض بطبقة الخدمة.
        Index("uq_only_one_active_version", "is_active", unique=True),
    )

    version_code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    riwayah: Mapped[str] = mapped_column(String(80), nullable=False)
    script_type: Mapped[str] = mapped_column(String(40), nullable=False)
    counting_system: Mapped[str] = mapped_column(String(40), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[RecordStatus] = mapped_column(
        pg_enum(RecordStatus, "record_status"),
        nullable=False,
        default=RecordStatus.IMPORTED,
    )
    is_active: Mapped[bool | None] = mapped_column(default=None, nullable=True)
    is_validated: Mapped[bool] = mapped_column(default=False, nullable=False)
    approved_by_first: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_by_second: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped["datetime | None"] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    activation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    ayahs: Mapped[list["Ayah"]] = relationship(back_populates="version")


class Surah(Base):
    """السورة بيانات ثابتة عبر الإصدارات (الاسم ونوع النزول).
    عدد الآيات يُشتق من آيات الإصدار النشط لا يخزَّن عالميًا (قسم 9 — تفادي
    تعارض العد مع نظام العد الخاص بالإصدار)."""

    __tablename__ = "surahs"

    number: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=False
    )
    arabic_name: Mapped[str] = mapped_column(String(80), nullable=False)
    revelation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # نص البسملة كما ورد في المصدر لهذه السورة. تُعرض قبل السورة ولا تُعد
    # آية إلا في الفاتحة، ولا توجد في براءة — لذا العمود nullable.
    basmala_text: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (CheckConstraint("number between 1 and 114", name="surah_range"),)


class Ayah(UUIDMixin, Base):
    """آية مرتبطة بإصدار نص. النص المعروض محفوظ كاملًا ولا يعاد تركيبه
    من الكلمات (السياسة العلمية)."""

    __tablename__ = "ayahs"
    __table_args__ = (
        UniqueConstraint("text_version_id", "surah_number", "ayah_number"),
        CheckConstraint("ayah_number > 0", name="ayah_number_positive"),
        Index("ix_ayahs_search", "plain_search_text"),
    )

    text_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("quran_text_versions.id", ondelete="CASCADE"), nullable=False
    )
    surah_number: Mapped[int] = mapped_column(
        ForeignKey("surahs.number"), nullable=False
    )
    ayah_number: Mapped[int] = mapped_column(Integer, nullable=False)
    uthmani_text: Mapped[str] = mapped_column(String(4000), nullable=False)
    plain_search_text: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    version: Mapped["QuranTextVersion"] = relationship(back_populates="ayahs")
    surah: Mapped["Surah"] = relationship()
