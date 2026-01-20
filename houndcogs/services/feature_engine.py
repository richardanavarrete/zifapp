"""
Feature Engine

Computes rolling averages, trends, volatility, and other metrics
from inventory records.
"""

import logging
from typing import Dict, List

import numpy as np
import pandas as pd

from houndcogs.models.inventory import InventoryDataset, ItemFeatures, WeeklyRecord

logger = logging.getLogger(__name__)


def compute_features(dataset: InventoryDataset) -> List[ItemFeatures]:
    """
    Compute features for all items in a dataset.

    Args:
        dataset: The inventory dataset to analyze

    Returns:
        List of ItemFeatures for each unique item
    """
    if not dataset.records:
        return []

    # Convert to DataFrame for efficient computation
    df = dataset.to_dataframe()
    df['week_date'] = pd.to_datetime(df['week_date'])
    df = df.sort_values(['item_id', 'week_date'])

    features = []

    for item_id in dataset.get_unique_items():
        item_df = df[df['item_id'] == item_id].copy()

        if item_df.empty:
            continue

        item_features = _compute_item_features(item_id, item_df)
        features.append(item_features)

    logger.info(f"Computed features for {len(features)} items")
    return features


def _compute_item_features(item_id: str, item_df: pd.DataFrame) -> ItemFeatures:
    """Compute features for a single item."""
    usage = item_df['usage'].values
    n_weeks = len(usage)

    # Rolling averages
    avg_ytd = np.mean(usage) if n_weeks > 0 else 0.0
    avg_10wk = np.mean(usage[-10:]) if n_weeks >= 10 else avg_ytd
    avg_4wk = np.mean(usage[-4:]) if n_weeks >= 4 else avg_ytd
    avg_2wk = np.mean(usage[-2:]) if n_weeks >= 2 else avg_ytd

    # Current state
    current_on_hand = item_df['on_hand'].iloc[-1] if n_weeks > 0 else 0.0

    # Weeks on hand (using 4-week average as reference)
    ref_usage = avg_4wk if avg_4wk > 0 else avg_ytd
    weeks_on_hand = current_on_hand / ref_usage if ref_usage > 0 else float('inf')

    # Volatility (coefficient of variation)
    std_dev = np.std(usage) if n_weeks > 1 else 0.0
    cv = std_dev / avg_ytd if avg_ytd > 0 else 0.0

    # Trend (simple: compare recent to historical)
    trend_direction, trend_strength = _compute_trend(usage)

    # Data quality flags
    has_negative = any(u < 0 for u in usage)
    has_gaps = _has_data_gaps(item_df)

    return ItemFeatures(
        item_id=item_id,
        avg_weekly_usage_ytd=round(avg_ytd, 2),
        avg_weekly_usage_10wk=round(avg_10wk, 2),
        avg_weekly_usage_4wk=round(avg_4wk, 2),
        avg_weekly_usage_2wk=round(avg_2wk, 2),
        current_on_hand=round(current_on_hand, 2),
        weeks_on_hand=round(weeks_on_hand, 2) if weeks_on_hand != float('inf') else 999.0,
        coefficient_of_variation=round(cv, 3),
        trend_direction=trend_direction,
        trend_strength=round(trend_strength, 3),
        has_negative_usage=has_negative,
        has_data_gaps=has_gaps,
        weeks_of_data=n_weeks,
    )


def _compute_trend(usage: np.ndarray) -> tuple:
    """
    Compute trend direction and strength.

    Uses simple comparison of recent vs historical average.
    For more sophistication, could use exponential smoothing.
    """
    if len(usage) < 4:
        return "stable", 0.0

    recent = np.mean(usage[-2:])
    historical = np.mean(usage[:-2])

    if historical == 0:
        return "stable", 0.0

    change_pct = (recent - historical) / historical

    if change_pct > 0.15:
        return "up", min(abs(change_pct), 1.0)
    elif change_pct < -0.15:
        return "down", min(abs(change_pct), 1.0)
    else:
        return "stable", abs(change_pct)


def _has_data_gaps(item_df: pd.DataFrame) -> bool:
    """Check if there are gaps in the weekly data."""
    if len(item_df) < 2:
        return False

    dates = pd.to_datetime(item_df['week_date']).sort_values()
    diffs = dates.diff().dropna()

    # If any gap is more than 8 days (allowing for some variance)
    return any(d.days > 8 for d in diffs)


def compute_features_for_item(
    records: List[WeeklyRecord],
    item_id: str
) -> ItemFeatures:
    """
    Compute features for a single item from records.

    Convenience function when you don't need to process the full dataset.
    """
    if not records:
        return ItemFeatures(item_id=item_id, weeks_of_data=0)

    df = pd.DataFrame([r.model_dump() for r in records])
    df['week_date'] = pd.to_datetime(df['week_date'])
    df = df.sort_values('week_date')

    return _compute_item_features(item_id, df)


def get_feature_summary(features: List[ItemFeatures]) -> Dict:
    """Get summary statistics across all items."""
    if not features:
        return {}

    return {
        "total_items": len(features),
        "items_with_negative_usage": sum(1 for f in features if f.has_negative_usage),
        "items_with_gaps": sum(1 for f in features if f.has_data_gaps),
        "items_low_stock": sum(1 for f in features if f.weeks_on_hand < 1.0),
        "items_overstocked": sum(1 for f in features if f.weeks_on_hand > 8.0),
        "items_trending_up": sum(1 for f in features if f.trend_direction == "up"),
        "items_trending_down": sum(1 for f in features if f.trend_direction == "down"),
    }
