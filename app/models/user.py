"""
User model.

Roles:
  organizer — creates and manages events
  customer  — browses events and books tickets
"""
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str):
    ORGANIZER = "organizer"
    CUSTOMER = "customer"


# PostgreSQL ENUM type (created once in the DB)
user_role_enum = sa.Enum("organizer", "customer", name="userrole")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        sa.String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(sa.Text, nullable=False)
    full_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        user_role_enum,
        nullable=False,
        default="customer",
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.true(),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    events: Mapped[list["Event"]] = relationship(  # noqa: F821
        "Event",
        back_populates="organizer",
        cascade="all, delete-orphan",
    )
    bookings: Mapped[list["Booking"]] = relationship(  # noqa: F821
        "Booking",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
