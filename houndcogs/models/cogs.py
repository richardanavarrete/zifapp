"""COGS (Cost of Goods Sold) analysis data models."""

from datetime import date, datetime
from typing import Optional, Dict, List
from pydantic import BaseModel, Field


class CategoryCOGS(BaseModel):
    """COGS data for a single category."""

    category: str
    cogs_amount: float = Field(..., description="Total cost of goods sold")
    sales_amount: float = Field(..., description="Total sales revenue")
    pour_cost_percent: float = Field(..., description="COGS / Sales * 100")
    target_pour_cost: float = Field(default=25.0, description="Target pour cost %")
    variance_from_target: float = Field(default=0.0, description="Actual - Target")
    status: str = Field(default="on_target")  # under_target, on_target, over_target


class COGSSummary(BaseModel):
    """Summary of COGS analysis for a period."""

    report_id: str
    period_start: date
    period_end: date
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Totals
    total_cogs: float
    total_sales: float
    overall_pour_cost_percent: float

    # By category
    by_category: List[CategoryCOGS]

    # Trends
    prior_period_pour_cost: Optional[float] = None
    pour_cost_trend: str = Field(default="stable")  # improving, stable, worsening


class PourCostBenchmarks(BaseModel):
    """Industry benchmarks for pour costs by category."""

    benchmarks: Dict[str, float] = Field(
        default_factory=lambda: {
            "Liquor": 18.0,
            "Whiskey": 18.0,
            "Vodka": 18.0,
            "Gin": 18.0,
            "Tequila": 18.0,
            "Rum": 18.0,
            "Scotch": 20.0,
            "Brandy": 20.0,
            "Well": 15.0,
            "Liqueur": 22.0,
            "Cordials": 22.0,
            "Wine": 30.0,
            "Draft Beer": 20.0,
            "Bottled Beer": 25.0,
        }
    )


class ItemVariance(BaseModel):
    """Variance analysis for a single item."""

    item_id: str
    display_name: str
    category: str

    # Theoretical vs Actual
    theoretical_usage: float = Field(..., description="Expected usage from sales")
    actual_usage: float = Field(..., description="Actual inventory usage")
    variance_units: float = Field(..., description="Actual - Theoretical")
    variance_percent: float = Field(..., description="Variance / Theoretical * 100")
    variance_cost: float = Field(..., description="Variance in dollar value")

    # Classification
    status: str = Field(default="normal")  # shrinkage, overpour, normal, gain


class VarianceResult(BaseModel):
    """Complete variance analysis result."""

    report_id: str
    period_start: date
    period_end: date
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Summary
    total_theoretical_cost: float
    total_actual_cost: float
    total_variance_cost: float
    overall_variance_percent: float

    # By item
    items: List[ItemVariance]

    # Categories with issues
    shrinkage_items: int = 0
    overpour_items: int = 0
    total_shrinkage_cost: float = 0.0


class PourCostResult(BaseModel):
    """Pour cost calculation result."""

    item_id: str
    display_name: str
    category: str

    # Costs
    unit_cost: float
    pour_size_oz: float
    cost_per_pour: float

    # Pricing
    menu_price: Optional[float] = None
    pour_cost_percent: Optional[float] = None

    # Comparison
    benchmark_pour_cost: float
    variance_from_benchmark: Optional[float] = None


class COGSAnalysisRequest(BaseModel):
    """Request for COGS analysis."""

    dataset_id: str
    period_start: date
    period_end: date
    sales_data: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional sales data by category if not using uploaded sales mix"
    )


class VarianceAnalysisRequest(BaseModel):
    """Request for variance analysis."""

    dataset_id: str
    period_start: date
    period_end: date
    sales_mix_file_id: Optional[str] = Field(
        default=None,
        description="ID of uploaded sales mix CSV"
    )
