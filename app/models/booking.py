"""
Booking model.

Design decisions:
- NO UNIQUE(event_id, customer_id) constraint: a customer may create multiple
  booking records for the same event (e.g., buying additional tickets later).
  This is an intentional application decision documented in the README.
- total_cents is calculated at booking time using integer arithmetic.
- Status transitions: confirmed → cancelled (one-way; cancelled bookings
  cannot be re-confirmed).
"""
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# PostgreSQL ENUM type
booking_status_enum = sa.Enum("confirmed", "cancelled", name="bookingstatus")


class Booking(Base):
    __tablename__ = "bookings"

    __table_args__ = (
        # Index to quickly find all confirmed bookings for an event
        # (used by event-update notification task)
        sa.Index("ix_bookings_event_id_status", "event_id", "status"),
        # Index to quickly list a customer's bookings
        sa.Index("ix_bookings_customer_id", "customer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=1,
    )
    status: Mapped[str] = mapped_column(
        booking_status_enum,
        nullable=False,
        default="confirmed",
    )
    # Total cost in cents; calculated at booking time: quantity * event.price_cents
    total_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False)
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
    event: Mapped["Event"] = relationship(  # noqa: F821
        "Event",
        back_populates="bookings",
    )
    customer: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="bookings",
    )
