"""Common types used across the inventory system."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# ============================================================================
# Status Enums (these are system states, not business data)
# ============================================================================

class ReasonCode(str, Enum):
    """Order recommendation reason codes."""
    STOCKOUT_RISK = "STOCKOUT_RISK"
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    OVERSTOCK = "OVERSTOCK"
    BELOW_TARGET = "BELOW_TARGET"
    REBALANCE = "REBALANCE"
    VENDOR_MINIMUM = "VENDOR_MINIMUM"
    SEASONAL = "SEASONAL"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    DATA_QUALITY = "DATA_QUALITY"
    NO_ORDER = "NO_ORDER"


class Confidence(str, Enum):
    """Confidence level for recommendations."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SessionStatus(str, Enum):
    """Voice counting session status."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TrendDirection(str, Enum):
    """Usage trend direction."""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


# ============================================================================
# Common Value Objects
# ============================================================================

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


class SortParams(BaseModel):
    """Sorting parameters."""
    sort_by: str = "created_at"
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class PaginatedResponse(BaseModel):
    """Base class for paginated responses."""
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool
