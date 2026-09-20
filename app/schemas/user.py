"""
Pydantic schemas for User endpoints.

hashed_password is NEVER included in any response schema.
"""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, field_validator


class UserRegister(BaseModel):
    """Request body for POST /auth/register."""
    email: EmailStr
    password: str
    full_name: str
    role: Literal["organizer", "customer"] = "customer"

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("full_name cannot be blank")
        return v


class UserLogin(BaseModel):
    """Request body for POST /auth/login."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response from POST /auth/login."""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Safe user representation — never includes hashed_password."""
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
