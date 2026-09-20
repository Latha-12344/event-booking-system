"""
Booking service layer.

Handles concurrency control via SELECT ... FOR UPDATE pessimistic locking,
safe ticket allocation, and strict post-commit Celery task dispatch.
"""
import math
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.event import Event
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingListResponse, BookingResponse
from app.tasks.email_tasks import send_booking_confirmation


def create_booking(
    db: Session,
    data: BookingCreate,
    customer: User,
) -> Booking:
    """
    Create a new booking using pessimistic locking (SELECT FOR UPDATE).
    
    Order of operations:
    1. Acquire row lock on the event: SELECT ... FOR UPDATE
    2. Validate availability and decrement available_tickets
    3. Insert booking record
    4. COMMIT transaction (releases lock, ensures durability)
    5. AFTER successful commit: dispatch Celery email confirmation task
    """
    # 1. Acquire row-level lock on event
    stmt = select(Event).where(Event.id == data.event_id).with_for_update()
    event = db.execute(stmt).scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    if not event.is_published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book tickets for an unpublished event",
        )

    # Optional check: has event ended?
    now = datetime.now(timezone.utc)
    event_ends = event.ends_at
    if event_ends.tzinfo is None:
        event_ends = event_ends.replace(tzinfo=timezone.utc)
    if event_ends < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book tickets for an event that has already ended",
        )

    # 2. Check ticket availability
    if event.available_tickets < data.quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Not enough tickets available. Remaining: {event.available_tickets}, requested: {data.quantity}",
        )

    # Decrement tickets & compute total
    event.available_tickets -= data.quantity
    total_cents = data.quantity * event.price_cents

    booking = Booking(
        event_id=event.id,
        customer_id=customer.id,
        quantity=data.quantity,
        status="confirmed",
        total_cents=total_cents,
    )
    db.add(booking)

    # 3. Commit transaction — guarantees DB consistency before queueing background work
    # Keep server-generated defaults loaded from the INSERT RETURNING result so
    # the booking path does not perform a second SELECT after commit.
    db.expire_on_commit = False
    db.commit()

    # Capture details for email payload
    starts_at_str = event.starts_at.strftime("%Y-%m-%d %H:%M UTC") if event.starts_at else "TBD"

    # 4. Enqueue task ONLY after successful commit
    send_booking_confirmation.delay(
        booking_id=str(booking.id),
        customer_email=customer.email,
        customer_name=customer.full_name,
        event_title=event.title,
        starts_at=starts_at_str,
        location=event.location,
        quantity=booking.quantity,
        total_cents=booking.total_cents,
    )

    return booking


def get_booking_by_id(
    db: Session,
    booking_id: uuid.UUID,
    customer_id: uuid.UUID,
) -> Booking:
    """Retrieve booking by ID with customer ownership validation."""
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )
    if booking.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own bookings",
        )
    return booking


def list_customer_bookings(
    db: Session,
    customer_id: uuid.UUID,
    page: int = 1,
    size: int = 20,
) -> BookingListResponse:
    """List bookings for the authenticated customer."""
    base_query = select(Booking).where(Booking.customer_id == customer_id)

    count_query = select(func.count()).select_from(base_query.subquery())
    total = db.execute(count_query).scalar_one()

    pages = math.ceil(total / size) if total > 0 else 1
    offset = (page - 1) * size

    bookings = (
        db.execute(
            base_query.order_by(Booking.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        .scalars()
        .all()
    )

    return BookingListResponse(
        items=[BookingResponse.model_validate(b) for b in bookings],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


def cancel_booking(
    db: Session,
    booking_id: uuid.UUID,
    customer_id: uuid.UUID,
) -> Booking:
    """
    Cancel an existing booking and release held tickets back to the event.
    Uses pessimistic locking on the event row to prevent ticket count drift.
    """
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found",
        )
    if booking.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel your own bookings",
        )
    if booking.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking is already cancelled",
        )

    # Lock the event row and restore available tickets
    stmt = select(Event).where(Event.id == booking.event_id).with_for_update()
    event = db.execute(stmt).scalar_one_or_none()
    if event:
        event.available_tickets += booking.quantity

    booking.status = "cancelled"
    db.commit()
    db.refresh(booking)
    return booking
