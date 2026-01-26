"""
Ordering/Agentic Models

Smart order recommendations based on inventory usage and trends.
Fully configurable - no hardcoded business rules.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReasonCode(str, Enum):
    """Why an order is recommended."""
    STOCKOUT_RISK = "stockout_risk"
    LOW_STOCK = "low_stock"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    BELOW_TARGET = "below_target"
    OVERSTOCK = "overstock"
    REORDER_POINT = "reorder_point"
    MANUAL = "manual"
    DATA_QUALITY = "data_quality"
    FORECAST_ADJUSTED = "forecast_adjusted"


class SalesForecast(BaseModel):
    """
    Sales forecast for order recommendations.

    Users can input expected sales to adjust ordering quantities.
    Three ways to use:
    1. percent_change: Simply say "+20%" and all orders scale up 20%
    2. expected_total_sales + historical_avg_total_sales: Compare expected vs historical
    3. by_category + historical_by_category: Category-level comparison

    The system computes a multiplier and applies it to order quantities.
    """
    # Option 1: Simple percentage change (easiest to use)
    # Positive = expect more sales, Negative = expect less
    percent_change: Optional[float] = Field(
        default=None,
        description="Expected % change from historical average (e.g., 20 for +20%, -10 for -10%)"
    )

    # Option 2: Expected total sales with historical comparison
    expected_total_sales: Optional[float] = Field(
        default=None,
        ge=0,
        description="Expected total sales for the forecast period"
    )
    historical_avg_total_sales: Optional[float] = Field(
        default=None,
        ge=0,
        description="Historical average total sales per week (for computing multiplier)"
    )

    # Option 3: Expected sales by category (more granular control)
    by_category: Dict[str, float] = Field(
        default_factory=dict,
        description="Expected sales by category name (e.g., {'Liquor': 15000, 'Wine': 5000})"
    )
    historical_by_category: Dict[str, float] = Field(
        default_factory=dict,
        description="Historical average sales by category (e.g., {'Liquor': 12000, 'Wine': 4000})"
    )

    # Forecast period in weeks (how far ahead are we forecasting)
    forecast_weeks: float = Field(
        default=1.0,
        gt=0,
        description="Number of weeks the forecast covers"
    )

    # Notes for tracking
    notes: Optional[str] = Field(
        default=None,
        description="Optional notes (e.g., 'Holiday weekend expected')"
    )

    def get_multiplier(self, category: Optional[str] = None) -> float:
        """
        Compute the forecast multiplier for ordering.

        Returns a value like 1.2 for +20% expected sales.
        """
        # Priority 1: Direct percent change
        if self.percent_change is not None:
            return 1.0 + (self.percent_change / 100.0)

        # Priority 2: Category-specific comparison
        if category and category in self.by_category and category in self.historical_by_category:
            historical = self.historical_by_category[category]
            if historical > 0:
                return self.by_category[category] / historical

        # Priority 3: Total sales comparison
        if self.expected_total_sales is not None and self.historical_avg_total_sales:
            if self.historical_avg_total_sales > 0:
                return self.expected_total_sales / self.historical_avg_total_sales

        # No forecast adjustment
        return 1.0


class Confidence(str, Enum):
    """Confidence level in recommendation."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class OrderTargets(BaseModel):
    """
    User-defined inventory targets.

    No defaults - each business sets their own.
    """
    # Default weeks of stock to maintain
    default_weeks: float = Field(default=2.0, ge=0)

    # Category-specific targets (user defines categories)
    by_category: Dict[str, float] = Field(
        default_factory=dict,
        description="category_name -> target_weeks"
    )

    # Item-specific overrides
    by_item: Dict[str, float] = Field(
        default_factory=dict,
        description="item_id -> target_weeks"
    )

    # Items to never recommend
    exclude_items: List[str] = Field(default_factory=list)

    def get_target(self, item_id: str, category: Optional[str] = None) -> float:
        """Get target weeks for an item."""
        if item_id in self.exclude_items:
            return 0.0
        if item_id in self.by_item:
            return self.by_item[item_id]
        if category and category in self.by_category:
            return self.by_category[category]
        return self.default_weeks


class OrderConstraints(BaseModel):
    """User-defined ordering constraints."""

    # Budget
    max_spend: Optional[float] = Field(default=None, ge=0)
    max_items: Optional[int] = Field(default=None, ge=0)

    # Per-vendor limits (user defines vendor names)
    vendor_minimums: Dict[str, float] = Field(default_factory=dict)
    vendor_maximums: Dict[str, float] = Field(default_factory=dict)

    # Thresholds for alerts
    low_stock_weeks: float = Field(default=1.0, ge=0)
    overstock_weeks: float = Field(default=8.0, ge=0)


class Recommendation(BaseModel):
    """A single order recommendation."""
    item_id: str
    item_name: str
    category: Optional[str] = None
    vendor: Optional[str] = None

    # Current state
    on_hand: float
    avg_usage: float
    weeks_on_hand: Optional[float] = None

    # Recommendation
    suggested_qty: int = Field(..., ge=0)
    unit_cost: Optional[float] = None
    total_cost: Optional[float] = None

    # Reasoning
    reason: ReasonCode
    reason_text: str
    confidence: Confidence

    # Context
    trend_direction: Optional[str] = None  # up, down, stable
    trend_pct: Optional[float] = None

    # Forecast adjustment
    forecast_multiplier: Optional[float] = Field(
        default=None,
        description="Multiplier applied due to sales forecast (e.g., 1.2 = +20%)"
    )
    base_suggested_qty: Optional[int] = Field(
        default=None,
        description="Suggested qty before forecast adjustment"
    )

    # Issues
    warnings: List[str] = Field(default_factory=list)


class ForecastSummary(BaseModel):
    """Summary of forecast applied to recommendations."""
    forecast_applied: bool = False
    historical_avg_sales: Optional[float] = None
    expected_sales: Optional[float] = None
    overall_multiplier: float = 1.0
    by_category_multipliers: Dict[str, float] = Field(default_factory=dict)
    notes: Optional[str] = None


class RecommendationRun(BaseModel):
    """A complete recommendation run."""
    run_id: str
    dataset_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Config used
    targets: OrderTargets
    constraints: OrderConstraints

    # Sales Forecast
    forecast: Optional[SalesForecast] = None
    forecast_summary: Optional[ForecastSummary] = None

    # Results
    recommendations: List[Recommendation]

    # Summary
    total_items: int = 0
    total_spend: float = 0.0
    low_stock_count: int = 0
    overstock_count: int = 0

    # By group
    by_vendor: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    by_category: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    by_reason: Dict[str, int] = Field(default_factory=dict)

    # Issues
    warnings: List[str] = Field(default_factory=list)
    data_issues: List[Dict[str, Any]] = Field(default_factory=list)

    # Status
    status: str = "completed"  # completed, approved, exported


class RecommendRequest(BaseModel):
    """Request for recommendations."""
    dataset_id: str
    targets: Optional[OrderTargets] = None
    constraints: Optional[OrderConstraints] = None

    # Sales Forecast - adjust orders based on expected sales
    forecast: Optional[SalesForecast] = Field(
        default=None,
        description="Sales forecast to adjust order quantities"
    )

    # Filters
    categories: Optional[List[str]] = None
    vendors: Optional[List[str]] = None
    exclude_items: Optional[List[str]] = None

    # Options
    include_overstock: bool = False
    min_confidence: Confidence = Confidence.LOW


class ApprovalRequest(BaseModel):
    """Approve/modify recommendations."""
    run_id: str
    approved: Dict[str, int] = Field(
        default_factory=dict,
        description="item_id -> approved_qty"
    )
    rejected: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class OrderExport(BaseModel):
    """Exported order for copy/paste or download."""
    run_id: str
    exported_at: datetime = Field(default_factory=datetime.utcnow)

    # Data
    items: List[Dict[str, Any]]
    total_items: int
    total_spend: float

    # Formats
    csv_text: Optional[str] = None
    summary_text: Optional[str] = None

    # Grouped
    by_vendor: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
