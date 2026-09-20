"""
Bookings router: /api/v1/bookings
"""
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_customer
from app.database import get_db
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingListResponse, BookingResponse
from app.services import booking_service

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post(
    "/",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book tickets for an event (Customer only)",
)
def create_booking(
    data: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_customer),
) -> BookingResponse:
    booking = booking_service.create_booking(db, data, current_user)
    return BookingResponse.model_validate(booking)


@router.get(
    "/",
    response_model=BookingListResponse,
    summary="List current customer's bookings",
)
def list_my_bookings(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_customer),
) -> BookingListResponse:
    return booking_service.list_customer_bookings(
        db=db,
        customer_id=current_user.id,
        page=page,
        size=size,
    )


@router.get(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Get single booking details (Customer owner only)",
)
def get_booking(
    booking_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_customer),
) -> BookingResponse:
    booking = booking_service.get_booking_by_id(db, booking_id, current_user.id)
    return BookingResponse.model_validate(booking)


@router.delete(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Cancel a booking and release tickets (Customer owner only)",
)
def cancel_booking(
    booking_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_customer),
) -> BookingResponse:
    booking = booking_service.cancel_booking(db, booking_id, current_user.id)
    return BookingResponse.model_validate(booking)
