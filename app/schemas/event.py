"""
Pydantic schemas for Event endpoints.

Monetary values use price_cents (integer) throughout.
A helper property price_display converts to a human-readable decimal string.
"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator


class EventCreate(BaseModel):
    """Request body for POST /events/."""
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    total_tickets: int
    price_cents: int = 0  # free by default

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title cannot be blank")
        return v

    @field_validator("total_tickets")
    @classmethod
    def total_tickets_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("total_tickets must be at least 1")
        return v

    @field_validator("price_cents")
    @classmethod
    def price_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("price_cents cannot be negative")
        return v

    @model_validator(mode="after")
    def end_after_start(self) -> "EventCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class EventUpdate(BaseModel):
    """Request body for PUT /events/{id} — full update."""
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    starts_at: datetime
    ends_at: datetime
    total_tickets: int
    price_cents: int

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title cannot be blank")
        return v

    @field_validator("total_tickets")
    @classmethod
    def total_tickets_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("total_tickets must be at least 1")
        return v

    @field_validator("price_cents")
    @classmethod
    def price_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("price_cents cannot be negative")
        return v

    @model_validator(mode="after")
    def end_after_start(self) -> "EventUpdate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class EventPatch(BaseModel):
    """Request body for PATCH /events/{id} — partial update."""
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    total_tickets: Optional[int] = None
    price_cents: Optional[int] = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("title cannot be blank")
        return v

    @field_validator("total_tickets")
    @classmethod
    def total_tickets_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError("total_tickets must be at least 1")
        return v

    @field_validator("price_cents")
    @classmethod
    def price_non_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("price_cents cannot be negative")
        return v


class EventResponse(BaseModel):
    """Event representation returned to clients."""
    id: uuid.UUID
    organizer_id: uuid.UUID
    title: str
    description: Optional[str]
    location: Optional[str]
    starts_at: datetime
    ends_at: datetime
    total_tickets: int
    available_tickets: int
    price_cents: int
    is_published: bool
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    """Paginated list of events."""
    items: list[EventResponse]
    total: int
    page: int
    size: int
    pages: int
