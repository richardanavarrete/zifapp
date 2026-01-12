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

import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import hashlib

from models import InventoryDataset
from features import compute_features
from policy import recommend_order, generate_order_summary, OrderTargets, OrderConstraints
from storage import save_agent_run, get_user_prefs, init_db
import mappings


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
    custom_constraints: Optional[OrderConstraints] = None
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

    Returns:
        Dictionary with:
        - run_id: Unique identifier for this run
        - recommendations: DataFrame with order recommendations
        - summary: Text summary of the run
        - summary_stats: Dictionary with detailed statistics
        - items_needing_recount: List of item IDs flagged for data issues
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

    # Step 6: Identify items needing recount
    items_needing_recount = []
    for _, row in recommendations_df.iterrows():
        reason_codes = row['reason_codes']
        if any(code.startswith('DATA_ISSUE') for code in reason_codes):
            items_needing_recount.append(row['item_id'])

    # Step 7: Generate summary
    summary_stats = generate_order_summary(recommendations_df)

    summary_text = (
        f"Total items: {summary_stats['total_items']} | "
        f"To order: {summary_stats['items_to_order']} | "
        f"Total qty: {summary_stats['total_qty']}"
    )

    if summary_stats['stockout_risks'] > 0:
        summary_text += f" | ⚠️ {summary_stats['stockout_risks']} stockout risks"

    # Step 8: Save run to storage
    run_id = generate_run_id(dataset)
    save_agent_run(
        run_id,
        recommendations_df,
        summary_text,
        usage_column=usage_column
    )

    # Step 9: Return results
    return {
        'run_id': run_id,
        'recommendations': recommendations_df,
        'summary': summary_text,
        'summary_stats': summary_stats,
        'items_needing_recount': items_needing_recount,
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
