"""
Order Recommendations API Routes

Endpoints for agentic ordering - smart recommendations based on usage.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_inventory_service, get_order_service
from smallcogs.models.orders import (
    ApprovalRequest,
    ForecastSummary,
    OrderConstraints,
    OrderExport,
    OrderTargets,
    RecommendationRun,
    RecommendRequest,
    SalesForecast,
)
from smallcogs.services import InventoryService, OrderService

router = APIRouter(prefix="/orders", tags=["Order Recommendations"])


# =============================================================================
# Forecast Models
# =============================================================================

class HistoricalSalesResponse(BaseModel):
    """Historical sales data for forecasting."""
    weeks_analyzed: int = Field(..., description="Number of weeks of data analyzed")
    avg_total_sales: Optional[float] = Field(None, description="Average total weekly sales")
    by_category: Dict[str, float] = Field(
        default_factory=dict,
        description="Average weekly sales by category"
    )
    data_quality: str = Field(
        default="good",
        description="Data quality indicator: good, partial, insufficient"
    )
    notes: List[str] = Field(default_factory=list, description="Any data quality notes")


# =============================================================================
# Recommendations
# =============================================================================

@router.post("/recommend", response_model=RecommendationRun)
async def generate_recommendations(
    request: RecommendRequest,
    order_svc: OrderService = Depends(get_order_service),
    inv_svc: InventoryService = Depends(get_inventory_service),
):
    """
    Generate order recommendations for a dataset.

    Analyzes usage patterns and suggests orders based on targets.
    """
    dataset = inv_svc.get_dataset(request.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return order_svc.generate_recommendations(dataset, request)


@router.get("/runs", response_model=List[RecommendationRun])
async def list_runs(
    dataset_id: Optional[str] = None,
    order_svc: OrderService = Depends(get_order_service),
):
    """List all recommendation runs."""
    return order_svc.list_runs(dataset_id)


@router.get("/runs/{run_id}", response_model=RecommendationRun)
async def get_run(
    run_id: str,
    order_svc: OrderService = Depends(get_order_service),
):
    """Get a specific recommendation run."""
    run = order_svc.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


# =============================================================================
# Approval
# =============================================================================

@router.post("/runs/{run_id}/approve")
async def approve_recommendations(
    run_id: str,
    request: ApprovalRequest,
    order_svc: OrderService = Depends(get_order_service),
):
    """
    Approve or modify recommendations.

    Can approve all, approve with modifications, or reject items.
    """
    run = order_svc.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Update status
    run.status = "approved"

    # TODO: Apply approval changes

    return {"status": "approved", "run_id": run_id}


# =============================================================================
# Export
# =============================================================================

@router.get("/runs/{run_id}/export", response_model=OrderExport)
async def export_run(
    run_id: str,
    format: str = "csv",
    group_by_vendor: bool = True,
    order_svc: OrderService = Depends(get_order_service),
):
    """
    Export recommendations for copy/paste or download.

    Returns CSV text and summary text ready for clipboard.
    """
    export = order_svc.export_run(run_id, format, group_by_vendor)
    if not export:
        raise HTTPException(status_code=404, detail="Run not found")
    return export


# =============================================================================
# Configuration
# =============================================================================

@router.get("/targets/default", response_model=OrderTargets)
async def get_default_targets():
    """Get default order targets (user can customize)."""
    return OrderTargets()


@router.get("/constraints/default", response_model=OrderConstraints)
async def get_default_constraints():
    """Get default order constraints (user can customize)."""
    return OrderConstraints()


# =============================================================================
# Forecasting
# =============================================================================

@router.get("/forecast/historical-sales", response_model=HistoricalSalesResponse)
async def get_historical_sales(
    weeks: int = Query(default=4, ge=1, le=52, description="Number of weeks to average"),
    inv_svc: InventoryService = Depends(get_inventory_service),
):
    """
    Get historical average sales data for forecasting.

    Returns average weekly sales (total and by category) based on
    COGS summaries from the bevweekly sheet. Use this data to populate
    the SalesForecast when generating order recommendations.

    Example workflow:
    1. Call this endpoint to get historical_avg_total_sales and historical_by_category
    2. Input your expected sales (based on events, seasonality, etc.)
    3. Call /orders/recommend with a SalesForecast containing both values
    """
    # Try to get COGS summaries from the most recent dataset
    # In a real implementation, you might pass a dataset_id
    try:
        from models import InventoryDataset, create_dataset_from_excel

        # For now, return guidance - in production this would load actual data
        notes = []
        notes.append("Upload a bevweekly file to compute actual historical sales")

        return HistoricalSalesResponse(
            weeks_analyzed=0,
            avg_total_sales=None,
            by_category={},
            data_quality="insufficient",
            notes=notes,
        )

    except Exception as e:
        return HistoricalSalesResponse(
            weeks_analyzed=0,
            avg_total_sales=None,
            by_category={},
            data_quality="insufficient",
            notes=[f"Could not load historical data: {str(e)}"],
        )


@router.get("/forecast/default", response_model=SalesForecast)
async def get_default_forecast():
    """
    Get a default/example SalesForecast structure.

    Shows the structure for submitting a sales forecast with order recommendations.
    """
    return SalesForecast(
        percent_change=None,
        expected_total_sales=None,
        historical_avg_total_sales=None,
        by_category={},
        historical_by_category={},
        forecast_weeks=1.0,
        notes=None,
    )
