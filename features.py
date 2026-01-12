"""
Feature Pipeline - Compute item-level features for agent decision-making.

This module replaces compute_metrics() from zifapp.py:93-153 and adds
additional features needed for intelligent ordering decisions.
"""

import pandas as pd
import numpy as np
from statsmodels.tsa.holtwinters import SimpleExpSmoothing
from models import InventoryDataset
from typing import Optional


def compute_features(
    dataset: InventoryDataset,
    smoothing_level: float = 0.3,
    trend_threshold: float = 0.1
) -> pd.DataFrame:
    """
    Compute item-level features for agent decision-making.

    This replaces and enhances compute_metrics() from zifapp.py:93-153.

    Args:
        dataset: InventoryDataset with items and records
        smoothing_level: Alpha parameter for exponential smoothing (0.1-0.9)
        trend_threshold: Threshold for trend detection (0.05-0.30)

    Returns:
        DataFrame with columns:
        - item_id
        - on_hand: Current inventory level
        - last_week_usage: Most recent week's usage
        - avg_ytd, avg_10wk, avg_4wk, avg_2wk: Various rolling averages
        - avg_highest_4, avg_lowest_4_nonzero: Peak/trough averages
        - volatility: Coefficient of variation (std/mean)
        - weeks_on_hand_ytd, weeks_on_hand_10wk, weeks_on_hand_4wk: Supply calculations
        - trend: Indicator (↑→↓)
        - recent_trend_ratio: Last 4 weeks vs prior 4 weeks
        - anomaly_negative_usage, anomaly_huge_jump, anomaly_missing_count: Data quality flags
    """

    def compute_item_features(group):
        """Compute features for a single item's weekly records."""
        usage = group['usage']
        inventory = group['on_hand']
        dates = group['week_date']

        # Basic stats
        last_week_usage = usage.iloc[-1] if not usage.empty else None
        last_10 = usage.tail(10)
        last_4 = usage.tail(4)
        last_2 = usage.tail(2)

        # YTD based on most recent year in data (not current calendar year)
        if pd.api.types.is_datetime64_any_dtype(dates) and not dates.empty:
            most_recent_year = dates.max().year
            ytd_avg = group[dates.dt.year == most_recent_year]['usage'].mean()
        else:
            ytd_avg = None

        # Volatility (coefficient of variation)
        volatility = usage.std() / usage.mean() if usage.mean() > 0 else None

        # Highest/Lowest averages
        avg_highest_4 = usage.nlargest(4).mean() if len(usage) >= 4 else usage.mean()
        non_zero_usage = usage[usage > 0]
        avg_lowest_4_nonzero = non_zero_usage.nsmallest(4).mean() if len(non_zero_usage) >= 4 else non_zero_usage.mean()

        # Weeks on hand calculations
        def safe_div(n, d):
            """Safe division, returns None if denominator is 0 or None."""
            if pd.notna(d) and d > 0:
                return round(n / d, 2)
            return None

        on_hand_val = inventory.iloc[-1] if not inventory.empty else 0
        weeks_on_hand_ytd = safe_div(on_hand_val, ytd_avg)
        weeks_on_hand_10wk = safe_div(on_hand_val, last_10.mean())
        weeks_on_hand_4wk = safe_div(on_hand_val, last_4.mean())
        weeks_on_hand_2wk = safe_div(on_hand_val, last_2.mean())
        weeks_on_hand_ath = safe_div(on_hand_val, avg_highest_4)
        weeks_on_hand_lowest4 = safe_div(on_hand_val, avg_lowest_4_nonzero)

        # Trend indicator using exponential smoothing
        trend = "→"
        if len(usage) >= 4:
            try:
                model = SimpleExpSmoothing(usage.values).fit(
                    smoothing_level=smoothing_level,
                    optimized=False
                )
                smoothed_current = model.fittedvalues[-1]
                baseline = usage.mean()
                if baseline > 0:
                    ratio = smoothed_current / baseline
                    if ratio > (1 + trend_threshold):
                        trend = "↑"
                    elif ratio < (1 - trend_threshold):
                        trend = "↓"
            except Exception:
                trend = "→"

        # Recent trend ratio (last 4 vs prior 4)
        recent_trend_ratio = None
        if len(usage) >= 8:
            recent_4 = usage.tail(4).mean()
            prior_4 = usage.tail(8).head(4).mean()
            if prior_4 > 0:
                recent_trend_ratio = recent_4 / prior_4

        # Anomaly detection
        anomaly_negative_usage = (usage < 0).any()

        anomaly_huge_jump = False
        if len(usage) >= 2:
            mean_val = usage.mean()
            if mean_val > 0:
                anomaly_huge_jump = ((usage.iloc[-1] / mean_val) > 5)

        anomaly_missing_count = len(usage) < 4

        # Check for zero usage items (possible discontinued items)
        is_zero_usage = (usage.tail(4).sum() == 0) if len(usage) >= 4 else False

        return pd.Series({
            'on_hand': round(on_hand_val, 2),
            'last_week_usage': round(last_week_usage, 2) if pd.notna(last_week_usage) else None,
            'avg_ytd': round(ytd_avg, 2) if pd.notna(ytd_avg) else None,
            'avg_10wk': round(last_10.mean(), 2) if not last_10.empty else None,
            'avg_4wk': round(last_4.mean(), 2) if not last_4.empty else None,
            'avg_2wk': round(last_2.mean(), 2) if not last_2.empty else None,
            'avg_highest_4': round(avg_highest_4, 2) if pd.notna(avg_highest_4) else None,
            'avg_lowest_4_nonzero': round(avg_lowest_4_nonzero, 2) if pd.notna(avg_lowest_4_nonzero) else None,
            'all_time_high': round(usage.max(), 2) if not usage.empty else None,
            'volatility': round(volatility, 2) if pd.notna(volatility) else None,
            'weeks_on_hand_ytd': weeks_on_hand_ytd,
            'weeks_on_hand_10wk': weeks_on_hand_10wk,
            'weeks_on_hand_4wk': weeks_on_hand_4wk,
            'weeks_on_hand_2wk': weeks_on_hand_2wk,
            'weeks_on_hand_ath': weeks_on_hand_ath,
            'weeks_on_hand_lowest4': weeks_on_hand_lowest4,
            'trend': trend,
            'recent_trend_ratio': round(recent_trend_ratio, 2) if pd.notna(recent_trend_ratio) else None,
            'anomaly_negative_usage': anomaly_negative_usage,
            'anomaly_huge_jump': anomaly_huge_jump,
            'anomaly_missing_count': anomaly_missing_count,
            'is_zero_usage': is_zero_usage,
        })

    if dataset.records.empty:
        # Return empty dataframe with correct columns
        return pd.DataFrame(columns=[
            'item_id', 'on_hand', 'last_week_usage', 'avg_ytd', 'avg_10wk', 'avg_4wk', 'avg_2wk',
            'avg_highest_4', 'avg_lowest_4_nonzero', 'all_time_high', 'volatility',
            'weeks_on_hand_ytd', 'weeks_on_hand_10wk', 'weeks_on_hand_4wk', 'weeks_on_hand_2wk',
            'weeks_on_hand_ath', 'weeks_on_hand_lowest4', 'trend', 'recent_trend_ratio',
            'anomaly_negative_usage', 'anomaly_huge_jump', 'anomaly_missing_count', 'is_zero_usage'
        ])

    # Compute features for all items
    features_df = dataset.records.groupby('item_id').apply(compute_item_features).reset_index()

    return features_df


def get_summary_stats(features_df: pd.DataFrame) -> dict:
    """
    Get summary statistics from features dataframe.

    Returns:
        Dictionary with summary metrics
    """
    return {
        'total_items': len(features_df),
        'items_low_stock': len(features_df[features_df['weeks_on_hand_4wk'] < 2.0]),
        'items_overstocked': len(features_df[features_df['weeks_on_hand_4wk'] > 8.0]),
        'items_with_anomalies': len(features_df[
            features_df['anomaly_negative_usage'] |
            features_df['anomaly_huge_jump'] |
            features_df['anomaly_missing_count']
        ]),
        'items_trending_up': len(features_df[features_df['trend'] == '↑']),
        'items_trending_down': len(features_df[features_df['trend'] == '↓']),
        'items_zero_usage': len(features_df[features_df['is_zero_usage']]),
    }
