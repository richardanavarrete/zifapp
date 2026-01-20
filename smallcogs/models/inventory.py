"""
Inventory Data Models

Generic models that work with any structured spreadsheet.
No hardcoded categories, vendors, or business-specific logic.
"""

from datetime import datetime, date
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
import pandas as pd

from smallcogs.models.common import TrendDirection


class Item(BaseModel):
    """An inventory item - fully generic."""

    item_id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Item name from spreadsheet")

    # Optional categorization (user-provided strings, not enums)
    category: Optional[str] = None
    subcategory: Optional[str] = None
    vendor: Optional[str] = None

    # Optional metadata
    sku: Optional[str] = None
    unit_cost: Optional[float] = Field(default=None, ge=0)
    unit_of_measure: str = Field(default="unit")
    location: Optional[str] = None

    # Flexible custom fields
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class Record(BaseModel):
    """A single inventory record (one row from spreadsheet)."""

    record_id: Optional[str] = None
    item_id: str
    record_date: date
    on_hand: float
    usage: Optional[float] = None
    period_name: Optional[str] = None
    source_file: Optional[str] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class ItemStats(BaseModel):
    """Computed statistics for an item."""

    item_id: str
    item_name: str
    category: Optional[str] = None

    # Current state
    current_on_hand: float = 0.0
    last_count_date: Optional[date] = None

    # Usage statistics
    total_usage: float = 0.0
    avg_usage: float = 0.0
    avg_usage_recent: float = 0.0
    min_usage: float = 0.0
    max_usage: float = 0.0

    # Derived metrics
    weeks_on_hand: Optional[float] = None
    days_on_hand: Optional[float] = None

    # Trend
    trend_direction: TrendDirection = TrendDirection.STABLE
    trend_percent_change: float = 0.0

    # Volatility
    std_deviation: float = 0.0
    coefficient_of_variation: float = 0.0

    # Data quality
    record_count: int = 0
    has_negative_usage: bool = False
    has_gaps: bool = False


class UsageTrend(BaseModel):
    """Usage data point for charts."""
    date: date
    usage: float
    on_hand: float
    period_name: Optional[str] = None


class ItemDetail(BaseModel):
    """Complete item detail for drill-down view."""
    item: Item
    stats: ItemStats
    history: List[UsageTrend] = Field(default_factory=list)
    rolling_avg_4wk: List[float] = Field(default_factory=list)


class Dataset(BaseModel):
    """A complete inventory dataset."""

    dataset_id: str
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Source info
    source_files: List[str] = Field(default_factory=list)
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None

    # Counts
    items_count: int = 0
    records_count: int = 0
    periods_count: int = 0

    # Discovered schema (from the data itself)
    categories: List[str] = Field(default_factory=list)
    vendors: List[str] = Field(default_factory=list)

    # Data
    items: Dict[str, Item] = Field(default_factory=dict)
    records: List[Record] = Field(default_factory=list)

    def get_item(self, item_id: str) -> Optional[Item]:
        return self.items.get(item_id)

    def get_item_records(self, item_id: str) -> List[Record]:
        return [r for r in self.records if r.item_id == item_id]

    def to_dataframe(self) -> pd.DataFrame:
        if not self.records:
            return pd.DataFrame()
        return pd.DataFrame([r.model_dump() for r in self.records])

    class Config:
        arbitrary_types_allowed = True


class DatasetSummary(BaseModel):
    """Summary for dataset listing."""
    dataset_id: str
    name: str
    created_at: datetime
    items_count: int
    records_count: int
    periods_count: int
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    categories: List[str] = Field(default_factory=list)


class UploadResult(BaseModel):
    """Result of file upload."""
    success: bool
    dataset_id: str
    filename: str
    items_count: int
    records_count: int
    periods_count: int
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    categories_found: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ItemFilter(BaseModel):
    """Filters for querying items."""
    search: Optional[str] = None
    categories: Optional[List[str]] = None
    vendors: Optional[List[str]] = None
    min_on_hand: Optional[float] = None
    max_on_hand: Optional[float] = None
    trending_up: bool = False
    trending_down: bool = False
    has_issues: bool = False
