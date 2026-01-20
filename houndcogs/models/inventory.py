"""Inventory data models."""

from datetime import datetime, date
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, field_validator
import pandas as pd

from houndcogs.models.common import Category, Vendor


class Item(BaseModel):
    """An inventory item."""

    item_id: str = Field(..., description="Unique identifier, e.g., 'WHISKEY Buffalo Trace'")
    display_name: str = Field(..., description="Human-readable name")
    category: Category = Field(default=Category.UNKNOWN)
    vendor: Vendor = Field(default=Vendor.UNKNOWN)
    location: Optional[str] = Field(default=None, description="Physical storage location")
    unit_cost: float = Field(default=0.0, ge=0)
    unit_of_measure: str = Field(default="bottle")
    full_weight_grams: Optional[float] = Field(default=None, description="Weight when full (for scale counting)")
    empty_weight_grams: Optional[float] = Field(default=None, description="Weight when empty")

    class Config:
        use_enum_values = True


class WeeklyRecord(BaseModel):
    """A single week's inventory record for an item."""

    item_id: str
    week_date: date
    on_hand: float = Field(..., description="Ending inventory count")
    usage: float = Field(..., description="Units used during the week")
    week_name: Optional[str] = Field(default=None, description="Human-readable week name")
    source_file: Optional[str] = Field(default=None, description="Source file this came from")

    @field_validator("usage")
    @classmethod
    def validate_usage(cls, v: float) -> float:
        """Flag negative usage but don't reject it (data quality issue)."""
        # We allow negative usage as it indicates data quality issues
        # that should be surfaced to the user
        return v


class ItemFeatures(BaseModel):
    """Computed features for an item (rolling averages, trends, etc.)."""

    item_id: str

    # Rolling averages
    avg_weekly_usage_ytd: float = Field(default=0.0)
    avg_weekly_usage_10wk: float = Field(default=0.0)
    avg_weekly_usage_4wk: float = Field(default=0.0)
    avg_weekly_usage_2wk: float = Field(default=0.0)

    # Current state
    current_on_hand: float = Field(default=0.0)
    weeks_on_hand: float = Field(default=0.0, description="Current inventory / avg usage")

    # Volatility and trends
    coefficient_of_variation: float = Field(default=0.0, description="Std dev / mean")
    trend_direction: str = Field(default="stable", description="up, down, or stable")
    trend_strength: float = Field(default=0.0, ge=0, le=1)

    # Data quality flags
    has_negative_usage: bool = Field(default=False)
    has_data_gaps: bool = Field(default=False)
    weeks_of_data: int = Field(default=0)


class InventoryDataset(BaseModel):
    """A complete inventory dataset with items and records."""

    dataset_id: str
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Metadata
    source_files: List[str] = Field(default_factory=list)
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    items_count: int = 0
    weeks_count: int = 0

    # Items dictionary (item_id -> Item)
    items: Dict[str, Item] = Field(default_factory=dict)

    # Records stored as list (will be converted to DataFrame for processing)
    records: List[WeeklyRecord] = Field(default_factory=list)

    def get_item(self, item_id: str) -> Optional[Item]:
        """Get an item by ID."""
        return self.items.get(item_id)

    def get_item_records(self, item_id: str) -> List[WeeklyRecord]:
        """Get all records for a specific item."""
        return [r for r in self.records if r.item_id == item_id]

    def get_unique_items(self) -> List[str]:
        """Get list of unique item IDs."""
        return list(self.items.keys())

    def to_dataframe(self) -> pd.DataFrame:
        """Convert records to pandas DataFrame."""
        if not self.records:
            return pd.DataFrame()
        return pd.DataFrame([r.model_dump() for r in self.records])

    class Config:
        arbitrary_types_allowed = True


class DatasetSummary(BaseModel):
    """Summary info for a dataset (for listing)."""

    dataset_id: str
    name: str
    created_at: datetime
    items_count: int
    weeks_count: int
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    source_files: List[str] = Field(default_factory=list)


class UploadResult(BaseModel):
    """Result of uploading an inventory file."""

    dataset_id: str
    filename: str
    items_count: int
    weeks_count: int
    date_range: Optional[Dict[str, str]] = None
    created_at: datetime
    warnings: List[str] = Field(default_factory=list)
