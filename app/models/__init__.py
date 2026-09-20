"""
Models package — imports all models so Alembic autogenerate can discover them.
"""
from app.models.user import User  # noqa: F401
from app.models.event import Event  # noqa: F401
from app.models.booking import Booking  # noqa: F401

__all__ = ["User", "Event", "Booking"]
