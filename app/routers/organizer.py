"""
Organizer router: /api/v1/organizer
- GET /events
- GET /events/{event_id}/bookings
"""
import math
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_organizer
from app.database import get_db
from app.models.booking import Booking
from app.models.event import Event
from app.models.user import User
from app.schemas.booking import BookingListResponse, BookingResponse
from app.schemas.event import EventListResponse, EventResponse

router = APIRouter(prefix="/organizer", tags=["organizer"])


@router.get(
    "/events",
    response_model=EventListResponse,
    summary="List all events created by current organizer (draft and published)",
)
def list_my_events(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
) -> EventListResponse:
    base_query = select(Event).where(Event.organizer_id == current_user.id)

    count_query = select(func.count()).select_from(base_query.subquery())
    total = db.execute(count_query).scalar_one()

    pages = math.ceil(total / size) if total > 0 else 1
    offset = (page - 1) * size

    events = (
        db.execute(
            base_query.order_by(Event.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        .scalars()
        .all()
    )

    return EventListResponse(
        items=[EventResponse.model_validate(e) for e in events],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get(
    "/events/{event_id}/bookings",
    response_model=BookingListResponse,
    summary="List all bookings for a specific event owned by this organizer",
)
def list_event_bookings(
    event_id: uuid.UUID,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
) -> BookingListResponse:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    if event.organizer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view bookings for events you organized",
        )

    base_query = select(Booking).where(Booking.event_id == event_id)

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
