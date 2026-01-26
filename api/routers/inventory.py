"""Inventory API endpoints."""

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from api.config import get_settings
from api.dependencies import get_supabase_repository
from api.supabase.middleware import get_current_user, require_org
from api.supabase.models import CurrentUser
from smallcogs.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])

# Service instance (in production, use dependency injection)
_service: Optional[InventoryService] = None


def get_service() -> InventoryService:
    global _service
    if _service is None:
        settings = get_settings()
        _service = InventoryService(storage_path=settings.data_dir)
    return _service


# =============================================================================
# Dataset Endpoints
# =============================================================================

@router.post("/upload")
async def upload_inventory(
    file: UploadFile = File(...),
    name: Optional[str] = Query(None, description="Dataset name"),
    skip_rows: int = Query(0, ge=0, description="Rows to skip"),
    current_user: CurrentUser = Depends(require_org),
    service: InventoryService = Depends(get_service),
):
    """Upload an inventory spreadsheet (Excel or CSV)."""
    settings = get_settings()

    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = file.filename.split(".")[-1].lower()
    if ext not in ["xlsx", "xls", "csv"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Use .xlsx, .xls, or .csv"
        )

    # Save uploaded file temporarily
    upload_dir = settings.upload_dir
    os.makedirs(upload_dir, exist_ok=True)

    temp_path = os.path.join(upload_dir, f"{uuid.uuid4().hex}_{file.filename}")

    try:
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Parse file
        result = service.upload_file(
            file_path=temp_path,
            name=name or file.filename.rsplit(".", 1)[0],
            skip_rows=skip_rows,
        )

        # Save to Supabase if enabled
        if settings.supabase_enabled and current_user.org_id:
            repo = get_supabase_repository(current_user.org_id)
            dataset = service.get_dataset(result.dataset_id)
            if dataset:
                repo.save_dataset(dataset)

        return result.model_dump()

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/datasets")
async def list_datasets(
    current_user: CurrentUser = Depends(require_org),
    service: InventoryService = Depends(get_service),
):
    """List all uploaded datasets."""
    settings = get_settings()

    # Use Supabase if enabled
    if settings.supabase_enabled and current_user.org_id:
        repo = get_supabase_repository(current_user.org_id)
        datasets = repo.list_datasets()
        return {"datasets": [d.model_dump() for d in datasets]}

    # Fall back to in-memory service
    datasets = service.list_datasets()
    return {"datasets": [d.model_dump() for d in datasets]}


@router.get("/datasets/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    current_user: CurrentUser = Depends(require_org),
    service: InventoryService = Depends(get_service),
):
    """Get dataset details."""
    settings = get_settings()

    # Use Supabase if enabled
    if settings.supabase_enabled and current_user.org_id:
        repo = get_supabase_repository(current_user.org_id)
        dataset = repo.get_dataset(dataset_id)
    else:
        dataset = service.get_dataset(dataset_id)

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return {
        "dataset_id": dataset.dataset_id,
        "name": dataset.name,
        "created_at": dataset.created_at.isoformat(),
        "items_count": dataset.items_count,
        "records_count": getattr(dataset, "records_count", len(dataset.records)),
        "periods_count": getattr(dataset, "periods_count", dataset.weeks_count),
        "date_range_start": str(dataset.date_range_start) if dataset.date_range_start else None,
        "date_range_end": str(dataset.date_range_end) if dataset.date_range_end else None,
        "categories": getattr(dataset, "categories", []),
        "vendors": getattr(dataset, "vendors", []),
    }


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    current_user: CurrentUser = Depends(require_org),
    service: InventoryService = Depends(get_service),
):
    """Delete a dataset."""
    settings = get_settings()

    # Use Supabase if enabled
    if settings.supabase_enabled and current_user.org_id:
        repo = get_supabase_repository(current_user.org_id)
        deleted = repo.delete_dataset(dataset_id)
    else:
        deleted = service.delete_dataset(dataset_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"deleted": True}


# =============================================================================
# Item Endpoints
# =============================================================================

@router.get("/datasets/{dataset_id}/items")
async def get_items(
    dataset_id: str,
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    vendor: Optional[str] = Query(None),
    include_stats: bool = Query(True),
    current_user: CurrentUser = Depends(require_org),
    service: InventoryService = Depends(get_service),
):
    """Get items in a dataset with optional filtering."""
    from smallcogs.models.inventory import ItemFilter

    settings = get_settings()

    # For Supabase, first get the dataset then use service for stats
    if settings.supabase_enabled and current_user.org_id:
        repo = get_supabase_repository(current_user.org_id)
        dataset = repo.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # Store in service for stats computation
        service._datasets[dataset_id] = dataset

    filters = ItemFilter(
        search=search,
        categories=[category] if category else None,
        vendors=[vendor] if vendor else None,
    )

    items = service.get_items(dataset_id, filters, include_stats)
    if not items and not service.get_dataset(dataset_id):
        raise HTTPException(status_code=404, detail="Dataset not found")

    return {"items": items, "count": len(items)}


@router.get("/datasets/{dataset_id}/items/{item_id}")
async def get_item_detail(
    dataset_id: str,
    item_id: str,
    current_user: CurrentUser = Depends(require_org),
    service: InventoryService = Depends(get_service),
):
    """Get detailed view of a single item including history and trends."""
    settings = get_settings()

    # For Supabase, first get the dataset
    if settings.supabase_enabled and current_user.org_id:
        repo = get_supabase_repository(current_user.org_id)
        dataset = repo.get_dataset(dataset_id)
        if dataset:
            service._datasets[dataset_id] = dataset

    detail = service.get_item_detail(dataset_id, item_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Item not found")
    return detail


# =============================================================================
# Analytics Endpoints
# =============================================================================

@router.get("/datasets/{dataset_id}/dashboard")
async def get_dashboard(
    dataset_id: str,
    current_user: CurrentUser = Depends(require_org),
    service: InventoryService = Depends(get_service),
):
    """Get dashboard summary with key metrics and alerts."""
    settings = get_settings()

    # For Supabase, first get the dataset
    if settings.supabase_enabled and current_user.org_id:
        repo = get_supabase_repository(current_user.org_id)
        dataset = repo.get_dataset(dataset_id)
        if dataset:
            service._datasets[dataset_id] = dataset

    stats = service.get_dashboard_stats(dataset_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return stats
