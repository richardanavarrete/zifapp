"""
REST API for the Inventory Agent System

This FastAPI application provides HTTP endpoints for:
- Uploading inventory data
- Running the agent
- Retrieving recommendations and run history
- Managing user preferences
- Exporting orders
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import pandas as pd
from datetime import datetime
import json
import io

from models import create_dataset_from_excel, InventoryDataset
from agent import run_agent, export_order_csv, get_order_by_vendor
from storage import (
    init_db, get_recent_runs, get_run_details, get_run_actions,
    save_user_pref, get_user_prefs, save_user_actions, get_item_history
)
from policy import OrderTargets, OrderConstraints

# Initialize FastAPI app
app = FastAPI(
    title="Inventory Agent API",
    description="REST API for intelligent inventory ordering with agent-based recommendations",
    version="1.0.0"
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()

# ============================================================================
# Request/Response Models
# ============================================================================

class AgentRunRequest(BaseModel):
    """Request model for running the agent."""
    usage_column: str = Field(default='avg_4wk', description="Usage metric to use")
    smoothing_level: float = Field(default=0.3, ge=0.1, le=0.9)
    trend_threshold: float = Field(default=0.1, ge=0.05, le=0.30)
    custom_targets: Optional[Dict[str, float]] = Field(default=None, description="Category-specific target weeks")

class AgentRunResponse(BaseModel):
    """Response model for agent run."""
    run_id: str
    summary: str
    total_items: int
    items_to_order: int
    total_qty: int
    stockout_risks: int
    items_needing_recount: List[str]
    recommendations_count: int

class RecommendationResponse(BaseModel):
    """Single recommendation item."""
    item_id: str
    vendor: str
    category: str
    on_hand: float
    avg_usage: float
    weeks_on_hand: float
    target_weeks: float
    recommended_qty: int
    reason_codes: List[str]
    confidence: str
    notes: str

class UserActionRequest(BaseModel):
    """Request to save user actions."""
    run_id: str
    actions: List[Dict]

class UserPreferenceRequest(BaseModel):
    """Request to update user preference."""
    item_id: str
    target_weeks_override: Optional[float] = None
    never_order: Optional[bool] = None
    preferred_case_rounding: Optional[int] = None
    notes: Optional[str] = None

# ============================================================================
# Global State (In-memory dataset storage)
# ============================================================================

# Store datasets in memory by dataset_id
_datasets: Dict[str, InventoryDataset] = {}

def store_dataset(dataset: InventoryDataset) -> str:
    """Store a dataset and return its ID."""
    dataset_id = datetime.now().isoformat().replace(':', '-')
    _datasets[dataset_id] = dataset
    return dataset_id

def get_dataset(dataset_id: str) -> InventoryDataset:
    """Retrieve a stored dataset."""
    if dataset_id not in _datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return _datasets[dataset_id]

# ============================================================================
# Health Check
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Inventory Agent API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",
        "datasets_in_memory": len(_datasets),
        "timestamp": datetime.now().isoformat()
    }

# ============================================================================
# Data Upload & Management
# ============================================================================

@app.post("/upload", summary="Upload inventory Excel files")
async def upload_inventory(
    files: List[UploadFile] = File(..., description="Excel files to upload")
):
    """
    Upload one or more Excel inventory files.

    Returns a dataset_id that can be used in subsequent API calls.
    """
    try:
        # Save uploaded files temporarily
        temp_files = []
        for file in files:
            content = await file.read()
            temp_file = io.BytesIO(content)
            temp_file.name = file.filename
            temp_files.append(temp_file)

        # Create dataset
        dataset = create_dataset_from_excel(temp_files)

        if not dataset.items:
            raise HTTPException(status_code=400, detail="No valid data found in uploaded files")

        # Store dataset
        dataset_id = store_dataset(dataset)

        # Get date range
        date_range = dataset.get_date_range()

        return {
            "dataset_id": dataset_id,
            "total_items": len(dataset.items),
            "total_records": len(dataset.records),
            "total_weeks": dataset.get_total_weeks(),
            "date_range": {
                "start": date_range[0].isoformat() if date_range[0] else None,
                "end": date_range[1].isoformat() if date_range[1] else None
            },
            "message": "Data uploaded successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing files: {str(e)}")

@app.get("/datasets/{dataset_id}/info", summary="Get dataset information")
async def get_dataset_info(dataset_id: str):
    """Get information about a stored dataset."""
    dataset = get_dataset(dataset_id)
    date_range = dataset.get_date_range()

    return {
        "dataset_id": dataset_id,
        "total_items": len(dataset.items),
        "total_records": len(dataset.records),
        "total_weeks": dataset.get_total_weeks(),
        "date_range": {
            "start": date_range[0].isoformat() if date_range[0] else None,
            "end": date_range[1].isoformat() if date_range[1] else None
        }
    }

# ============================================================================
# Agent Operations
# ============================================================================

@app.post("/agent/run/{dataset_id}", response_model=AgentRunResponse, summary="Run the agent")
async def run_agent_endpoint(
    dataset_id: str,
    request: AgentRunRequest
):
    """
    Run the inventory agent on a dataset.

    This generates order recommendations based on current inventory levels,
    usage patterns, and configurable targets.
    """
    try:
        dataset = get_dataset(dataset_id)

        # Build custom targets if provided
        custom_targets = None
        if request.custom_targets:
            custom_targets = OrderTargets()
            custom_targets.target_weeks_by_category.update(request.custom_targets)

        # Run agent
        result = run_agent(
            dataset,
            usage_column=request.usage_column,
            smoothing_level=request.smoothing_level,
            trend_threshold=request.trend_threshold,
            custom_targets=custom_targets
        )

        return AgentRunResponse(
            run_id=result['run_id'],
            summary=result['summary'],
            total_items=result['summary_stats']['total_items'],
            items_to_order=result['summary_stats']['items_to_order'],
            total_qty=result['summary_stats']['total_qty'],
            stockout_risks=result['summary_stats']['stockout_risks'],
            items_needing_recount=result['items_needing_recount'],
            recommendations_count=len(result['recommendations'])
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running agent: {str(e)}")

@app.get("/agent/runs", summary="Get recent agent runs")
async def get_runs(limit: int = Query(default=10, ge=1, le=100)):
    """Get a list of recent agent runs."""
    try:
        runs_df = get_recent_runs(limit=limit)
        runs = runs_df.to_dict(orient='records')
        return {"runs": runs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving runs: {str(e)}")

@app.get("/agent/runs/{run_id}", summary="Get run details")
async def get_run(run_id: str):
    """Get detailed recommendations for a specific run."""
    try:
        recs_df = get_run_details(run_id)

        if recs_df.empty:
            raise HTTPException(status_code=404, detail="Run not found")

        recommendations = recs_df.to_dict(orient='records')
        return {
            "run_id": run_id,
            "total_recommendations": len(recommendations),
            "recommendations": recommendations
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving run: {str(e)}")

@app.get("/agent/runs/{run_id}/recommendations", response_model=List[RecommendationResponse], summary="Get recommendations")
async def get_recommendations(
    run_id: str,
    vendor: Optional[str] = Query(default=None, description="Filter by vendor"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    items_to_order_only: bool = Query(default=False, description="Only items with qty > 0")
):
    """Get recommendations from a run with optional filters."""
    try:
        recs_df = get_run_details(run_id)

        if recs_df.empty:
            raise HTTPException(status_code=404, detail="Run not found")

        # Apply filters
        if vendor:
            recs_df = recs_df[recs_df['vendor'] == vendor]

        if category:
            recs_df = recs_df[recs_df['category'] == category]

        if items_to_order_only:
            recs_df = recs_df[recs_df['recommended_qty'] > 0]

        recommendations = recs_df.to_dict(orient='records')
        return recommendations

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving recommendations: {str(e)}")

@app.get("/agent/runs/{run_id}/export", summary="Export recommendations as CSV")
async def export_recommendations(
    run_id: str,
    vendor: Optional[str] = Query(default=None, description="Filter by vendor"),
    items_to_order_only: bool = Query(default=True, description="Only items with qty > 0")
):
    """Export recommendations as a CSV file."""
    try:
        recs_df = get_run_details(run_id)

        if recs_df.empty:
            raise HTTPException(status_code=404, detail="Run not found")

        # Apply filters
        if vendor:
            recs_df = recs_df[recs_df['vendor'] == vendor]

        if items_to_order_only:
            recs_df = recs_df[recs_df['recommended_qty'] > 0]

        # Convert to CSV
        output = io.StringIO()
        recs_df[['item_id', 'vendor', 'category', 'on_hand', 'avg_usage',
                 'weeks_on_hand', 'target_weeks', 'recommended_qty',
                 'confidence', 'notes']].to_csv(output, index=False)
        output.seek(0)

        filename = f"order_{run_id}_{vendor if vendor else 'all'}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting: {str(e)}")

# ============================================================================
# User Actions & Preferences
# ============================================================================

@app.post("/actions", summary="Save user actions")
async def save_actions(request: UserActionRequest):
    """
    Save user actions (approvals/edits) for a run.

    This records what the user actually ordered vs. what the agent recommended.
    """
    try:
        save_user_actions(request.run_id, request.actions)
        return {"message": "Actions saved successfully", "count": len(request.actions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving actions: {str(e)}")

@app.get("/actions/{run_id}", summary="Get user actions for a run")
async def get_actions(run_id: str):
    """Get user actions for a specific run."""
    try:
        actions_df = get_run_actions(run_id)
        actions = actions_df.to_dict(orient='records') if not actions_df.empty else []
        return {"run_id": run_id, "actions": actions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving actions: {str(e)}")

@app.get("/preferences", summary="Get all user preferences")
async def get_preferences():
    """Get all user preferences."""
    try:
        prefs = get_user_prefs()
        return {"preferences": prefs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving preferences: {str(e)}")

@app.post("/preferences", summary="Update user preference")
async def update_preference(request: UserPreferenceRequest):
    """Update or create a user preference for an item."""
    try:
        kwargs = {}
        if request.target_weeks_override is not None:
            kwargs['target_weeks_override'] = request.target_weeks_override
        if request.never_order is not None:
            kwargs['never_order'] = int(request.never_order)
        if request.preferred_case_rounding is not None:
            kwargs['preferred_case_rounding'] = request.preferred_case_rounding
        if request.notes is not None:
            kwargs['notes'] = request.notes

        save_user_pref(request.item_id, **kwargs)
        return {"message": "Preference saved successfully", "item_id": request.item_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving preference: {str(e)}")

@app.get("/items/{item_id}/history", summary="Get item history")
async def get_item_history_endpoint(item_id: str, limit: int = Query(default=10, ge=1, le=50)):
    """Get recommendation and action history for a specific item."""
    try:
        history = get_item_history(item_id, limit=limit)

        return {
            "item_id": item_id,
            "recommendations": history['recommendations'].to_dict(orient='records') if not history['recommendations'].empty else [],
            "actions": history['actions'].to_dict(orient='records') if not history['actions'].empty else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving history: {str(e)}")

# ============================================================================
# Statistics & Analytics
# ============================================================================

@app.get("/stats/summary", summary="Get overall statistics")
async def get_summary_stats():
    """Get summary statistics across all runs."""
    try:
        runs_df = get_recent_runs(limit=100)

        if runs_df.empty:
            return {"message": "No runs found"}

        return {
            "total_runs": len(runs_df),
            "total_items_analyzed": runs_df['total_items'].sum(),
            "total_items_ordered": runs_df['items_to_order'].sum(),
            "total_qty_ordered": runs_df['total_qty_recommended'].sum(),
            "avg_items_per_run": runs_df['total_items'].mean(),
            "avg_qty_per_run": runs_df['total_qty_recommended'].mean()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving stats: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
