"""COGS (Cost of Goods Sold) analysis endpoints."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Query, UploadFile
from pydantic import BaseModel

from api.dependencies import get_api_key, get_file_storage, get_inventory_service
from api.middleware.errors import NotFoundError, ProcessingError
from houndcogs.models.cogs import (
    COGSAnalysisRequest,
    COGSSummary,
    PourCostResult,
    VarianceAnalysisRequest,
    VarianceResult,
)
from houndcogs.services import cogs_analyzer
from smallcogs.services.inventory_service import InventoryService

router = APIRouter()


# =============================================================================
# Adapter classes to convert Pydantic Dataset to service's expected interface
# =============================================================================

@dataclass
class _AdaptedRecord:
    """Adapter for Record that maps record_date -> week_date."""
    item_id: str
    week_date: date
    on_hand: float
    usage: float


@dataclass
class _AdaptedItem:
    """Adapter for Item that maps name -> display_name."""
    item_id: str
    display_name: str
    category: str
    unit_cost: float


class _DatasetAdapter:
    """
    Adapts a Pydantic Dataset to the interface expected by cogs_analyzer.

    The service expects:
    - dataset.records: iterable of objects with .item_id, .week_date, .usage
    - dataset.items: dict of items with .display_name, .category, .unit_cost
    - dataset.get_item(id): method returning item
    """

    def __init__(self, dataset):
        self._dataset = dataset

        # Convert records: record_date -> week_date
        self.records = [
            _AdaptedRecord(
                item_id=r.item_id,
                week_date=r.record_date,
                on_hand=r.on_hand,
                usage=r.usage if r.usage is not None else 0.0,
            )
            for r in dataset.records
        ]

        # Convert items: name -> display_name, handle None values
        self.items: Dict[str, _AdaptedItem] = {}
        for item_id, item in dataset.items.items():
            self.items[item_id] = _AdaptedItem(
                item_id=item_id,
                display_name=item.name,
                category=item.category or "Unknown",
                unit_cost=item.unit_cost if item.unit_cost is not None else 0.0,
            )

    def get_item(self, item_id: str) -> Optional[_AdaptedItem]:
        return self.items.get(item_id)


def _get_adapted_dataset(
    dataset_id: str,
    service: InventoryService,
) -> _DatasetAdapter:
    """Fetch dataset and adapt it for the cogs_analyzer service."""
    dataset = service.get_dataset(dataset_id)
    if not dataset:
        raise NotFoundError("Dataset", dataset_id)
    return _DatasetAdapter(dataset)


# =============================================================================
# Response Models
# =============================================================================

class ReportListItem(BaseModel):
    """Summary item for listing reports."""
    report_id: str
    report_type: str  # cogs, variance, pour_cost
    period_start: date
    period_end: date
    created_at: datetime


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/analyze", response_model=COGSSummary)
async def analyze_cogs(
    request: COGSAnalysisRequest = Body(...),
    api_key: str = Depends(get_api_key),
    service: InventoryService = Depends(get_inventory_service),
):
    """
    Run COGS analysis for a period.

    Calculates cost of goods sold, pour costs by category,
    and compares to benchmarks.

    **Required:**
    - `dataset_id`: Inventory dataset to analyze
    - `period_start`: Start date of analysis period
    - `period_end`: End date of analysis period

    **Optional:**
    - `sales_data`: Sales amounts by category (if not using uploaded sales mix)
    """
    try:
        adapted = _get_adapted_dataset(request.dataset_id, service)

        result = cogs_analyzer.analyze_cogs(
            dataset=adapted,
            period_start=request.period_start,
            period_end=request.period_end,
            sales_data=request.sales_data,
        )
        return result

    except NotFoundError:
        raise
    except Exception as e:
        raise ProcessingError(
            message=f"Failed to analyze COGS: {str(e)}",
            details={"dataset_id": request.dataset_id}
        )


@router.post("/pour-cost", response_model=List[PourCostResult])
async def calculate_pour_costs(
    dataset_id: str = Query(..., description="Dataset with item costs"),
    category: Optional[str] = Query(None, description="Filter by category"),
    api_key: str = Depends(get_api_key),
    service: InventoryService = Depends(get_inventory_service),
):
    """
    Calculate pour costs for items.

    Returns cost per pour based on bottle cost and pour size,
    along with comparison to benchmarks.
    """
    try:
        adapted = _get_adapted_dataset(dataset_id, service)

        result = cogs_analyzer.calculate_pour_costs(
            dataset=adapted,
            category_filter=category,
        )
        return result

    except NotFoundError:
        raise
    except Exception as e:
        raise ProcessingError(
            message=f"Failed to calculate pour costs: {str(e)}",
            details={"dataset_id": dataset_id}
        )


@router.post("/variance", response_model=VarianceResult)
async def analyze_variance(
    request: VarianceAnalysisRequest = Body(...),
    api_key: str = Depends(get_api_key),
    service: InventoryService = Depends(get_inventory_service),
):
    """
    Run variance analysis (theoretical vs actual usage).

    Compares expected usage from sales data to actual inventory usage
    to identify shrinkage, overpours, or other discrepancies.

    **Required:**
    - `dataset_id`: Inventory dataset
    - `period_start` / `period_end`: Analysis period
    - `sales_mix_file_id`: Uploaded sales mix CSV (or sales_data in body)
    """
    try:
        adapted = _get_adapted_dataset(request.dataset_id, service)

        # For variance analysis, we need theoretical_usage data.
        # This would normally come from parsing the sales_mix_file.
        # For now, we pass an empty dict if no sales mix is provided.
        theoretical_usage: Dict[str, float] = {}

        result = cogs_analyzer.calculate_variance(
            dataset=adapted,
            period_start=request.period_start,
            period_end=request.period_end,
            theoretical_usage=theoretical_usage,
        )
        return result

    except NotFoundError:
        raise
    except Exception as e:
        raise ProcessingError(
            message=f"Failed to analyze variance: {str(e)}"
        )


@router.post("/sales-mix/upload")
async def upload_sales_mix(
    file: UploadFile = File(..., description="Sales mix CSV file"),
    api_key: str = Depends(get_api_key),
    file_storage = Depends(get_file_storage),
):
    """
    Upload a sales mix CSV file for variance analysis.

    The sales mix shows what was sold, which is used to calculate
    theoretical usage for comparison against actual inventory usage.

    **File format**: GEMpos sales mix CSV export
    """
    if not file.filename.endswith('.csv'):
        raise ProcessingError(
            message="Invalid file format. Expected .csv",
            details={"filename": file.filename}
        )

    file_id = f"sm_{uuid.uuid4().hex[:12]}"

    # Save file
    await file_storage.save_upload(
        file=file,
        dataset_id="sales_mix",
        filename=f"{file_id}_{file.filename}"
    )

    return {
        "file_id": file_id,
        "filename": file.filename,
        "uploaded_at": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/reports", response_model=List[ReportListItem])
async def list_reports(
    report_type: Optional[str] = Query(None, description="Filter by type: cogs, variance, pour_cost"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    api_key: str = Depends(get_api_key),
):
    """
    List historical COGS/variance reports.
    """
    # Skipped - needs database persistence
    return []


@router.get("/reports/{report_id}")
async def get_report(
    report_id: str,
    api_key: str = Depends(get_api_key),
):
    """
    Get a specific report by ID.

    Returns the full report (COGS summary, variance result, etc.)
    """
    # Skipped - needs database persistence
    raise NotFoundError("Report", report_id)
