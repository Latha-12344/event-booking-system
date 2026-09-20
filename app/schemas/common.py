"""
Common/shared Pydantic schemas.
"""
from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str


class PaginationParams(BaseModel):
    """Common pagination parameters."""
    page: int = 1
    size: int = 20

    model_config = {"from_attributes": True}

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
