"""
Comprehensive REST API for Inventory Management System

This unified API provides endpoints for:
- Data upload and management
- Analytics (summary, sales mix, trends)
- Visualizations (charts, graphs)
- Agent-based recommendations
- User preferences and actions

Both humans and agents can use these same endpoints.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import pandas as pd
from datetime import datetime
import json
import io

from models import create_dataset_from_excel, InventoryDataset
from features import compute_features, get_summary_stats
from agent import run_agent, export_order_csv, get_order_by_vendor
from storage import (
    init_db, get_recent_runs, get_run_details, get_run_actions,
    save_user_pref, get_user_prefs, save_user_actions, get_item_history
)
from policy import OrderTargets, OrderConstraints, generate_order_summary
import mappings

# Initialize FastAPI app
app = FastAPI(
    title="Inventory Management API",
    description="Unified REST API for inventory analytics and intelligent ordering",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware to allow web frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()

# ============================================================================
# Request/Response Models
# ============================================================================

class DatasetInfo(BaseModel):
    """Dataset information."""
    dataset_id: str
    total_items: int
    total_records: int
    total_weeks: int
    date_range: Dict[str, Optional[str]]
    vendors: List[str]
    categories: List[str]

class SummaryMetrics(BaseModel):
    """Summary metrics for an item."""
    item_id: str
    vendor: str
    category: str
    location: str
    on_hand: float
    last_week_usage: float
    avg_ytd: Optional[float]
    avg_10wk: Optional[float]
    avg_4wk: Optional[float]
    avg_2wk: Optional[float]
    weeks_on_hand_ytd: Optional[float]
    weeks_on_hand_10wk: Optional[float]
    weeks_on_hand_4wk: Optional[float]
    trend: str
    volatility: Optional[float]

class AgentRunRequest(BaseModel):
    """Request model for running the agent."""
    usage_column: str = Field(default='avg_4wk', description="Usage metric to use")
    smoothing_level: float = Field(default=0.3, ge=0.1, le=0.9)
    trend_threshold: float = Field(default=0.1, ge=0.05, le=0.30)
    custom_targets: Optional[Dict[str, float]] = None

class FilterParams(BaseModel):
    """Filter parameters for data queries."""
    vendors: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    min_weeks_on_hand: Optional[float] = None
    max_weeks_on_hand: Optional[float] = None
    trends: Optional[List[str]] = None  # ["↑", "→", "↓"]

# ============================================================================
# Global State
# ============================================================================

_datasets: Dict[str, InventoryDataset] = {}
_features_cache: Dict[str, pd.DataFrame] = {}

def store_dataset(dataset: InventoryDataset) -> str:
    """Store a dataset and return its ID."""
    dataset_id = datetime.now().isoformat().replace(':', '-').replace('.', '-')
    _datasets[dataset_id] = dataset
    return dataset_id

def get_dataset(dataset_id: str) -> InventoryDataset:
    """Retrieve a stored dataset."""
    if dataset_id not in _datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return _datasets[dataset_id]

def get_or_compute_features(dataset_id: str, smoothing_level: float = 0.3, trend_threshold: float = 0.1) -> pd.DataFrame:
    """Get cached features or compute them."""
    cache_key = f"{dataset_id}_{smoothing_level}_{trend_threshold}"
    if cache_key not in _features_cache:
        dataset = get_dataset(dataset_id)
        dataset = mappings.enrich_dataset(dataset)
        features_df = compute_features(dataset, smoothing_level, trend_threshold)
        _features_cache[cache_key] = features_df
    return _features_cache[cache_key]

# ============================================================================
# Core Endpoints
# ============================================================================

@app.get("/")
async def root():
    """API root with service information."""
    return {
        "service": "Inventory Management API",
        "version": "2.0.0",
        "status": "healthy",
        "endpoints": {
            "data": "/upload, /datasets",
            "analytics": "/analytics/summary, /analytics/items, /analytics/trends",
            "agent": "/agent/run, /agent/runs",
            "preferences": "/preferences",
            "docs": "/docs"
        }
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
# Data Management Endpoints
# ============================================================================

@app.post("/upload", response_model=DatasetInfo)
async def upload_inventory(
    files: List[UploadFile] = File(..., description="Excel inventory files")
):
    """
    Upload inventory data files and create a dataset.

    **Human use case:** Upload weekly Excel files to analyze
    **Agent use case:** Ingest new data for analysis
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
            raise HTTPException(status_code=400, detail="No valid data found")

        # Enrich with mappings
        dataset = mappings.enrich_dataset(dataset)

        # Store dataset
        dataset_id = store_dataset(dataset)

        # Get metadata
        date_range = dataset.get_date_range()
        vendors = mappings.get_all_vendors(dataset)
        categories = mappings.get_all_categories(dataset)

        return DatasetInfo(
            dataset_id=dataset_id,
            total_items=len(dataset.items),
            total_records=len(dataset.records),
            total_weeks=dataset.get_total_weeks(),
            date_range={
                "start": date_range[0].isoformat() if date_range[0] else None,
                "end": date_range[1].isoformat() if date_range[1] else None
            },
            vendors=vendors,
            categories=categories
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing files: {str(e)}")

@app.get("/datasets", summary="List all datasets")
async def list_datasets():
    """
    List all datasets currently in memory.

    **Human use case:** See available datasets
    **Agent use case:** Enumerate datasets for analysis
    """
    datasets_info = []
    for dataset_id, dataset in _datasets.items():
        date_range = dataset.get_date_range()
        datasets_info.append({
            "dataset_id": dataset_id,
            "total_items": len(dataset.items),
            "total_records": len(dataset.records),
            "total_weeks": dataset.get_total_weeks(),
            "date_range": {
                "start": date_range[0].isoformat() if date_range[0] else None,
                "end": date_range[1].isoformat() if date_range[1] else None
            }
        })
    return {"datasets": datasets_info, "count": len(datasets_info)}

@app.get("/datasets/{dataset_id}", response_model=DatasetInfo)
async def get_dataset_info(dataset_id: str):
    """
    Get detailed information about a dataset.

    **Human use case:** View dataset metadata
    **Agent use case:** Inspect dataset before processing
    """
    dataset = get_dataset(dataset_id)
    date_range = dataset.get_date_range()
    vendors = mappings.get_all_vendors(dataset)
    categories = mappings.get_all_categories(dataset)

    return DatasetInfo(
        dataset_id=dataset_id,
        total_items=len(dataset.items),
        total_records=len(dataset.records),
        total_weeks=dataset.get_total_weeks(),
        date_range={
            "start": date_range[0].isoformat() if date_range[0] else None,
            "end": date_range[1].isoformat() if date_range[1] else None
        },
        vendors=vendors,
        categories=categories
    )

@app.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str):
    """Delete a dataset from memory."""
    if dataset_id in _datasets:
        del _datasets[dataset_id]
        # Clear cached features
        for key in list(_features_cache.keys()):
            if key.startswith(dataset_id):
                del _features_cache[key]
        return {"message": "Dataset deleted", "dataset_id": dataset_id}
    raise HTTPException(status_code=404, detail="Dataset not found")

# ============================================================================
# Analytics Endpoints
# ============================================================================

@app.get("/analytics/{dataset_id}/summary")
async def get_summary_analytics(
    dataset_id: str,
    smoothing_level: float = Query(default=0.3, ge=0.1, le=0.9),
    trend_threshold: float = Query(default=0.1, ge=0.05, le=0.30),
    vendor: Optional[str] = None,
    category: Optional[str] = None
):
    """
    Get summary analytics for all items.

    **Human use case:** View dashboard summary table
    **Agent use case:** Get overview of inventory state
    """
    try:
        features_df = get_or_compute_features(dataset_id, smoothing_level, trend_threshold)
        dataset = get_dataset(dataset_id)

        # Merge features with item metadata
        summary_data = []
        for _, row in features_df.iterrows():
            item = dataset.get_item(row['item_id'])
            if not item:
                continue

            # Apply filters
            if vendor and item.vendor != vendor:
                continue
            if category and item.category != category:
                continue

            summary_data.append({
                'item_id': row['item_id'],
                'vendor': item.vendor,
                'category': item.category,
                'location': item.location or 'Unknown',
                'on_hand': row['on_hand'],
                'last_week_usage': row['last_week_usage'],
                'avg_ytd': row['avg_ytd'],
                'avg_10wk': row['avg_10wk'],
                'avg_4wk': row['avg_4wk'],
                'avg_2wk': row['avg_2wk'],
                'avg_highest_4': row['avg_highest_4'],
                'avg_lowest_4_nonzero': row['avg_lowest_4_nonzero'],
                'weeks_on_hand_ytd': row['weeks_on_hand_ytd'],
                'weeks_on_hand_10wk': row['weeks_on_hand_10wk'],
                'weeks_on_hand_4wk': row['weeks_on_hand_4wk'],
                'weeks_on_hand_2wk': row['weeks_on_hand_2wk'],
                'trend': row['trend'],
                'volatility': row['volatility'],
                'recent_trend_ratio': row['recent_trend_ratio']
            })

        return {
            "dataset_id": dataset_id,
            "total_items": len(summary_data),
            "summary": summary_data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")

@app.get("/analytics/{dataset_id}/items/{item_id}")
async def get_item_details(
    dataset_id: str,
    item_id: str,
    smoothing_level: float = Query(default=0.3, ge=0.1, le=0.9),
    trend_threshold: float = Query(default=0.1, ge=0.05, le=0.30)
):
    """
    Get detailed analytics for a specific item.

    **Human use case:** View item detail page
    **Agent use case:** Inspect specific item for decision-making
    """
    try:
        dataset = get_dataset(dataset_id)
        item = dataset.get_item(item_id)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        features_df = get_or_compute_features(dataset_id, smoothing_level, trend_threshold)
        item_features = features_df[features_df['item_id'] == item_id]

        if item_features.empty:
            raise HTTPException(status_code=404, detail="Item features not found")

        # Get weekly history
        records = dataset.get_item_records(item_id)
        weekly_history = records.to_dict(orient='records')

        return {
            "item": {
                "item_id": item.item_id,
                "display_name": item.display_name,
                "vendor": item.vendor,
                "category": item.category,
                "location": item.location
            },
            "features": item_features.iloc[0].to_dict(),
            "weekly_history": weekly_history
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving item: {str(e)}")

@app.get("/analytics/{dataset_id}/trends")
async def get_trends(
    dataset_id: str,
    smoothing_level: float = Query(default=0.3, ge=0.1, le=0.9),
    trend_threshold: float = Query(default=0.1, ge=0.05, le=0.30)
):
    """
    Get trend statistics across all items.

    **Human use case:** View trend dashboard
    **Agent use case:** Understand overall inventory trends
    """
    try:
        features_df = get_or_compute_features(dataset_id, smoothing_level, trend_threshold)
        summary_stats = get_summary_stats(features_df)

        return {
            "dataset_id": dataset_id,
            "stats": summary_stats,
            "trending_up": features_df[features_df['trend'] == '↑']['item_id'].tolist(),
            "trending_down": features_df[features_df['trend'] == '↓']['item_id'].tolist(),
            "low_stock": features_df[features_df['weeks_on_hand_4wk'] < 2.0]['item_id'].tolist()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating trends: {str(e)}")

@app.get("/analytics/{dataset_id}/chart/{item_id}")
async def get_item_chart_data(dataset_id: str, item_id: str):
    """
    Get time-series data for charting an item's usage history.

    **Human use case:** Generate usage chart
    **Agent use case:** Visualize usage patterns for analysis
    """
    try:
        dataset = get_dataset(dataset_id)
        records = dataset.get_item_records(item_id)

        if records.empty:
            raise HTTPException(status_code=404, detail="No data found for item")

        chart_data = {
            "item_id": item_id,
            "dates": records['week_date'].dt.strftime('%Y-%m-%d').tolist(),
            "usage": records['usage'].tolist(),
            "on_hand": records['on_hand'].tolist()
        }

        return chart_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating chart: {str(e)}")

@app.get("/analytics/{dataset_id}/vendors")
async def get_vendor_summary(dataset_id: str):
    """
    Get summary statistics grouped by vendor.

    **Human use case:** View vendor comparison
    **Agent use case:** Analyze vendor distribution
    """
    try:
        dataset = get_dataset(dataset_id)
        features_df = get_or_compute_features(dataset_id)

        vendor_stats = []
        for vendor in mappings.get_all_vendors(dataset):
            vendor_items = mappings.get_items_by_vendor(dataset, vendor)
            vendor_features = features_df[features_df['item_id'].isin(vendor_items)]

            vendor_stats.append({
                "vendor": vendor,
                "total_items": len(vendor_items),
                "total_on_hand": vendor_features['on_hand'].sum(),
                "avg_weeks_on_hand": vendor_features['weeks_on_hand_4wk'].mean(),
                "items_low_stock": len(vendor_features[vendor_features['weeks_on_hand_4wk'] < 2.0])
            })

        return {"vendors": vendor_stats}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating vendor summary: {str(e)}")

@app.get("/analytics/{dataset_id}/categories")
async def get_category_summary(dataset_id: str):
    """
    Get summary statistics grouped by category.

    **Human use case:** View category comparison
    **Agent use case:** Analyze category distribution
    """
    try:
        dataset = get_dataset(dataset_id)
        features_df = get_or_compute_features(dataset_id)

        category_stats = []
        for category in mappings.get_all_categories(dataset):
            category_items = mappings.get_items_by_category(dataset, category)
            category_features = features_df[features_df['item_id'].isin(category_items)]

            category_stats.append({
                "category": category,
                "total_items": len(category_items),
                "total_on_hand": category_features['on_hand'].sum(),
                "avg_usage": category_features['avg_4wk'].mean(),
                "avg_weeks_on_hand": category_features['weeks_on_hand_4wk'].mean()
            })

        return {"categories": category_stats}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating category summary: {str(e)}")

# ============================================================================
# Agent Endpoints (from previous api.py)
# ============================================================================

@app.post("/agent/run/{dataset_id}")
async def run_agent_endpoint(dataset_id: str, request: AgentRunRequest):
    """
    Run the intelligent ordering agent.

    **Human use case:** Generate draft order recommendations
    **Agent use case:** Self-initiate ordering analysis
    """
    try:
        dataset = get_dataset(dataset_id)
        dataset = mappings.enrich_dataset(dataset)

        custom_targets = None
        if request.custom_targets:
            custom_targets = OrderTargets()
            custom_targets.target_weeks_by_category.update(request.custom_targets)

        result = run_agent(
            dataset,
            usage_column=request.usage_column,
            smoothing_level=request.smoothing_level,
            trend_threshold=request.trend_threshold,
            custom_targets=custom_targets
        )

        return {
            "run_id": result['run_id'],
            "summary": result['summary'],
            "stats": result['summary_stats'],
            "items_needing_recount": result['items_needing_recount'],
            "recommendations_count": len(result['recommendations'])
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running agent: {str(e)}")

@app.get("/agent/runs")
async def get_agent_runs(limit: int = Query(default=10, ge=1, le=100)):
    """
    Get history of agent runs.

    **Human use case:** View past order recommendations
    **Agent use case:** Review decision history
    """
    try:
        runs_df = get_recent_runs(limit=limit)
        return {"runs": runs_df.to_dict(orient='records'), "count": len(runs_df)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving runs: {str(e)}")

@app.get("/agent/runs/{run_id}/recommendations")
async def get_recommendations(
    run_id: str,
    vendor: Optional[str] = None,
    category: Optional[str] = None,
    items_to_order_only: bool = False
):
    """
    Get recommendations from a specific agent run.

    **Human use case:** Review and approve order recommendations
    **Agent use case:** Retrieve own recommendations for follow-up actions
    """
    try:
        recs_df = get_run_details(run_id)

        if recs_df.empty:
            raise HTTPException(status_code=404, detail="Run not found")

        if vendor:
            recs_df = recs_df[recs_df['vendor'] == vendor]
        if category:
            recs_df = recs_df[recs_df['category'] == category]
        if items_to_order_only:
            recs_df = recs_df[recs_df['recommended_qty'] > 0]

        return {
            "run_id": run_id,
            "recommendations": recs_df.to_dict(orient='records'),
            "count": len(recs_df)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving recommendations: {str(e)}")

@app.get("/agent/runs/{run_id}/export")
async def export_run(
    run_id: str,
    vendor: Optional[str] = None,
    items_to_order_only: bool = True
):
    """
    Export recommendations as CSV.

    **Human use case:** Download order sheet for vendor
    **Agent use case:** Generate order file for automated submission
    """
    try:
        recs_df = get_run_details(run_id)

        if recs_df.empty:
            raise HTTPException(status_code=404, detail="Run not found")

        if vendor:
            recs_df = recs_df[recs_df['vendor'] == vendor]
        if items_to_order_only:
            recs_df = recs_df[recs_df['recommended_qty'] > 0]

        output = io.StringIO()
        recs_df.to_csv(output, index=False)
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
# User Preferences & Actions
# ============================================================================

@app.post("/actions")
async def save_actions_endpoint(run_id: str, actions: List[Dict]):
    """
    Save user actions (what was actually ordered).

    **Human use case:** Record approved orders
    **Agent use case:** Learn from user overrides
    """
    try:
        save_user_actions(run_id, actions)
        return {"message": "Actions saved", "count": len(actions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving actions: {str(e)}")

@app.get("/preferences")
async def get_preferences_endpoint():
    """
    Get all user preferences.

    **Human use case:** View custom settings
    **Agent use case:** Apply learned preferences
    """
    try:
        prefs = get_user_prefs()
        return {"preferences": prefs, "count": len(prefs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving preferences: {str(e)}")

@app.post("/preferences/{item_id}")
async def update_preference_endpoint(item_id: str, preference: Dict):
    """
    Update preference for an item.

    **Human use case:** Set custom target weeks
    **Agent use case:** Store learned behavior
    """
    try:
        save_user_pref(item_id, **preference)
        return {"message": "Preference saved", "item_id": item_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving preference: {str(e)}")

@app.get("/items/{item_id}/history")
async def get_item_history_endpoint(item_id: str, limit: int = 10):
    """
    Get historical recommendations and actions for an item.

    **Human use case:** View item order history
    **Agent use case:** Learn from past decisions
    """
    try:
        history = get_item_history(item_id, limit=limit)
        return {
            "item_id": item_id,
            "recommendations": history['recommendations'].to_dict(orient='records') if not history['recommendations'].empty else [],
            "actions": history['actions'].to_dict(orient='records') if not history['actions'].empty else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving history: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("Starting Inventory Management API")
    print("=" * 60)
    print("\nEndpoints available:")
    print("  📊 Analytics: http://localhost:8000/docs#/analytics")
    print("  🤖 Agent: http://localhost:8000/docs#/agent")
    print("  ⚙️  Preferences: http://localhost:8000/docs#/preferences")
    print("\nAPI Documentation: http://localhost:8000/docs")
    print("=" * 60)
    print()
    uvicorn.run(app, host="0.0.0.0", port=8000)
