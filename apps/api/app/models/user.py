import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import UserRole, pg_enum


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    roles: Mapped[list["UserRoleAssignment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def role_values(self) -> set[str]:
        return {r.role.value for r in self.roles}


class UserRoleAssignment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="roles")


class ReviewerQualification(UUIDMixin, TimestampMixin, Base):
    """مؤهلات المراجع (قسم 9): تخصص، جهة، ملاحظة اعتماد."""

    __tablename__ = "reviewer_qualifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    specialty: Mapped[str] = mapped_column(String(120), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ConflictOfInterestDeclaration(UUIDMixin, TimestampMixin, Base):
    """إقرار تضارب المصالح (قسم 9)."""

    __tablename__ = "conflict_of_interest_declarations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    details: Mapped[str] = mapped_column(String(1000), nullable=False)
