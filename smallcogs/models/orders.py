"""
Ordering/Agentic Models

Smart order recommendations based on inventory usage and trends.
Fully configurable - no hardcoded business rules.
"""

from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from enum import Enum


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

    # Issues
    warnings: List[str] = Field(default_factory=list)


class RecommendationRun(BaseModel):
    """A complete recommendation run."""
    run_id: str
    dataset_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Config used
    targets: OrderTargets
    constraints: OrderConstraints

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
