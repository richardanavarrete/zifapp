"""
Inventory Data Models

Generic inventory models that work with any structured spreadsheet.
No hardcoded categories, vendors, or business-specific logic.
"""

from datetime import datetime, date
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, field_validator, computed_field
import pandas as pd

from houndcogs.models.common import TrendDirection


# ============================================================================
# Core Data Models
# ============================================================================

class Item(BaseModel):
    """
    An inventory item.

    Designed to be generic - category and vendor are user-provided strings,
    not hardcoded enums.
    """

    item_id: str = Field(..., description="Unique identifier (can be auto-generated or from sheet)")
    name: str = Field(..., description="Item name as it appears in the spreadsheet")

    # Optional categorization (user-provided, not enforced)
    category: Optional[str] = Field(default=None, description="Category/group from spreadsheet")
    subcategory: Optional[str] = Field(default=None, description="Sub-category if available")
    vendor: Optional[str] = Field(default=None, description="Vendor/supplier name")

    # Optional metadata
    sku: Optional[str] = Field(default=None, description="SKU or product code")
    unit_cost: Optional[float] = Field(default=None, ge=0, description="Cost per unit")
    unit_of_measure: str = Field(default="unit", description="Unit type (bottle, case, each, etc.)")
    location: Optional[str] = Field(default=None, description="Storage location")

    # For scale-based counting
    full_weight_grams: Optional[float] = Field(default=None)
    empty_weight_grams: Optional[float] = Field(default=None)

    # Custom fields from the spreadsheet (flexible schema)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class Record(BaseModel):
    """
    A single inventory record (one row from the spreadsheet).

    Represents a point-in-time count for an item.
    """

    record_id: Optional[str] = Field(default=None, description="Auto-generated if not provided")
    item_id: str

    # Core data (at minimum, we need date and either on_hand or count)
    record_date: date = Field(..., description="Date of this record")
    on_hand: float = Field(..., description="Quantity on hand")

    # Usage is computed or provided
    usage: Optional[float] = Field(default=None, description="Usage since last count")

    # Metadata
    period_name: Optional[str] = Field(default=None, description="Week name, period label, etc.")
    source_file: Optional[str] = Field(default=None)

    # Custom fields
    custom_fields: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("usage")
    @classmethod
    def allow_negative_usage(cls, v: Optional[float]) -> Optional[float]:
        """Allow negative usage - it indicates data quality issues to surface."""
        return v


# ============================================================================
# Computed Analytics Models
# ============================================================================

class ItemStats(BaseModel):
    """
    Computed statistics for an item based on historical records.

    These are calculated from the raw data, not stored.
    """

    item_id: str
    item_name: str
    category: Optional[str] = None

    # Current state
    current_on_hand: float = 0.0
    last_count_date: Optional[date] = None

    # Usage statistics
    total_usage: float = 0.0
    avg_usage: float = 0.0
    avg_usage_recent: float = Field(default=0.0, description="Recent period average (e.g., 4 weeks)")
    min_usage: float = 0.0
    max_usage: float = 0.0

    # Derived metrics
    weeks_on_hand: Optional[float] = Field(default=None, description="Current / avg_usage")
    days_on_hand: Optional[float] = Field(default=None, description="Current / (avg_usage/7)")

    # Trend analysis
    trend_direction: TrendDirection = TrendDirection.STABLE
    trend_percent_change: float = Field(default=0.0, description="% change recent vs historical")

    # Volatility
    std_deviation: float = 0.0
    coefficient_of_variation: float = Field(default=0.0, description="CV = std/mean")

    # Data quality
    record_count: int = 0
    has_negative_usage: bool = False
    has_gaps: bool = False
    data_quality_score: float = Field(default=1.0, ge=0, le=1, description="1.0 = perfect data")


class UsageTrend(BaseModel):
    """Usage data point for trend visualization."""

    date: date
    usage: float
    on_hand: float
    period_name: Optional[str] = None


class ItemDetail(BaseModel):
    """
    Complete item detail including stats and history.

    Used for the detail view when clicking on an item.
    """

    item: Item
    stats: ItemStats
    history: List[UsageTrend] = Field(default_factory=list)

    # Rolling averages for chart
    rolling_avg_4wk: List[float] = Field(default_factory=list)
    rolling_avg_8wk: List[float] = Field(default_factory=list)


# ============================================================================
# Dataset Models
# ============================================================================

class Dataset(BaseModel):
    """
    A complete inventory dataset.

    Contains items and their historical records from uploaded file(s).
    """

    dataset_id: str
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Source info
    source_files: List[str] = Field(default_factory=list)

    # Date range of data
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None

    # Counts
    items_count: int = 0
    records_count: int = 0
    periods_count: int = Field(default=0, description="Number of distinct date periods")

    # Discovered schema
    categories: List[str] = Field(default_factory=list, description="Unique categories found")
    vendors: List[str] = Field(default_factory=list, description="Unique vendors found")

    # The actual data
    items: Dict[str, Item] = Field(default_factory=dict)
    records: List[Record] = Field(default_factory=list)

    # Column mapping used during import
    column_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Maps spreadsheet columns to our fields"
    )

    def get_item(self, item_id: str) -> Optional[Item]:
        return self.items.get(item_id)

    def get_item_records(self, item_id: str) -> List[Record]:
        return [r for r in self.records if r.item_id == item_id]

    def get_items_by_category(self, category: str) -> List[Item]:
        return [item for item in self.items.values() if item.category == category]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert records to pandas DataFrame for analysis."""
        if not self.records:
            return pd.DataFrame()
        return pd.DataFrame([r.model_dump() for r in self.records])

    class Config:
        arbitrary_types_allowed = True


class DatasetSummary(BaseModel):
    """Summary info for dataset listing."""

    dataset_id: str
    name: str
    created_at: datetime
    updated_at: datetime
    items_count: int
    records_count: int
    periods_count: int
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    categories: List[str] = Field(default_factory=list)
    source_files: List[str] = Field(default_factory=list)


# ============================================================================
# Upload/Import Models
# ============================================================================

class ColumnMapping(BaseModel):
    """
    Maps spreadsheet columns to our data fields.

    Users can configure this during upload to handle different sheet formats.
    """

    # Required columns
    item_name: str = Field(..., description="Column containing item names")
    on_hand: str = Field(..., description="Column containing on-hand quantity")

    # Date handling (one of these)
    date_column: Optional[str] = Field(default=None, description="Column containing dates")
    date_from_filename: bool = Field(default=False, description="Parse date from filename")
    date_from_sheet_name: bool = Field(default=False, description="Parse date from sheet name")

    # Optional columns
    usage: Optional[str] = Field(default=None, description="Column containing usage")
    category: Optional[str] = Field(default=None)
    vendor: Optional[str] = Field(default=None)
    sku: Optional[str] = Field(default=None)
    unit_cost: Optional[str] = Field(default=None)
    location: Optional[str] = Field(default=None)

    # Processing options
    skip_rows: int = Field(default=0, description="Rows to skip at top")
    header_row: int = Field(default=0, description="Row containing headers (0-indexed)")


class UploadConfig(BaseModel):
    """Configuration for file upload processing."""

    # File handling
    compute_usage: bool = Field(
        default=True,
        description="Compute usage from on_hand changes if not provided"
    )
    merge_with_existing: bool = Field(
        default=False,
        description="Merge into existing dataset vs create new"
    )
    existing_dataset_id: Optional[str] = Field(
        default=None,
        description="Dataset to merge into"
    )

    # Column mapping (if not provided, will attempt auto-detect)
    column_mapping: Optional[ColumnMapping] = None

    # Data cleaning
    trim_whitespace: bool = True
    remove_empty_rows: bool = True
    remove_total_rows: bool = Field(default=True, description="Remove rows like 'TOTAL'")


class UploadResult(BaseModel):
    """Result of uploading an inventory file."""

    success: bool
    dataset_id: str
    filename: str

    # Counts
    items_count: int
    records_count: int
    periods_count: int

    # Data range
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None

    # Schema discovered
    categories_found: List[str] = Field(default_factory=list)
    vendors_found: List[str] = Field(default_factory=list)
    columns_detected: List[str] = Field(default_factory=list)

    # Column mapping used
    column_mapping: Dict[str, str] = Field(default_factory=dict)

    # Issues
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Filter/Query Models
# ============================================================================

class ItemFilter(BaseModel):
    """Filters for querying items."""

    search: Optional[str] = Field(default=None, description="Search in name")
    categories: Optional[List[str]] = Field(default=None, description="Filter by categories")
    vendors: Optional[List[str]] = Field(default=None, description="Filter by vendors")

    # Usage filters
    min_usage: Optional[float] = None
    max_usage: Optional[float] = None
    min_on_hand: Optional[float] = None
    max_on_hand: Optional[float] = None

    # Status filters
    low_stock: bool = Field(default=False, description="Below threshold")
    high_usage: bool = Field(default=False, description="Above average usage")
    has_issues: bool = Field(default=False, description="Has data quality issues")

    # Trend filters
    trending_up: bool = False
    trending_down: bool = False


class GroupBy(BaseModel):
    """Grouping options for analytics."""

    field: str = Field(..., description="Field to group by: category, vendor, location")
    include_items: bool = Field(default=False, description="Include item details in groups")
