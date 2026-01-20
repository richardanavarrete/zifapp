"""
Order Recommendation Data Models

Generic models for inventory ordering recommendations.
All business rules (targets, constraints) are user-configurable.
"""

from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field

from houndcogs.models.common import ReasonCode, Confidence


# ============================================================================
# Configuration Models (User-Defined)
# ============================================================================

class OrderTargets(BaseModel):
    """
    Target inventory levels - fully user-configurable.

    No defaults - user must define their own targets based on their business.
    """

    # Default target weeks (user sets their own)
    default_weeks: float = Field(
        default=2.0,
        ge=0,
        description="Default weeks of inventory to maintain"
    )

    # Category-specific targets (user-defined categories)
    weeks_by_category: Dict[str, float] = Field(
        default_factory=dict,
        description="Target weeks by category name"
    )

    # Item-specific overrides
    item_overrides: Dict[str, float] = Field(
        default_factory=dict,
        description="item_id -> target weeks"
    )

    # Items to never order
    never_order: List[str] = Field(
        default_factory=list,
        description="Item IDs to exclude from recommendations"
    )

    def get_target_weeks(self, item_id: str, category: Optional[str] = None) -> float:
        """Get target weeks for an item."""
        if item_id in self.never_order:
            return 0.0
        if item_id in self.item_overrides:
            return self.item_overrides[item_id]
        if category and category in self.weeks_by_category:
            return self.weeks_by_category[category]
        return self.default_weeks


class OrderConstraints(BaseModel):
    """
    Constraints on order generation - fully user-configurable.
    """

    # Budget constraints
    max_total_spend: Optional[float] = Field(
        default=None,
        ge=0,
        description="Maximum total order value"
    )
    max_items: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum number of items to order"
    )

    # Vendor constraints (user-defined vendor names)
    vendor_minimums: Dict[str, float] = Field(
        default_factory=dict,
        description="Minimum order value per vendor"
    )
    vendor_maximums: Dict[str, float] = Field(
        default_factory=dict,
        description="Maximum order value per vendor"
    )
    vendor_item_limits: Dict[str, int] = Field(
        default_factory=dict,
        description="Maximum items per vendor order"
    )

    # Thresholds
    low_stock_threshold_weeks: float = Field(
        default=1.0,
        ge=0,
        description="Weeks on hand below which to flag as low stock"
    )
    overstock_threshold_weeks: float = Field(
        default=8.0,
        ge=0,
        description="Weeks on hand above which to flag as overstock"
    )


# ============================================================================
# Recommendation Models
# ============================================================================

class Recommendation(BaseModel):
    """A single order recommendation."""

    item_id: str
    item_name: str
    category: Optional[str] = None
    vendor: Optional[str] = None

    # Current state
    current_on_hand: float
    weeks_on_hand: Optional[float] = None
    avg_usage: float

    # Recommendation
    suggested_quantity: int = Field(..., ge=0)
    unit_cost: Optional[float] = None
    total_cost: Optional[float] = None

    # Reasoning
    reason_code: ReasonCode
    reason_text: str
    confidence: Confidence

    # Adjustments applied
    adjustments: List[str] = Field(default_factory=list)

    # Data quality warnings for this item
    warnings: List[str] = Field(default_factory=list)


class VendorSummary(BaseModel):
    """Summary of recommendations for a vendor."""

    vendor: str
    items_count: int
    total_spend: float
    meets_minimum: bool = True
    exceeds_maximum: bool = False


class CategorySummary(BaseModel):
    """Summary of recommendations for a category."""

    category: str
    items_count: int
    total_spend: float
    avg_weeks_on_hand: float


# ============================================================================
# Agent Run Models
# ============================================================================

class RunSummary(BaseModel):
    """Summary statistics for a recommendation run."""

    total_items: int
    total_spend: float
    items_with_warnings: int = 0

    # Breakdowns
    by_vendor: Dict[str, VendorSummary] = Field(default_factory=dict)
    by_category: Dict[str, CategorySummary] = Field(default_factory=dict)
    by_reason: Dict[str, int] = Field(default_factory=dict)

    # Alerts
    low_stock_count: int = 0
    overstock_count: int = 0


class RecommendationRun(BaseModel):
    """A complete recommendation run with results."""

    run_id: str
    dataset_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Configuration used
    targets: OrderTargets
    constraints: OrderConstraints

    # Results
    summary: RunSummary
    recommendations: List[Recommendation]

    # Issues found
    warnings: List[str] = Field(default_factory=list)
    data_quality_issues: List[Dict[str, Any]] = Field(default_factory=list)

    # Status
    status: str = Field(default="completed")  # completed, approved, exported


class RecommendRequest(BaseModel):
    """Request to generate recommendations."""

    dataset_id: str
    targets: Optional[OrderTargets] = Field(default=None)
    constraints: Optional[OrderConstraints] = Field(default=None)

    # Optional filters
    categories: Optional[List[str]] = Field(
        default=None,
        description="Only include these categories"
    )
    vendors: Optional[List[str]] = Field(
        default=None,
        description="Only include these vendors"
    )
    exclude_items: Optional[List[str]] = Field(
        default=None,
        description="Exclude these item IDs"
    )


class ApprovalRequest(BaseModel):
    """Request to approve/modify recommendations."""

    run_id: str

    # Approvals
    approved_items: Dict[str, int] = Field(
        default_factory=dict,
        description="item_id -> approved quantity"
    )
    rejected_items: List[str] = Field(
        default_factory=list,
        description="item_ids to reject"
    )

    # Notes
    notes: Optional[str] = None


class ExportRequest(BaseModel):
    """Request to export recommendations."""

    run_id: str
    format: str = Field(default="csv", pattern="^(csv|xlsx|json)$")

    # Options
    include_rejected: bool = False
    group_by_vendor: bool = True
    include_summary: bool = True
