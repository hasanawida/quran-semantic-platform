from enum import Enum

from sqlalchemy import Enum as SAEnum


class RecordStatus(str, Enum):
    DRAFT = "draft"
    IMPORTED = "imported"
    MACHINE_GENERATED = "machine_generated"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    DISPUTED = "disputed"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


class ConfidenceLevel(str, Enum):
    VERIFIED = "verified"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MACHINE_ONLY = "machine_only"
    DISPUTED = "disputed"


class UserRole(str, Enum):
    RESEARCHER = "researcher"
    LINGUISTIC_REVIEWER = "linguistic_reviewer"
    SHARIA_REVIEWER = "sharia_reviewer"
    TEXT_OFFICER = "text_officer"
    QUALITY_MANAGER = "quality_manager"
    TECH_ADMIN = "tech_admin"
    ARBITRATION_COMMITTEE = "arbitration_committee"


def pg_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    """Enum محمول: VARCHAR + CHECK على كل الأنظمة (بلا نوع Postgres أصلي)
    لتبسيط الهجرات عبر SQLite وPostgres."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        values_callable=lambda e: [member.value for member in e],
        length=32,
    )
