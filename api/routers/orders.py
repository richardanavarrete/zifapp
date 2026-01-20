"""
Order Recommendations API Routes

Endpoints for agentic ordering - smart recommendations based on usage.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends

from smallcogs.models.orders import (
    OrderTargets,
    OrderConstraints,
    RecommendationRun,
    RecommendRequest,
    ApprovalRequest,
    OrderExport,
)
from smallcogs.services import OrderService, InventoryService
from api.dependencies import get_order_service, get_inventory_service

router = APIRouter(prefix="/orders", tags=["Order Recommendations"])


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
