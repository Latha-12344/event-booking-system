"""
Event router: /api/v1/events
"""
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_organizer
from app.database import get_db
from app.models.user import User
from app.schemas.event import (
    EventCreate,
    EventListResponse,
    EventPatch,
    EventResponse,
    EventUpdate,
)
from app.services import event_service

router = APIRouter(prefix="/events", tags=["events"])


@router.post(
    "/",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new event (Organizer only)",
)
def create_event(
    data: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
) -> EventResponse:
    event = event_service.create_event(db, data, current_user.id)
    return EventResponse.model_validate(event)


@router.get(
    "/",
    response_model=EventListResponse,
    summary="List all published events (Public)",
)
def list_events(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search keyword in title or description"),
    location: Optional[str] = Query(None, description="Filter by location"),
    date_from: Optional[datetime] = Query(None, description="Filter events starting on or after"),
    date_to: Optional[datetime] = Query(None, description="Filter events starting on or before"),
    db: Session = Depends(get_db),
) -> EventListResponse:
    return event_service.list_published_events(
        db=db,
        page=page,
        size=size,
        search=search,
        location=location,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    summary="Get single event details (Public)",
)
def get_event(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EventResponse:
    event = event_service.get_event_by_id(db, event_id)
    return EventResponse.model_validate(event)


@router.put(
    "/{event_id}",
    response_model=EventResponse,
    summary="Full update of event (Organizer only, owner)",
)
def update_event(
    event_id: uuid.UUID,
    data: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
) -> EventResponse:
    event = event_service.update_event(db, event_id, data, current_user.id)
    return EventResponse.model_validate(event)


@router.patch(
    "/{event_id}",
    response_model=EventResponse,
    summary="Partial update of event (Organizer only, owner)",
)
def patch_event(
    event_id: uuid.UUID,
    data: EventPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
) -> EventResponse:
    event = event_service.patch_event(db, event_id, data, current_user.id)
    return EventResponse.model_validate(event)


@router.patch(
    "/{event_id}/publish",
    response_model=EventResponse,
    summary="Publish or unpublish an event (Organizer only, owner)",
)
def toggle_publish(
    event_id: uuid.UUID,
    is_published: bool = Query(True, description="Target publish state"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
) -> EventResponse:
    event = event_service.toggle_publish_event(db, event_id, current_user.id, is_published)
    return EventResponse.model_validate(event)


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an event (Organizer only, owner)",
)
def delete_event(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_organizer),
) -> None:
    event_service.delete_event(db, event_id, current_user.id)
