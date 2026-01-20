"""Common types and enums used across HoundCOGS."""

from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Category(str, Enum):
    """Product categories."""
    WHISKEY = "Whiskey"
    VODKA = "Vodka"
    GIN = "Gin"
    TEQUILA = "Tequila"
    RUM = "Rum"
    SCOTCH = "Scotch"
    BRANDY = "Brandy"
    WELL = "Well"
    LIQUEUR = "Liqueur"
    CORDIALS = "Cordials"
    WINE = "Wine"
    DRAFT_BEER = "Draft Beer"
    BOTTLED_BEER = "Bottled Beer"
    JUICE = "Juice"
    BAR_CONSUMABLES = "Bar Consumables"
    UNKNOWN = "Unknown"


class Vendor(str, Enum):
    """Known vendors."""
    BREAKTHRU = "Breakthru"
    SOUTHERN = "Southern"
    RNDC = "RNDC"
    CRESCENT = "Crescent"
    HENSLEY = "Hensley"
    UNKNOWN = "Unknown"


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


class DateRange(BaseModel):
    """A date range."""
    start: datetime
    end: datetime


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=200)


class SortParams(BaseModel):
    """Sorting parameters."""
    sort_by: str = "created_at"
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
