"""
Agent Orchestrator - Ties together all components into a single workflow.

This module provides the main run_agent() function that:
1. Enriches dataset with mappings
2. Computes features
3. Loads user preferences
4. Generates recommendations
5. Identifies items needing recount
6. Saves run to storage
7. Returns structured results
"""

import hashlib
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

import mappings
from features import compute_features
from models import InventoryDataset
from policy import (
    OrderConstraints,
    OrderTargets,
    calculate_vendor_keg_totals,
    generate_order_summary,
    get_keg_adjustment_suggestions,
    recommend_order,
)
from storage import get_user_prefs, init_db, save_agent_run


def analyze_usage_variance(
    features_df: pd.DataFrame,
    sales_mix_usage: Dict,
    variance_threshold: float = 10.0
) -> List[Dict]:
    """
    Compare theoretical usage from sales mix against actual usage from inventory.

    Identifies items where counts might be off based on significant variance
    between what was sold (theoretical) vs what was used (actual).

    Automatically accounts for batch products: if ingredients are in batched form
    (e.g., Milagro Silver in Milagro Marg On Tap), converts batch inventory back
    to ingredient bottles for accurate "true on-hand" variance calculation.

    Args:
        features_df: DataFrame with item features including last_week_usage
        sales_mix_usage: Dict from aggregate_all_usage() with theoretical usage
        variance_threshold: Percentage threshold to flag as significant (default 10%)

    Returns:
        List of dicts with variance analysis for items exceeding threshold:
        - item_id: Inventory item name
        - theoretical_usage: Expected usage from sales data
        - actual_usage: Actual usage from inventory (includes batch equivalents)
        - variance: Difference (theoretical - actual)
        - variance_pct: Percentage variance relative to actual
        - unit: Unit of measurement (kegs, bottles, oz, etc.)
        - details: List of calculation details from sales mix
        - interpretation: Human-readable explanation of what this variance means
        - severity: 'high', 'medium', or 'low' based on variance percentage
    """
    from config.batch_products import BATCH_PRODUCTS, convert_batch_to_ingredients

    variance_items = []

    # Create lookup for features by item_id
    features_lookup = features_df.set_index('item_id').to_dict('index')

    # Build reverse lookup: ingredient -> batch products that contain it
    ingredient_to_batches = {}
    for batch_name, batch_config in BATCH_PRODUCTS.items():
        for ingredient_name in batch_config['ingredients'].keys():
            if ingredient_name not in ingredient_to_batches:
                ingredient_to_batches[ingredient_name] = []
            ingredient_to_batches[ingredient_name].append(batch_name)

    for inv_item, data in sales_mix_usage.items():
        theoretical_usage = data.get('theoretical_usage', 0)
        unit = data.get('unit', 'units')
        details = data.get('details', [])

        # Get actual usage from features
        if inv_item in features_lookup:
            actual_usage = features_lookup[inv_item].get('last_week_usage')
            batch_notes = []

            # Add batch inventory equivalents if this ingredient is in batch products
            if inv_item in ingredient_to_batches and actual_usage is not None:
                for batch_name in ingredient_to_batches[inv_item]:
                    # Check if we have inventory for this batch product
                    if batch_name in features_lookup:
                        batch_on_hand = features_lookup[batch_name].get('on_hand', 0)
                        if batch_on_hand and batch_on_hand > 0:
                            # Convert batch to oz (batch is tracked in liters in inventory)
                            batch_oz = batch_on_hand * 33.814  # Convert liters to oz

                            # Convert to ingredient bottles
                            batch_ingredients = convert_batch_to_ingredients(batch_name, batch_oz)
                            if inv_item in batch_ingredients:
                                batch_equiv_bottles = batch_ingredients[inv_item]
                                actual_usage += batch_equiv_bottles
                                batch_notes.append(
                                    f"  + {batch_equiv_bottles:.2f} bottles from {batch_name} "
                                    f"({batch_on_hand:.1f}L on hand)"
                                )

            # Only analyze if we have valid actual usage
            if actual_usage is not None and actual_usage > 0:
                variance = theoretical_usage - actual_usage
                variance_pct = (variance / actual_usage) * 100

                # Only include items that exceed threshold
                if abs(variance_pct) >= variance_threshold:
                    # Determine severity
                    abs_var_pct = abs(variance_pct)
                    if abs_var_pct >= 50:
                        severity = 'high'
                    elif abs_var_pct >= 25:
                        severity = 'medium'
                    else:
                        severity = 'low'

                    # Generate interpretation
                    if variance > 0:
                        # Theoretical > Actual: Should have used more
                        interpretation = (
                            f"📉 Used {abs(variance):.1f} {unit} LESS than expected. "
                            f"Possible causes: Over-counting inventory, theft, waste, spillage, or "
                            f"drinks not rung up correctly in POS."
                        )
                    else:
                        # Theoretical < Actual: Used more than expected
                        interpretation = (
                            f"📈 Used {abs(variance):.1f} {unit} MORE than expected. "
                            f"Possible causes: Under-counting inventory, over-ringing items, "
                            f"comps not tracked in POS, or heavy pours."
                        )

                    # Append batch notes to details if any
                    all_details = details.copy()
                    if batch_notes:
                        all_details.append("")  # Empty line separator
                        all_details.append("Batch Inventory Included:")
                        all_details.extend(batch_notes)

                    variance_items.append({
                        'item_id': inv_item,
                        'theoretical_usage': round(theoretical_usage, 2),
                        'actual_usage': round(actual_usage, 2),
                        'variance': round(variance, 2),
                        'variance_pct': round(variance_pct, 1),
                        'unit': unit,
                        'details': all_details,
                        'interpretation': interpretation,
                        'severity': severity
                    })

    # Sort by absolute variance percentage (highest first)
    variance_items.sort(key=lambda x: abs(x['variance_pct']), reverse=True)

    return variance_items


def generate_run_id(dataset: InventoryDataset) -> str:
    """
    Generate a unique run ID based on dataset and timestamp.

    Args:
        dataset: InventoryDataset to generate ID for

    Returns:
        Unique run ID string
    """
    timestamp = datetime.now().isoformat()
    total_records = len(dataset.records)
    date_range = dataset.get_date_range()

    hash_input = f"{timestamp}_{total_records}_{date_range}".encode()
    short_hash = hashlib.md5(hash_input).hexdigest()[:8]

    return f"run_{short_hash}"


def run_agent(
    dataset: InventoryDataset,
    usage_column: str = 'avg_4wk',
    smoothing_level: float = 0.3,
    trend_threshold: float = 0.1,
    custom_targets: Optional[OrderTargets] = None,
    custom_constraints: Optional[OrderConstraints] = None,
    sales_mix_usage: Optional[Dict] = None
) -> Dict:
    """
    Execute a complete agent run.

    This is the main entry point for the agent system. It orchestrates
    all the steps needed to generate ordering recommendations.

    Steps:
    1. Initialize database
    2. Enrich dataset with vendor/category/location mappings
    3. Compute item features (usage, trends, anomalies)
    4. Load user preferences from storage
    5. Generate order recommendations using policy engine
    6. Identify items needing recount (data quality issues)
    7. Generate summary statistics
    8. Save run to storage
    9. Return structured results

    Args:
        dataset: InventoryDataset with items and records
        usage_column: Which usage average to use ('avg_4wk', 'avg_10wk', etc.)
        smoothing_level: Exponential smoothing parameter (0.1-0.9)
        trend_threshold: Trend detection threshold (0.05-0.30)
        custom_targets: Optional custom OrderTargets (overrides defaults)
        custom_constraints: Optional custom OrderConstraints
        sales_mix_usage: Optional dict from aggregate_all_usage() with theoretical usage
                         based on sales mix data. Format: {inv_item: {theoretical_usage, unit, details}}

    Returns:
        Dictionary with:
        - run_id: Unique identifier for this run
        - recommendations: DataFrame with order recommendations
        - summary: Text summary of the run
        - summary_stats: Dictionary with detailed statistics
        - items_needing_recount: List of dicts with detailed recount info:
            - item_id, on_hand, avg_usage, last_week_usage
            - issue_type, issue_description, discrepancy
            - expected_on_hand or expected_usage (depending on issue type)
        - vendor_keg_info: Dict with Crescent/Hensley keg rebalancing analysis:
            - total_kegs, max_order_size (21), kegs_to_add
            - needs_rebalancing, stockout_items, min_weeks_on_hand
            - rebalancing_suggestions (if rebalancing needed)
        - usage_variance_analysis: List of dicts with theoretical vs actual comparison
            (only when sales_mix_usage is provided):
            - item_id, theoretical_usage, actual_usage, variance, variance_pct
            - unit, details (calculation breakdown), interpretation, severity
        - dataset: The enriched InventoryDataset
        - features: DataFrame with computed features
    """

    # Step 1: Ensure database is initialized
    init_db()

    # Step 2: Enrich dataset with mappings
    dataset = mappings.enrich_dataset(dataset)

    # Step 3: Compute features
    features_df = compute_features(
        dataset,
        smoothing_level=smoothing_level,
        trend_threshold=trend_threshold
    )

    if features_df.empty:
        # Return empty result if no data
        return {
            'run_id': None,
            'recommendations': pd.DataFrame(),
            'summary': 'No data available',
            'summary_stats': {},
            'items_needing_recount': [],
            'vendor_keg_info': {},
            'dataset': dataset,
            'features': features_df
        }

    # Step 4: Load user preferences and build targets
    user_prefs = get_user_prefs()

    if custom_targets:
        targets = custom_targets
    else:
        targets = OrderTargets()

    # Apply user preferences to targets
    for item_id, prefs in user_prefs.items():
        if prefs.get('target_weeks_override'):
            targets.item_overrides[item_id] = prefs['target_weeks_override']
        if prefs.get('never_order'):
            if item_id not in targets.never_order:
                targets.never_order.append(item_id)

    # Step 5: Generate recommendations
    if custom_constraints:
        constraints = custom_constraints
    else:
        constraints = OrderConstraints()

    recommendations_df = recommend_order(
        dataset,
        features_df,
        targets,
        constraints,
        usage_column=usage_column
    )

    # Step 6: Identify items needing recount with detailed information
    # Create lookup dict for efficient access to features
    features_lookup = features_df.set_index('item_id')['last_week_usage'].to_dict()

    items_needing_recount = []
    for _, row in recommendations_df.iterrows():
        reason_codes = row['reason_codes']
        if any(code.startswith('DATA_ISSUE') for code in reason_codes):
            item_id = row['item_id']
            # Build detailed recount info
            recount_info = {
                'item_id': item_id,
                'on_hand': row['on_hand'],
                'avg_usage': row['avg_usage'],
                'last_week_usage': features_lookup.get(item_id),
                'reason_codes': [code for code in reason_codes if code.startswith('DATA_ISSUE')],
                'notes': row['notes'],
                'expected_on_hand': None,  # Will be calculated based on issue type
                'discrepancy': None,
                'has_sales_mix_data': False  # Flag to indicate if sales mix data is available
            }

            # Check if we have sales mix data for this item
            sales_mix_expected = None
            if sales_mix_usage and item_id in sales_mix_usage:
                sales_mix_data = sales_mix_usage[item_id]
                sales_mix_expected = sales_mix_data.get('theoretical_usage')
                sales_mix_unit = sales_mix_data.get('unit', 'units')
                recount_info['has_sales_mix_data'] = True
                recount_info['sales_mix_expected_usage'] = sales_mix_expected
                recount_info['sales_mix_unit'] = sales_mix_unit
                recount_info['sales_mix_details'] = sales_mix_data.get('details', [])

            # Calculate expected values based on issue type
            if 'DATA_ISSUE_NEGATIVE' in reason_codes:
                recount_info['issue_type'] = 'Negative Usage'
                recount_info['issue_description'] = 'Usage calculation resulted in negative value, indicating inventory count may be incorrect.'

                # For negative usage: the calculated usage = (prev_on_hand + purchases - current_on_hand) was negative
                # This usually means current_on_hand was counted too high relative to last week.
                # Expected on_hand = current_on_hand + expected_usage shows what it SHOULD have been at start of week
                # (i.e., if we used X bottles, we should have started with current + X)
                # Use sales mix data if available, otherwise fall back to avg usage
                if sales_mix_expected is not None:
                    recount_info['expected_on_hand'] = round(row['on_hand'] + sales_mix_expected, 2)
                    recount_info['discrepancy'] = f"Expected ~{recount_info['expected_on_hand']:.1f} based on sales mix ({sales_mix_expected:.1f} {sales_mix_unit}/week)"
                elif recount_info['avg_usage'] and recount_info['avg_usage'] > 0:
                    recount_info['expected_on_hand'] = round(row['on_hand'] + recount_info['avg_usage'], 2)
                    recount_info['discrepancy'] = f"Expected ~{recount_info['expected_on_hand']:.1f} based on avg usage of {recount_info['avg_usage']:.1f}/week"

            elif 'DATA_ISSUE_JUMP' in reason_codes:
                recount_info['issue_type'] = 'Usage Spike'
                recount_info['issue_description'] = 'Last week usage was >5x the average, suggesting a counting error.'

                # Use sales mix data if available, otherwise fall back to avg usage
                if sales_mix_expected is not None:
                    recount_info['expected_usage'] = round(sales_mix_expected, 2)
                    recount_info['actual_usage'] = round(recount_info['last_week_usage'], 2) if recount_info['last_week_usage'] else None
                    recount_info['discrepancy'] = f"Used {recount_info['actual_usage']:.1f} last week vs sales mix expected of {recount_info['expected_usage']:.1f} {sales_mix_unit}"
                elif recount_info['avg_usage'] and recount_info['last_week_usage']:
                    recount_info['expected_usage'] = round(recount_info['avg_usage'], 2)
                    recount_info['actual_usage'] = round(recount_info['last_week_usage'], 2)
                    recount_info['discrepancy'] = f"Used {recount_info['actual_usage']:.1f} last week vs avg of {recount_info['expected_usage']:.1f}/week"

            items_needing_recount.append(recount_info)

    # Step 7.5: Calculate vendor keg totals and suggestions for Crescent/Hensley
    vendor_keg_info = calculate_vendor_keg_totals(recommendations_df, constraints)

    # Add rebalancing suggestions for vendors that need it
    for vendor, info in vendor_keg_info.items():
        if info['needs_rebalancing'] and info['kegs_to_add'] > 0:
            suggestions = get_keg_adjustment_suggestions(
                recommendations_df, vendor, info['kegs_to_add'], dataset
            )
            vendor_keg_info[vendor]['rebalancing_suggestions'] = suggestions

    # Step 7.6: Analyze usage variance if sales mix data is available
    usage_variance_analysis = []
    if sales_mix_usage:
        usage_variance_analysis = analyze_usage_variance(
            features_df,
            sales_mix_usage,
            variance_threshold=10.0
        )

    # Step 8: Generate summary
    summary_stats = generate_order_summary(recommendations_df)

    summary_text = (
        f"Total items: {summary_stats['total_items']} | "
        f"To order: {summary_stats['items_to_order']} | "
        f"Total qty: {summary_stats['total_qty']}"
    )

    if summary_stats['stockout_risks'] > 0:
        summary_text += f" | ⚠️ {summary_stats['stockout_risks']} stockout risks"

    # Add keg rebalancing info to summary
    for vendor, info in vendor_keg_info.items():
        if info['needs_rebalancing'] and info['kegs_to_add'] > 0:
            summary_text += f" | 🍺 {vendor}: {info['stockout_items']} items need rebalancing (order 21 kegs)"

    # Add variance analysis info to summary
    if usage_variance_analysis:
        high_variance_count = sum(1 for item in usage_variance_analysis if item['severity'] == 'high')
        if high_variance_count > 0:
            summary_text += f" | 🔍 {len(usage_variance_analysis)} variance alerts ({high_variance_count} high priority)"
        else:
            summary_text += f" | 🔍 {len(usage_variance_analysis)} variance alerts"

    # Step 9: Save run to storage
    run_id = generate_run_id(dataset)
    save_agent_run(
        run_id,
        recommendations_df,
        summary_text,
        usage_column=usage_column
    )

    # Step 10: Return results
    return {
        'run_id': run_id,
        'recommendations': recommendations_df,
        'summary': summary_text,
        'summary_stats': summary_stats,
        'items_needing_recount': items_needing_recount,
        'vendor_keg_info': vendor_keg_info,
        'usage_variance_analysis': usage_variance_analysis,
        'dataset': dataset,
        'features': features_df
    }


def get_order_by_vendor(recommendations_df: pd.DataFrame, vendor: str) -> pd.DataFrame:
    """
    Filter recommendations to a specific vendor.

    Args:
        recommendations_df: DataFrame from run_agent()
        vendor: Vendor name to filter to

    Returns:
        Filtered DataFrame with only items from that vendor
    """
    return recommendations_df[recommendations_df['vendor'] == vendor].copy()


def get_order_by_category(recommendations_df: pd.DataFrame, category: str) -> pd.DataFrame:
    """
    Filter recommendations to a specific category.

    Args:
        recommendations_df: DataFrame from run_agent()
        category: Category name to filter to

    Returns:
        Filtered DataFrame with only items from that category
    """
    return recommendations_df[recommendations_df['category'] == category].copy()


def export_order_csv(recommendations_df: pd.DataFrame, filename: str, items_to_order_only: bool = True):
    """
    Export recommendations to CSV.

    Args:
        recommendations_df: DataFrame from run_agent()
        filename: Path to save CSV to
        items_to_order_only: If True, only export items with qty > 0
    """
    if items_to_order_only:
        export_df = recommendations_df[recommendations_df['recommended_qty'] > 0]
    else:
        export_df = recommendations_df

    # Select and order columns for export
    export_columns = [
        'item_id', 'vendor', 'category', 'on_hand', 'avg_usage',
        'weeks_on_hand', 'target_weeks', 'recommended_qty',
        'confidence', 'notes'
    ]

    export_df[export_columns].to_csv(filename, index=False)
