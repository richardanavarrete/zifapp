"""Common types used across smallCOGS."""

from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class TrendDirection(str, Enum):
    """Usage trend direction."""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class Confidence(str, Enum):
    """Confidence level."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SessionStatus(str, Enum):
    """Voice counting session status."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DateRange(BaseModel):
    """A date range."""
    start: datetime
    end: datetime


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
