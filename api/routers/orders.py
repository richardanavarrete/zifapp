"""Order recommendation endpoints."""

import uuid
from datetime import datetime
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Query, Body
from pydantic import BaseModel

from api.dependencies import get_api_key
from api.middleware.errors import NotFoundError, ProcessingError
from houndcogs.models.orders import (
    OrderTargets,
    OrderConstraints,
    Recommendation,
    AgentRun,
    AgentRunSummary,
    ApprovalRequest,
)

router = APIRouter()


class RecommendRequest(BaseModel):
    """Request body for order recommendations."""
    dataset_id: str
    targets: Optional[OrderTargets] = None
    constraints: Optional[OrderConstraints] = None


class RunListItem(BaseModel):
    """Summary item for listing runs."""
    run_id: str
    dataset_id: str
    created_at: datetime
    total_items: int
    total_spend: float
    status: str


@router.post("/recommend", response_model=AgentRun)
async def generate_recommendations(
    request: RecommendRequest,
    api_key: str = Depends(get_api_key),
):
    """
    Generate order recommendations for a dataset.

    Uses the ordering agent to analyze inventory levels and generate
    recommended order quantities based on targets and constraints.

    **Process:**
    1. Load dataset and compute features
    2. Apply policy rules to determine what to order
    3. Generate recommendations with reasons and confidence
    4. Return full run with summary and recommendations
    """
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    targets = request.targets or OrderTargets()
    constraints = request.constraints or OrderConstraints()

    try:
        # TODO: Implement with houndcogs.services.ordering_agent
        # from houndcogs.services.ordering_agent import run_agent
        # run = run_agent(
        #     dataset_id=request.dataset_id,
        #     targets=targets,
        #     constraints=constraints,
        #     run_id=run_id
        # )
        # return run

        # Placeholder response
        return AgentRun(
            run_id=run_id,
            dataset_id=request.dataset_id,
            created_at=datetime.utcnow(),
            targets=targets,
            constraints=constraints,
            summary=AgentRunSummary(
                total_items=0,
                total_spend=0.0,
            ),
            recommendations=[],
            warnings=[{"message": "Agent not yet implemented"}]
        )

    except Exception as e:
        raise ProcessingError(
            message=f"Failed to generate recommendations: {str(e)}",
            details={"dataset_id": request.dataset_id}
        )


@router.get("/runs", response_model=List[RunListItem])
async def list_runs(
    dataset_id: Optional[str] = Query(None, description="Filter by dataset"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    api_key: str = Depends(get_api_key),
):
    """
    List past agent runs.

    Returns paginated list of run summaries.
    """
    # TODO: Implement with houndcogs.storage.sqlite_repo
    return []


@router.get("/runs/{run_id}", response_model=AgentRun)
async def get_run(
    run_id: str,
    api_key: str = Depends(get_api_key),
):
    """
    Get details of a specific agent run.

    Returns full run with all recommendations.
    """
    # TODO: Implement with houndcogs.storage.sqlite_repo
    raise NotFoundError("Run", run_id)


@router.post("/runs/{run_id}/approve")
async def approve_run(
    run_id: str,
    approval: ApprovalRequest = Body(...),
    api_key: str = Depends(get_api_key),
):
    """
    Approve or modify recommendations from a run.

    Allows the user to:
    - Approve all recommendations as-is
    - Modify quantities for specific items
    - Reject specific items

    **Body:**
    - `approved_items`: Dict of item_id -> approved quantity
    - `rejected_items`: List of item_ids to not order
    - `notes`: Optional notes about the approval
    """
    # TODO: Implement with houndcogs.storage.sqlite_repo
    # 1. Validate run exists
    # 2. Store approval decision
    # 3. Update run status

    return {
        "status": "approved",
        "run_id": run_id,
        "approved_at": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/targets", response_model=OrderTargets)
async def get_targets(
    api_key: str = Depends(get_api_key),
):
    """
    Get current order targets configuration.
    """
    # TODO: Load from storage or return defaults
    return OrderTargets()


@router.put("/targets", response_model=OrderTargets)
async def update_targets(
    targets: OrderTargets = Body(...),
    api_key: str = Depends(get_api_key),
):
    """
    Update order targets configuration.

    **Body:**
    - `weeks_by_category`: Target weeks of inventory by category
    - `item_overrides`: Item-specific target weeks
    - `never_order`: List of items to never order
    """
    # TODO: Save to storage
    return targets


@router.get("/constraints", response_model=OrderConstraints)
async def get_constraints(
    api_key: str = Depends(get_api_key),
):
    """
    Get current order constraints configuration.
    """
    return OrderConstraints()


@router.put("/constraints", response_model=OrderConstraints)
async def update_constraints(
    constraints: OrderConstraints = Body(...),
    api_key: str = Depends(get_api_key),
):
    """
    Update order constraints configuration.
    """
    return constraints
