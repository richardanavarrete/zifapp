"""Order recommendation data models."""

from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field

from houndcogs.models.common import Category, Vendor, ReasonCode, Confidence


class OrderTargets(BaseModel):
    """Target inventory levels by category."""

    # Default weeks of inventory to maintain by category
    weeks_by_category: Dict[str, float] = Field(
        default_factory=lambda: {
            "Beer": 2.0,
            "Draft Beer": 2.0,
            "Bottled Beer": 2.0,
            "Liquor": 4.0,
            "Whiskey": 4.0,
            "Vodka": 4.0,
            "Gin": 4.0,
            "Tequila": 4.0,
            "Rum": 4.0,
            "Scotch": 4.0,
            "Brandy": 4.0,
            "Well": 4.0,
            "Liqueur": 4.0,
            "Cordials": 4.0,
            "Wine": 3.0,
            "Juice": 2.0,
            "Bar Consumables": 2.0,
        }
    )

    # Item-specific overrides (item_id -> target weeks)
    item_overrides: Dict[str, float] = Field(default_factory=dict)

    # Items to never order
    never_order: List[str] = Field(default_factory=list)

    def get_target_weeks(self, item_id: str, category: str) -> float:
        """Get target weeks for an item, checking overrides first."""
        if item_id in self.never_order:
            return 0.0
        if item_id in self.item_overrides:
            return self.item_overrides[item_id]
        return self.weeks_by_category.get(category, 4.0)


class OrderConstraints(BaseModel):
    """Constraints on order generation."""

    max_total_spend: Optional[float] = Field(default=None, description="Maximum total order value")
    max_total_cases: Optional[int] = Field(default=None, description="Maximum total cases")

    # Vendor-specific constraints
    vendor_minimums: Dict[str, float] = Field(
        default_factory=dict,
        description="Minimum order value per vendor"
    )
    vendor_keg_limits: Dict[str, int] = Field(
        default_factory=lambda: {
            "Crescent": 21,
            "Hensley": 21,
        },
        description="Maximum kegs per vendor order"
    )

    # Rebalancing
    keg_rebalance_threshold: float = Field(
        default=1.0,
        description="Weeks on hand below which to consider rebalancing"
    )


class Recommendation(BaseModel):
    """A single order recommendation."""

    item_id: str
    display_name: str
    category: str
    vendor: str

    # Current state
    current_on_hand: float
    weeks_on_hand: float
    avg_weekly_usage: float

    # Recommendation
    suggested_order: int = Field(..., ge=0)
    unit_cost: float
    total_cost: float

    # Reasoning
    reason_code: ReasonCode
    reason_text: str
    confidence: Confidence

    # Adjustments applied
    adjustments: List[str] = Field(default_factory=list)

    # Data quality warnings
    warnings: List[str] = Field(default_factory=list)


class VendorSummary(BaseModel):
    """Summary of recommendations for a vendor."""

    vendor: str
    items_count: int
    total_spend: float
    meets_minimum: bool = True
    keg_count: int = 0


class AgentRunSummary(BaseModel):
    """Summary statistics for an agent run."""

    total_items: int
    total_spend: float
    items_with_warnings: int = 0
    by_vendor: Dict[str, VendorSummary] = Field(default_factory=dict)
    by_category: Dict[str, int] = Field(default_factory=dict)
    by_reason: Dict[str, int] = Field(default_factory=dict)


class AgentRun(BaseModel):
    """A complete agent run with all recommendations."""

    run_id: str
    dataset_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Configuration used
    targets: OrderTargets
    constraints: OrderConstraints

    # Results
    summary: AgentRunSummary
    recommendations: List[Recommendation]

    # Warnings and issues
    warnings: List[Dict[str, str]] = Field(default_factory=list)

    # Status
    status: str = Field(default="completed")  # completed, approved, rejected


class ApprovalRequest(BaseModel):
    """Request to approve/modify recommendations."""

    run_id: str
    approved_items: Dict[str, int] = Field(
        default_factory=dict,
        description="item_id -> approved quantity (can differ from suggested)"
    )
    rejected_items: List[str] = Field(
        default_factory=list,
        description="item_ids to reject (not order)"
    )
    notes: Optional[str] = None
