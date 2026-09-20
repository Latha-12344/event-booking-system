"""
Event model.

Prices are stored as INTEGER cents to avoid floating-point precision issues.
available_tickets is decremented atomically via SELECT FOR UPDATE in the booking service.
"""
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Event(Base):
    __tablename__ = "events"

    __table_args__ = (
        # Composite index for fast published-event browsing by date
        sa.Index("ix_events_published_starts_at", "is_published", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organizer_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    location: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    ends_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False
    )
    # Monetary value stored as integer cents (e.g., 1000 = $10.00)
    price_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    total_tickets: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    available_tickets: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    is_published: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
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
    organizer: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="events",
    )
    bookings: Mapped[list["Booking"]] = relationship(  # noqa: F821
        "Booking",
        back_populates="event",
        cascade="all, delete-orphan",
    )
