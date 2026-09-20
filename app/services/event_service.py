"""
Event service layer.

Handles business logic for event creation, listing, retrieval, update,
and publishing. Guaranteed post-commit Celery notification dispatch.
"""
import math
import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.event import Event
from app.schemas.event import EventCreate, EventListResponse, EventPatch, EventResponse, EventUpdate
from app.tasks.email_tasks import send_event_update_notifications


def create_event(db: Session, data: EventCreate, organizer_id: uuid.UUID) -> Event:
    """Create a new event in draft (unpublished) state."""
    event = Event(
        organizer_id=organizer_id,
        title=data.title,
        description=data.description,
        location=data.location,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        price_cents=data.price_cents,
        total_tickets=data.total_tickets,
        available_tickets=data.total_tickets,
        is_published=False,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_event_by_id(db: Session, event_id: uuid.UUID) -> Event:
    """Retrieve an event or raise 404."""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return event


def list_published_events(
    db: Session,
    page: int = 1,
    size: int = 20,
    search: str | None = None,
    location: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> EventListResponse:
    """List published events with optional filtering and pagination."""
    query = select(Event).where(Event.is_published.is_(True))

    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Event.title.ilike(search_pattern),
                Event.description.ilike(search_pattern),
            )
        )

    if location:
        query = query.where(Event.location.ilike(f"%{location.strip()}%"))

    if date_from:
        query = query.where(Event.starts_at >= date_from)

    if date_to:
        query = query.where(Event.starts_at <= date_to)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar_one()

    # Apply pagination and sorting
    pages = math.ceil(total / size) if total > 0 else 1
    offset = (page - 1) * size
    events = (
        db.execute(query.order_by(Event.starts_at.asc()).offset(offset).limit(size))
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


def update_event(
    db: Session,
    event_id: uuid.UUID,
    data: EventUpdate,
    organizer_id: uuid.UUID,
) -> Event:
    """
    Full update of an event.
    Verifies organizer ownership, adjusts available tickets safely,
    commits, then enqueues event update notifications.
    """
    event = get_event_by_id(db, event_id)
    if event.organizer_id != organizer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit events you organized",
        )

    # Validate tickets count against already booked tickets
    booked_tickets = event.total_tickets - event.available_tickets
    if data.total_tickets < booked_tickets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reduce total tickets below already booked quantity ({booked_tickets})",
        )

    # Track changes for notification
    changes: dict[str, Any] = {}
    if event.title != data.title:
        changes["title"] = f"{event.title} -> {data.title}"
    if event.starts_at != data.starts_at:
        changes["starts_at"] = f"{event.starts_at.isoformat()} -> {data.starts_at.isoformat()}"
    if event.location != data.location:
        changes["location"] = f"{event.location or 'N/A'} -> {data.location or 'N/A'}"
    if event.description != data.description:
        changes["description"] = "Event description updated"
    if event.ends_at != data.ends_at:
        changes["ends_at"] = f"{event.ends_at.isoformat()} -> {data.ends_at.isoformat()}"
    if event.price_cents != data.price_cents:
        changes["price_cents"] = f"{event.price_cents} -> {data.price_cents}"
    if event.total_tickets != data.total_tickets:
        changes["total_tickets"] = f"{event.total_tickets} -> {data.total_tickets}"

    # Apply updates
    event.title = data.title
    event.description = data.description
    event.location = data.location
    event.starts_at = data.starts_at
    event.ends_at = data.ends_at
    event.price_cents = data.price_cents
    event.total_tickets = data.total_tickets
    event.available_tickets = data.total_tickets - booked_tickets

    # 1. Commit changes to DB
    db.commit()
    db.refresh(event)

    # 2. Post-commit task enqueueing
    if changes and event.is_published:
        send_event_update_notifications.delay(
            event_id=str(event.id),
            changes=changes,
        )

    return event


def patch_event(
    db: Session,
    event_id: uuid.UUID,
    data: EventPatch,
    organizer_id: uuid.UUID,
) -> Event:
    """Partial update of an event."""
    event = get_event_by_id(db, event_id)
    if event.organizer_id != organizer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit events you organized",
        )

    proposed_starts_at = data.starts_at or event.starts_at
    proposed_ends_at = data.ends_at or event.ends_at
    if proposed_ends_at <= proposed_starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ends_at must be after starts_at",
        )

    changes: dict[str, Any] = {}
    if data.title is not None and data.title != event.title:
        changes["title"] = f"{event.title} -> {data.title}"
        event.title = data.title

    if data.description is not None and data.description != event.description:
        changes["description"] = "Event description updated"
        event.description = data.description

    if data.location is not None and data.location != event.location:
        changes["location"] = f"{event.location or 'N/A'} -> {data.location}"
        event.location = data.location

    if data.starts_at is not None and data.starts_at != event.starts_at:
        changes["starts_at"] = f"{event.starts_at.isoformat()} -> {data.starts_at.isoformat()}"
        event.starts_at = data.starts_at

    if data.ends_at is not None:
        if data.ends_at <= proposed_starts_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ends_at must be after starts_at",
            )
        if data.ends_at != event.ends_at:
            changes["ends_at"] = f"{event.ends_at.isoformat()} -> {data.ends_at.isoformat()}"
        event.ends_at = data.ends_at

    if data.price_cents is not None and data.price_cents != event.price_cents:
        changes["price_cents"] = f"{event.price_cents} -> {data.price_cents}"
        event.price_cents = data.price_cents

    if data.total_tickets is not None:
        booked_tickets = event.total_tickets - event.available_tickets
        if data.total_tickets < booked_tickets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reduce total tickets below already booked quantity ({booked_tickets})",
            )
        if data.total_tickets != event.total_tickets:
            changes["total_tickets"] = f"{event.total_tickets} -> {data.total_tickets}"
        event.total_tickets = data.total_tickets
        event.available_tickets = data.total_tickets - booked_tickets

    # 1. Commit
    db.commit()
    db.refresh(event)

    # 2. Post-commit Celery enqueueing
    if changes and event.is_published:
        send_event_update_notifications.delay(
            event_id=str(event.id),
            changes=changes,
        )

    return event


def toggle_publish_event(
    db: Session,
    event_id: uuid.UUID,
    organizer_id: uuid.UUID,
    publish: bool,
) -> Event:
    """Publish or unpublish an event."""
    event = get_event_by_id(db, event_id)
    if event.organizer_id != organizer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only publish/unpublish events you organized",
        )
    event.is_published = publish
    db.commit()
    db.refresh(event)
    return event


def delete_event(
    db: Session,
    event_id: uuid.UUID,
    organizer_id: uuid.UUID,
) -> None:
    """Delete an event owned by the organizer."""
    event = get_event_by_id(db, event_id)
    if event.organizer_id != organizer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete events you organized",
        )
    db.delete(event)
    db.commit()
