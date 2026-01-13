"""
COGS Analysis Module - Pour Cost, Variance, and Profitability Analysis

This module provides functions for:
- Calculating COGS by category and vendor
- Pour cost analysis (COGS / Revenue)
- Variance analysis (Theoretical vs Actual usage in dollars)
- Shrinkage reports
"""

import pandas as pd
from typing import Dict, Tuple, Optional
from models import InventoryDataset


# Category mapping - maps item-level categories to spreadsheet-level categories
CATEGORY_CONSOLIDATION = {
    "Whiskey": "Liquor",
    "Vodka": "Liquor",
    "Gin": "Liquor",
    "Tequila": "Liquor",
    "Rum": "Liquor",
    "Scotch": "Liquor",
    "Well": "Liquor",
    "Liqueur": "Liquor",
    "Cordials": "Liquor",
    "Wine": "Wine",
    "Draft Beer": "Draft Beer",
    "Bottled Beer": "Bottle Beer",
    "Juice": "Juice",
    "Bar Consumables": "Juice",  # Consolidate with Juice for reporting
}

# Pour cost targets by category (industry standards adjusted for Zipps)
POUR_COST_TARGETS = {
    "Whiskey": {"target": 13, "warning": 15, "critical": 20},
    "Vodka": {"target": 13, "warning": 15, "critical": 20},
    "Tequila": {"target": 13, "warning": 15, "critical": 20},
    "Gin": {"target": 13, "warning": 15, "critical": 20},
    "Rum": {"target": 13, "warning": 15, "critical": 20},
    "Scotch": {"target": 13, "warning": 15, "critical": 20},
    "Bourbon": {"target": 13, "warning": 15, "critical": 20},
    "Liquor": {"target": 13, "warning": 15, "critical": 20},  # Generic liquor
    "Draft Beer": {"target": 20, "warning": 27, "critical": 30},
    "Bottle Beer": {"target": 19, "warning": 25, "critical": 30},  # Updated from 24
    "Wine": {"target": 22, "warning": 25, "critical": 30},  # Updated from 28
    "Bar Other": {"target": 13, "warning": 15, "critical": 20},
}


def calculate_cogs_by_category(dataset: InventoryDataset, features_df: pd.DataFrame, consolidate: bool = True) -> pd.DataFrame:
    """
    Calculate COGS summary by category.

    Args:
        dataset: InventoryDataset with items
        features_df: Features dataframe with cost metrics
        consolidate: If True, consolidate categories (Whiskey/Vodka/etc. -> Liquor)

    Returns:
        DataFrame with columns: category, weekly_cogs, inventory_value, cogs_ytd
    """
    # Add category to features
    features_with_cat = features_df.copy()
    features_with_cat['category'] = features_with_cat['item_id'].apply(
        lambda x: dataset.get_item(x).category if dataset.get_item(x) else "Unknown"
    )

    # Apply consolidation mapping if requested
    if consolidate:
        features_with_cat['category'] = features_with_cat['category'].apply(
            lambda x: CATEGORY_CONSOLIDATION.get(x, x)
        )

    # Group by category
    cogs_by_cat = features_with_cat.groupby('category').agg({
        'weekly_cogs': 'sum',
        'avg_weekly_cogs_4wk': 'sum',
        'inventory_value': 'sum',
        'cogs_ytd': 'sum'
    }).reset_index()

    # Convert to numeric and round values (handles object dtype from None values)
    for col in ['weekly_cogs', 'avg_weekly_cogs_4wk', 'inventory_value', 'cogs_ytd']:
        cogs_by_cat[col] = pd.to_numeric(cogs_by_cat[col], errors='coerce').fillna(0).round(2)

    # Sort by weekly_cogs descending
    cogs_by_cat = cogs_by_cat.sort_values('weekly_cogs', ascending=False)

    return cogs_by_cat


def calculate_cogs_by_vendor(dataset: InventoryDataset, features_df: pd.DataFrame, include_unknown: bool = False) -> pd.DataFrame:
    """
    Calculate COGS summary by vendor.

    Args:
        dataset: InventoryDataset with items
        features_df: Features dataframe with cost metrics
        include_unknown: If True, include items with "Unknown" vendor

    Returns:
        DataFrame with columns: vendor, weekly_cogs, inventory_value, cogs_ytd
    """
    # Add vendor to features
    features_with_vendor = features_df.copy()
    features_with_vendor['vendor'] = features_with_vendor['item_id'].apply(
        lambda x: dataset.get_item(x).vendor if dataset.get_item(x) else "Unknown"
    )

    # Filter out Unknown vendors if requested
    if not include_unknown:
        features_with_vendor = features_with_vendor[features_with_vendor['vendor'] != "Unknown"]

    # Group by vendor
    cogs_by_vendor = features_with_vendor.groupby('vendor').agg({
        'weekly_cogs': 'sum',
        'avg_weekly_cogs_4wk': 'sum',
        'inventory_value': 'sum',
        'cogs_ytd': 'sum'
    }).reset_index()

    # Convert to numeric and round values (handles object dtype from None values)
    for col in ['weekly_cogs', 'avg_weekly_cogs_4wk', 'inventory_value', 'cogs_ytd']:
        cogs_by_vendor[col] = pd.to_numeric(cogs_by_vendor[col], errors='coerce').fillna(0).round(2)

    # Sort by weekly_cogs descending
    cogs_by_vendor = cogs_by_vendor.sort_values('weekly_cogs', ascending=False)

    return cogs_by_vendor


def calculate_theoretical_cogs(
    usage_results: dict,
    dataset: InventoryDataset
) -> Dict[str, float]:
    """
    Calculate theoretical COGS from sales mix usage results.

    Args:
        usage_results: Dict from aggregate_all_usage with theoretical usage by item
        dataset: InventoryDataset with cost data

    Returns:
        Dict with:
        - theoretical_cogs_total: float
        - theoretical_cogs_by_category: Dict[str, float]
        - theoretical_cogs_by_item: Dict[str, float]
    """
    theoretical_cogs_by_item = {}
    theoretical_cogs_by_category = {}

    for item_id, usage_data in usage_results.items():
        theoretical_usage = usage_data.get('theoretical_usage', 0)
        item = dataset.get_item(item_id)

        if item and item.unit_cost and theoretical_usage:
            item_cogs = theoretical_usage * item.unit_cost
            theoretical_cogs_by_item[item_id] = round(item_cogs, 2)

            # Aggregate by category
            category = item.category
            if category not in theoretical_cogs_by_category:
                theoretical_cogs_by_category[category] = 0
            theoretical_cogs_by_category[category] += item_cogs

    # Round category totals
    for cat in theoretical_cogs_by_category:
        theoretical_cogs_by_category[cat] = round(theoretical_cogs_by_category[cat], 2)

    theoretical_cogs_total = sum(theoretical_cogs_by_item.values())

    return {
        'theoretical_cogs_total': round(theoretical_cogs_total, 2),
        'theoretical_cogs_by_category': theoretical_cogs_by_category,
        'theoretical_cogs_by_item': theoretical_cogs_by_item
    }


def calculate_pour_cost(
    theoretical_cogs: Dict[str, float],
    total_revenue: float,
    revenue_by_category: Optional[Dict[str, float]] = None
) -> Dict:
    """
    Calculate pour cost percentage.

    Pour Cost % = (COGS / Revenue) × 100

    Args:
        theoretical_cogs: Dict with theoretical_cogs_by_category
        total_revenue: Total revenue from sales
        revenue_by_category: Optional dict of revenue by category

    Returns:
        Dict with:
        - overall_pour_cost_pct: float
        - pour_cost_by_category: Dict[str, dict] with pct, status, target
    """
    overall_pour_cost_pct = 0.0
    if total_revenue > 0:
        overall_pour_cost_pct = (theoretical_cogs.get('theoretical_cogs_total', 0) / total_revenue) * 100

    pour_cost_by_category = {}

    if revenue_by_category and theoretical_cogs.get('theoretical_cogs_by_category'):
        for category, cogs in theoretical_cogs['theoretical_cogs_by_category'].items():
            revenue = revenue_by_category.get(category, 0)

            if revenue > 0:
                pct = (cogs / revenue) * 100

                # Get target thresholds
                targets = POUR_COST_TARGETS.get(category, POUR_COST_TARGETS.get("Liquor"))

                # Determine status
                if pct <= targets['target']:
                    status = 'on_target'
                elif pct <= targets['warning']:
                    status = 'warning'
                else:
                    status = 'critical'

                pour_cost_by_category[category] = {
                    'pour_cost_pct': round(pct, 2),
                    'cogs': round(cogs, 2),
                    'revenue': round(revenue, 2),
                    'status': status,
                    'target': targets['target'],
                    'warning': targets['warning'],
                    'critical': targets['critical']
                }

    return {
        'overall_pour_cost_pct': round(overall_pour_cost_pct, 2),
        'total_cogs': theoretical_cogs.get('theoretical_cogs_total', 0),
        'total_revenue': round(total_revenue, 2),
        'gross_profit': round(total_revenue - theoretical_cogs.get('theoretical_cogs_total', 0), 2),
        'pour_cost_by_category': pour_cost_by_category
    }


def calculate_pour_cost_actual(
    dataset: InventoryDataset,
    usage_results: dict,
    week_name: str = None
) -> Dict:
    """
    Calculate pour cost percentage using ACTUAL COGS and SALES from the bevweekly sheet.

    This replaces the theoretical COGS calculation with actual COGS from the
    spreadsheet's "Weekly COGS" section, which uses the formula:
    COGS = Beginning Inventory $ + Purchases $ - Ending Inventory $

    Sales data is also taken from the bevweekly sheet (column B - manager-entered).

    Args:
        dataset: InventoryDataset with weekly_cogs_summaries
        usage_results: Dict from aggregate_all_usage (used for item-level analysis)
        week_name: Optional specific week name (e.g., 'Q1 WK2'). If None, uses latest complete week.

    Returns:
        Dict with:
        - overall_pour_cost_pct: float
        - total_cogs: float (from bevweekly sheet)
        - total_revenue: float (from bevweekly sheet)
        - gross_profit: float
        - pour_cost_by_category: Dict[str, dict] with pct, status, target
    """
    # Get the COGS summary from the spreadsheet
    if week_name:
        cogs_summary = dataset.get_cogs_summary_by_name(week_name)
    else:
        cogs_summary = dataset.get_latest_complete_cogs_summary()

    if not cogs_summary or not cogs_summary.is_complete:
        # Fallback if actual COGS not available
        return {
            'overall_pour_cost_pct': 0.0,
            'total_cogs': 0.0,
            'total_revenue': 0.0,
            'gross_profit': 0.0,
            'pour_cost_by_category': {},
            'error': 'Actual COGS data not available from bevweekly sheet. Please ensure ending inventory is filled in.'
        }

    # Use actual COGS from the spreadsheet
    actual_cogs = cogs_summary.total_cogs or 0

    # Get sales data from bevweekly sheet (column B - manager-entered)
    total_sales = cogs_summary.total_sales or 0

    # Validate sales data
    if total_sales <= 0:
        return {
            'overall_pour_cost_pct': 0.0,
            'total_cogs': round(actual_cogs, 2),
            'total_revenue': 0.0,
            'gross_profit': -round(actual_cogs, 2),
            'pour_cost_by_category': {},
            'error': 'Sales data not available from bevweekly sheet. Please ensure SALES column (column B) is filled in.'
        }

    # Calculate overall pour cost
    overall_pour_cost_pct = (actual_cogs / total_sales * 100)

    # Get category-level sales from bevweekly sheet
    category_sales_map = {
        'Liquor': cogs_summary.liquor_sales or 0,
        'Wine': cogs_summary.wine_sales or 0,
        'Draft Beer': cogs_summary.draft_beer_sales or 0,
        'Bottle Beer': cogs_summary.bottle_beer_sales or 0,
        'Juice': 0  # Juice doesn't have direct sales, uses total beverage sales
    }

    # Build pour cost by category using actual COGS from spreadsheet
    pour_cost_by_category = {}

    # Map spreadsheet COGS to categories
    category_cogs_map = {
        'Liquor': cogs_summary.liquor_cogs or 0,
        'Wine': cogs_summary.wine_cogs or 0,
        'Draft Beer': cogs_summary.draft_beer_cogs or 0,
        'Bottle Beer': cogs_summary.bottle_beer_cogs or 0,
        'Juice': cogs_summary.juice_cogs or 0
    }

    for category, cogs in category_cogs_map.items():
        # Special case: Juice uses total beverage revenue (all categories except Juice)
        if category == 'Juice':
            revenue = (category_sales_map['Liquor'] +
                      category_sales_map['Wine'] +
                      category_sales_map['Draft Beer'] +
                      category_sales_map['Bottle Beer'])
        else:
            revenue = category_sales_map[category]

        if revenue > 0 and cogs > 0:
            pct = (cogs / revenue) * 100

            # Get target thresholds - map to correct target category
            target_category = category
            if category == 'Bottle Beer':
                target_category = 'Bottle Beer'

            targets = POUR_COST_TARGETS.get(target_category, POUR_COST_TARGETS.get("Liquor"))

            # Determine status
            if pct <= targets['target']:
                status = 'on_target'
            elif pct <= targets['warning']:
                status = 'warning'
            else:
                status = 'critical'

            pour_cost_by_category[category] = {
                'pour_cost_pct': round(pct, 2),
                'cogs': round(cogs, 2),
                'revenue': round(revenue, 2),
                'status': status,
                'target': targets['target'],
                'warning': targets['warning'],
                'critical': targets['critical']
            }

    return {
        'overall_pour_cost_pct': round(overall_pour_cost_pct, 2),
        'total_cogs': round(actual_cogs, 2),
        'total_revenue': round(total_sales, 2),
        'gross_profit': round(total_sales - actual_cogs, 2),
        'pour_cost_by_category': pour_cost_by_category,
        'week_name': cogs_summary.week_name,
        'week_date': cogs_summary.week_date
    }


def calculate_variance_analysis(
    theoretical_usage: dict,
    actual_usage: pd.DataFrame,
    dataset: InventoryDataset
) -> pd.DataFrame:
    """
    Calculate variance between theoretical and actual usage in both units and dollars.

    Args:
        theoretical_usage: Dict from aggregate_all_usage
        actual_usage: DataFrame with columns: item_id, actual_usage
        dataset: InventoryDataset with cost data

    Returns:
        DataFrame with variance analysis including:
        - item_id, category, theoretical, actual, variance_units, variance_dollars, variance_pct
    """
    variance_data = []

    for item_id, theory_data in theoretical_usage.items():
        theoretical = theory_data.get('theoretical_usage', 0)
        item = dataset.get_item(item_id)

        if not item:
            continue

        # Get actual usage from dataframe
        actual_row = actual_usage[actual_usage['item_id'] == item_id]
        actual = actual_row['usage'].iloc[0] if not actual_row.empty else 0

        # Calculate variance
        variance_units = actual - theoretical
        variance_dollars = 0
        variance_pct = 0

        if item.unit_cost:
            variance_dollars = variance_units * item.unit_cost

        if theoretical > 0:
            variance_pct = (variance_units / theoretical) * 100

        # Categorize severity
        severity = 'normal'
        if abs(variance_pct) > 50:
            severity = 'critical'
        elif abs(variance_pct) > 25:
            severity = 'warning'

        variance_data.append({
            'item_id': item_id,
            'category': item.category,
            'theoretical': round(theoretical, 2),
            'actual': round(actual, 2),
            'variance_units': round(variance_units, 2),
            'variance_dollars': round(variance_dollars, 2),
            'variance_pct': round(variance_pct, 2),
            'unit_cost': item.unit_cost,
            'severity': severity
        })

    variance_df = pd.DataFrame(variance_data)

    # Sort by absolute variance dollars
    if not variance_df.empty:
        variance_df['abs_variance_dollars'] = variance_df['variance_dollars'].abs()
        variance_df = variance_df.sort_values('abs_variance_dollars', ascending=False)
        variance_df = variance_df.drop('abs_variance_dollars', axis=1)

    return variance_df


def generate_shrinkage_report(
    variance_df: pd.DataFrame,
    top_n: int = 20
) -> pd.DataFrame:
    """
    Generate shrinkage report showing top losses.

    Shrinkage = Positive variance (used more than sold)

    Args:
        variance_df: DataFrame from calculate_variance_analysis
        top_n: Number of top items to include (None for all items)

    Returns:
        DataFrame with top shrinkage items
    """
    # Filter for positive variance (actual > theoretical = loss)
    shrinkage = variance_df[variance_df['variance_dollars'] > 0].copy()

    # Sort by variance dollars descending and take top N
    shrinkage = shrinkage.sort_values('variance_dollars', ascending=False)
    if top_n is not None:
        shrinkage = shrinkage.head(top_n)

    return shrinkage


def calculate_item_profitability(
    usage_results: dict,
    theoretical_cogs: Dict[str, float],
    dataset: InventoryDataset,
    week_name: str = None
) -> pd.DataFrame:
    """
    Calculate profitability metrics per item using ACTUAL COGS from bevweekly sheet.

    This function allocates actual COGS from the bevweekly sheet to individual items
    proportionally based on their theoretical usage, and compares to theoretical profit
    to show variance.

    Args:
        usage_results: Dict from aggregate_all_usage with revenue per item
        theoretical_cogs: Dict from calculate_theoretical_cogs
        dataset: InventoryDataset with item metadata and weekly_cogs_summaries
        week_name: Optional specific week name. If None, uses latest complete week.

    Returns:
        DataFrame with columns:
        - item_id, category, vendor, revenue, theoretical_cogs, actual_cogs,
          theoretical_profit, actual_profit, theoretical_margin_pct, actual_margin_pct,
          profit_variance, status
    """
    # Get the COGS summary from the spreadsheet
    if week_name:
        cogs_summary = dataset.get_cogs_summary_by_name(week_name)
    else:
        cogs_summary = dataset.get_latest_complete_cogs_summary()

    # If no actual COGS available, fall back to theoretical only
    use_actual_cogs = cogs_summary and cogs_summary.is_complete

    profitability_data = []
    theoretical_cogs_by_item = theoretical_cogs.get('theoretical_cogs_by_item', {})
    theoretical_cogs_by_category = theoretical_cogs.get('theoretical_cogs_by_category', {})

    # If we have actual COGS, calculate the scaling factors for each category
    # Actual COGS might be higher than theoretical (waste, overpouring, etc.)
    cogs_scaling_factors = {}
    if use_actual_cogs:
        category_actual_cogs_map = {
            'Liquor': cogs_summary.liquor_cogs or 0,
            'Wine': cogs_summary.wine_cogs or 0,
            'Draft Beer': cogs_summary.draft_beer_cogs or 0,
            'Bottle Beer': cogs_summary.bottle_beer_cogs or 0,
            'Juice': cogs_summary.juice_cogs or 0
        }

        # Calculate scaling factor for each category
        for category, actual_cogs in category_actual_cogs_map.items():
            theoretical_total = theoretical_cogs_by_category.get(category, 0)
            if theoretical_total > 0:
                cogs_scaling_factors[category] = actual_cogs / theoretical_total
            else:
                cogs_scaling_factors[category] = 1.0

    for item_id, usage_data in usage_results.items():
        revenue = usage_data.get('revenue', 0)
        theoretical_item_cogs = theoretical_cogs_by_item.get(item_id, 0)

        # Skip items with no revenue or COGS
        if revenue == 0 and theoretical_item_cogs == 0:
            continue

        # Get item metadata
        item = dataset.get_item(item_id)
        category = item.category if item else "Unknown"
        vendor = item.vendor if item else "Unknown"

        # Map item category to consolidated category for COGS lookup
        consolidated_category = CATEGORY_CONSOLIDATION.get(category, category)

        # Calculate actual COGS by scaling theoretical COGS
        if use_actual_cogs and consolidated_category in cogs_scaling_factors:
            actual_item_cogs = theoretical_item_cogs * cogs_scaling_factors[consolidated_category]
        else:
            actual_item_cogs = theoretical_item_cogs

        # Calculate theoretical profit (perfect scenario)
        theoretical_profit = revenue - theoretical_item_cogs
        theoretical_margin_pct = (theoretical_profit / revenue * 100) if revenue > 0 else 0

        # Calculate actual profit (real scenario)
        actual_profit = revenue - actual_item_cogs
        actual_margin_pct = (actual_profit / revenue * 100) if revenue > 0 else 0

        # Calculate variance (how much profit we're losing)
        profit_variance = theoretical_profit - actual_profit
        variance_pct = (profit_variance / theoretical_profit * 100) if theoretical_profit > 0 else 0

        # Determine status based on ACTUAL profit margin
        if actual_margin_pct >= 75:
            status = 'excellent'
        elif actual_margin_pct >= 70:
            status = 'good'
        elif actual_margin_pct >= 65:
            status = 'fair'
        else:
            status = 'poor'

        profitability_data.append({
            'item_id': item_id,
            'category': category,
            'vendor': vendor,
            'revenue': round(revenue, 2),
            'theoretical_cogs': round(theoretical_item_cogs, 2),
            'actual_cogs': round(actual_item_cogs, 2),
            'theoretical_profit': round(theoretical_profit, 2),
            'actual_profit': round(actual_profit, 2),
            'theoretical_margin_pct': round(theoretical_margin_pct, 1),
            'actual_margin_pct': round(actual_margin_pct, 1),
            'profit_variance': round(profit_variance, 2),
            'variance_pct': round(variance_pct, 1),
            'status': status
        })

    profit_df = pd.DataFrame(profitability_data)

    # Sort by actual profit descending (highest profit items first)
    if not profit_df.empty:
        profit_df = profit_df.sort_values('actual_profit', ascending=False)

    return profit_df


def get_cogs_summary(features_df: pd.DataFrame, dataset: InventoryDataset = None, week_name: str = None) -> Dict:
    """
    Get summary statistics for COGS.

    Uses the pre-calculated "Weekly COGS" section from the spreadsheet when available,
    which is more accurate than calculating from individual line items.

    Args:
        features_df: Features dataframe with cost metrics
        dataset: Optional InventoryDataset with weekly_cogs_summaries
        week_name: Optional specific week name to display (e.g., 'Q1 WK3').
                   If None, uses the most recent complete week.

    Returns:
        Dict with summary metrics
    """
    # Try to get COGS from the spreadsheet's "Weekly COGS" section (most accurate)
    if dataset is not None:
        # Get the specific week or fall back to latest complete
        if week_name:
            latest_summary = dataset.get_cogs_summary_by_name(week_name)
        else:
            latest_summary = dataset.get_latest_complete_cogs_summary()

        if latest_summary:
            # Calculate 4-week average from complete weeks
            complete_summaries = dataset.get_complete_cogs_summaries(4)
            avg_weekly_cogs = (
                sum(s.total_cogs for s in complete_summaries if s.total_cogs) / len(complete_summaries)
                if complete_summaries else 0
            )

            # Calculate YTD COGS from all complete weeks in the most recent year
            complete_summaries_all = [s for s in dataset.weekly_cogs_summaries if s.is_complete]
            if complete_summaries_all:
                most_recent_year = max(s.week_date.year for s in complete_summaries_all)
                ytd_cogs = sum(
                    s.total_cogs for s in complete_summaries_all
                    if s.week_date.year == most_recent_year and s.total_cogs
                )
            else:
                ytd_cogs = 0

            return {
                'total_weekly_cogs': round(latest_summary.total_cogs or 0, 2),
                'total_avg_weekly_cogs_4wk': round(avg_weekly_cogs, 2),
                'total_inventory_value': round(features_df['inventory_value'].sum(), 2),
                'total_cogs_ytd': round(ytd_cogs, 2),
                'items_with_cost_data': len(features_df[features_df['unit_cost'].notna()]),
                'items_missing_cost_data': len(features_df[features_df['unit_cost'].isna()]),
                # COGS by category from the spreadsheet
                'liquor_cogs': latest_summary.liquor_cogs,
                'wine_cogs': latest_summary.wine_cogs,
                'draft_beer_cogs': latest_summary.draft_beer_cogs,
                'bottle_beer_cogs': latest_summary.bottle_beer_cogs,
                'juice_cogs': latest_summary.juice_cogs,
                'week_name': latest_summary.week_name,
                'week_date': latest_summary.week_date,
            }

    # Fallback to calculating from individual items (less accurate)
    return {
        'total_weekly_cogs': round(features_df['weekly_cogs'].sum(), 2),
        'total_avg_weekly_cogs_4wk': round(features_df['avg_weekly_cogs_4wk'].sum(), 2),
        'total_inventory_value': round(features_df['inventory_value'].sum(), 2),
        'total_cogs_ytd': round(features_df['cogs_ytd'].sum(), 2),
        'items_with_cost_data': len(features_df[features_df['unit_cost'].notna()]),
        'items_missing_cost_data': len(features_df[features_df['unit_cost'].isna()])
    }
