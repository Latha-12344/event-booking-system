"""
Pydantic schemas for Booking endpoints.

- quantity must be >= 1
- total_cents is calculated server-side (not supplied by the client)
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class BookingCreate(BaseModel):
    """Request body for POST /bookings/."""
    event_id: uuid.UUID
    quantity: int = 1

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("quantity must be at least 1")
        return v


class BookingResponse(BaseModel):
    """Booking representation returned to clients."""
    id: uuid.UUID
    event_id: uuid.UUID
    customer_id: uuid.UUID
    quantity: int
    status: str
    total_cents: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class BookingListResponse(BaseModel):
    """Paginated list of bookings."""
    items: list[BookingResponse]
    total: int
    page: int
    size: int
    pages: int
