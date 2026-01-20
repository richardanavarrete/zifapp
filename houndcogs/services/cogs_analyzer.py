"""
COGS Analyzer

Calculates Cost of Goods Sold, pour costs, and variance analysis.
"""

import logging
import uuid
from datetime import date, datetime
from typing import List, Dict, Optional

from houndcogs.models.inventory import InventoryDataset
from houndcogs.models.cogs import (
    COGSSummary,
    CategoryCOGS,
    PourCostResult,
    VarianceResult,
    ItemVariance,
    PourCostBenchmarks,
)

logger = logging.getLogger(__name__)


# Pour sizes by category (oz)
POUR_SIZES = {
    "Whiskey": 1.5,
    "Vodka": 1.5,
    "Gin": 1.5,
    "Tequila": 1.5,
    "Rum": 1.5,
    "Scotch": 1.5,
    "Brandy": 1.5,
    "Well": 1.5,
    "Liqueur": 1.0,
    "Cordials": 1.0,
    "Wine": 6.0,  # Glass pour
    "Draft Beer": 16.0,  # Pint
    "Bottled Beer": 12.0,  # Bottle
}

# Standard bottle sizes (oz)
BOTTLE_SIZES = {
    "Liquor": 25.4,  # 750ml
    "Wine": 25.4,    # 750ml
}


def analyze_cogs(
    dataset: InventoryDataset,
    period_start: date,
    period_end: date,
    sales_data: Optional[Dict[str, float]] = None,
) -> COGSSummary:
    """
    Analyze COGS for a period.

    Args:
        dataset: Inventory dataset with cost information
        period_start: Start of analysis period
        period_end: End of analysis period
        sales_data: Optional sales amounts by category

    Returns:
        COGSSummary with pour costs and benchmarks
    """
    report_id = f"cogs_{uuid.uuid4().hex[:12]}"
    benchmarks = PourCostBenchmarks()

    # Calculate COGS from inventory usage
    category_cogs = _calculate_category_cogs(dataset, period_start, period_end)

    # If sales data provided, calculate pour costs
    by_category = []
    total_cogs = 0.0
    total_sales = 0.0

    for category, cogs_amount in category_cogs.items():
        total_cogs += cogs_amount

        sales_amount = sales_data.get(category, 0.0) if sales_data else 0.0
        total_sales += sales_amount

        pour_cost_pct = (cogs_amount / sales_amount * 100) if sales_amount > 0 else 0.0
        target = benchmarks.benchmarks.get(category, 25.0)
        variance = pour_cost_pct - target

        if pour_cost_pct == 0:
            status = "no_data"
        elif pour_cost_pct < target - 2:
            status = "under_target"
        elif pour_cost_pct > target + 2:
            status = "over_target"
        else:
            status = "on_target"

        by_category.append(CategoryCOGS(
            category=category,
            cogs_amount=round(cogs_amount, 2),
            sales_amount=round(sales_amount, 2),
            pour_cost_percent=round(pour_cost_pct, 2),
            target_pour_cost=target,
            variance_from_target=round(variance, 2),
            status=status,
        ))

    overall_pour_cost = (total_cogs / total_sales * 100) if total_sales > 0 else 0.0

    return COGSSummary(
        report_id=report_id,
        period_start=period_start,
        period_end=period_end,
        total_cogs=round(total_cogs, 2),
        total_sales=round(total_sales, 2),
        overall_pour_cost_percent=round(overall_pour_cost, 2),
        by_category=by_category,
    )


def _calculate_category_cogs(
    dataset: InventoryDataset,
    period_start: date,
    period_end: date,
) -> Dict[str, float]:
    """Calculate COGS by category from inventory usage."""
    category_cogs = {}

    # Filter records to period
    period_records = [
        r for r in dataset.records
        if period_start <= r.week_date <= period_end
    ]

    for record in period_records:
        item = dataset.get_item(record.item_id)
        if not item:
            continue

        category = item.category.value if hasattr(item.category, 'value') else str(item.category)
        cost = record.usage * item.unit_cost

        category_cogs[category] = category_cogs.get(category, 0.0) + cost

    return category_cogs


def calculate_pour_costs(
    dataset: InventoryDataset,
    category_filter: Optional[str] = None,
) -> List[PourCostResult]:
    """
    Calculate pour cost for each item.

    Returns cost per pour based on bottle cost and standard pour size.
    """
    benchmarks = PourCostBenchmarks()
    results = []

    for item_id, item in dataset.items.items():
        category = item.category.value if hasattr(item.category, 'value') else str(item.category)

        if category_filter and category != category_filter:
            continue

        pour_size = POUR_SIZES.get(category, 1.5)
        bottle_size = BOTTLE_SIZES.get("Liquor", 25.4)

        # Cost per pour
        cost_per_pour = (item.unit_cost / bottle_size) * pour_size if bottle_size > 0 else 0

        benchmark = benchmarks.benchmarks.get(category, 25.0)

        results.append(PourCostResult(
            item_id=item_id,
            display_name=item.display_name,
            category=category,
            unit_cost=item.unit_cost,
            pour_size_oz=pour_size,
            cost_per_pour=round(cost_per_pour, 3),
            benchmark_pour_cost=benchmark,
        ))

    return results


def calculate_variance(
    dataset: InventoryDataset,
    period_start: date,
    period_end: date,
    theoretical_usage: Dict[str, float],
) -> VarianceResult:
    """
    Calculate variance between theoretical and actual usage.

    Args:
        dataset: Inventory dataset
        period_start: Start of period
        period_end: End of period
        theoretical_usage: Expected usage by item_id (from sales mix)

    Returns:
        VarianceResult with item-level detail
    """
    report_id = f"var_{uuid.uuid4().hex[:12]}"

    # Calculate actual usage from inventory records
    actual_usage = _calculate_actual_usage(dataset, period_start, period_end)

    items = []
    total_theoretical_cost = 0.0
    total_actual_cost = 0.0
    shrinkage_items = 0
    overpour_items = 0
    total_shrinkage_cost = 0.0

    for item_id in set(theoretical_usage.keys()) | set(actual_usage.keys()):
        item = dataset.get_item(item_id)
        if not item:
            continue

        theoretical = theoretical_usage.get(item_id, 0.0)
        actual = actual_usage.get(item_id, 0.0)

        variance_units = actual - theoretical
        variance_pct = (variance_units / theoretical * 100) if theoretical > 0 else 0.0
        variance_cost = variance_units * item.unit_cost

        total_theoretical_cost += theoretical * item.unit_cost
        total_actual_cost += actual * item.unit_cost

        # Classify variance
        if variance_pct > 5:  # More than 5% over theoretical
            status = "overpour"
            overpour_items += 1
        elif variance_pct < -5:  # More than 5% under theoretical (potential theft/waste)
            status = "shrinkage"
            shrinkage_items += 1
            total_shrinkage_cost += abs(variance_cost)
        else:
            status = "normal"

        category = item.category.value if hasattr(item.category, 'value') else str(item.category)

        items.append(ItemVariance(
            item_id=item_id,
            display_name=item.display_name,
            category=category,
            theoretical_usage=round(theoretical, 2),
            actual_usage=round(actual, 2),
            variance_units=round(variance_units, 2),
            variance_percent=round(variance_pct, 2),
            variance_cost=round(variance_cost, 2),
            status=status,
        ))

    total_variance_cost = total_actual_cost - total_theoretical_cost
    overall_variance_pct = (
        (total_variance_cost / total_theoretical_cost * 100)
        if total_theoretical_cost > 0 else 0.0
    )

    return VarianceResult(
        report_id=report_id,
        period_start=period_start,
        period_end=period_end,
        total_theoretical_cost=round(total_theoretical_cost, 2),
        total_actual_cost=round(total_actual_cost, 2),
        total_variance_cost=round(total_variance_cost, 2),
        overall_variance_percent=round(overall_variance_pct, 2),
        items=items,
        shrinkage_items=shrinkage_items,
        overpour_items=overpour_items,
        total_shrinkage_cost=round(total_shrinkage_cost, 2),
    )


def _calculate_actual_usage(
    dataset: InventoryDataset,
    period_start: date,
    period_end: date,
) -> Dict[str, float]:
    """Calculate actual usage by item from inventory records."""
    usage_by_item = {}

    for record in dataset.records:
        if period_start <= record.week_date <= period_end:
            usage_by_item[record.item_id] = (
                usage_by_item.get(record.item_id, 0.0) + record.usage
            )

    return usage_by_item
