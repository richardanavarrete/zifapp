"""
Policy Engine - Rules-based decision making for order recommendations.

This is the "agent brain v0" - makes intelligent ordering decisions
without requiring an LLM.
"""

import pandas as pd
import math
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from models import InventoryDataset


@dataclass
class OrderTargets:
    """Configuration for ordering targets."""

    # Default target weeks by category
    target_weeks_by_category: Dict[str, float] = field(default_factory=dict)

    # Item-specific overrides
    item_overrides: Dict[str, float] = field(default_factory=dict)

    # Items to never order
    never_order: List[str] = field(default_factory=list)

    def __post_init__(self):
        # Set defaults if not provided
        if not self.target_weeks_by_category:
            self.target_weeks_by_category = {
                "Draft Beer": 2.0,
                "Bottled Beer": 2.5,
                "Whiskey": 4.0,
                "Vodka": 4.0,
                "Gin": 5.0,
                "Tequila": 4.0,
                "Rum": 5.0,
                "Scotch": 6.0,
                "Well": 3.0,
                "Liqueur": 6.0,
                "Cordials": 8.0,
                "Wine": 3.0,
                "Juice": 2.0,
                "Bar Consumables": 3.0,
            }

    def get_target_weeks(self, item_id: str, category: str) -> float:
        """Get target weeks for an item (checks overrides first)."""
        if item_id in self.item_overrides:
            return self.item_overrides[item_id]
        return self.target_weeks_by_category.get(category, 4.0)


@dataclass
class OrderConstraints:
    """Constraints for ordering."""
    max_total_spend: Optional[float] = None
    max_total_cases: Optional[int] = None
    vendor_minimums: Dict[str, float] = field(default_factory=dict)

    # Minimum order quantity per item (skip items below this)
    min_order_qty: int = 1


def recommend_order(
    dataset: InventoryDataset,
    features_df: pd.DataFrame,
    targets: OrderTargets,
    constraints: OrderConstraints,
    usage_column: str = 'avg_4wk'  # Which average to use
) -> pd.DataFrame:
    """
    Generate order recommendations based on rules and targets.

    Args:
        dataset: InventoryDataset with item metadata
        features_df: DataFrame from compute_features()
        targets: OrderTargets configuration
        constraints: OrderConstraints configuration
        usage_column: Which usage average to use ('avg_4wk', 'avg_10wk', etc.)

    Returns:
        DataFrame with columns:
        - item_id, vendor, category
        - on_hand, avg_usage, weeks_on_hand, target_weeks
        - recommended_qty
        - reason_codes (JSON string of list)
        - confidence (high/medium/low)
        - notes (plain text)
    """

    recommendations = []

    for _, row in features_df.iterrows():
        item_id = row['item_id']
        item = dataset.get_item(item_id)

        if not item:
            continue

        # Skip items flagged as never order
        if item_id in targets.never_order:
            continue

        # Get target weeks for this item
        target_weeks = targets.get_target_weeks(item_id, item.category)

        # Get usage metric
        avg_usage = row.get(usage_column, row.get('avg_4wk', 0))
        if pd.isna(avg_usage) or avg_usage <= 0:
            avg_usage = 0

        on_hand = row['on_hand']
        weeks_on_hand = on_hand / avg_usage if avg_usage > 0 else 999

        # Calculate order quantity
        target_inventory = target_weeks * avg_usage
        order_qty = max(0, target_inventory - on_hand)

        # Round up to whole bottles
        order_qty = int(math.ceil(order_qty))

        # Round to cases if case_size is known
        if item.case_size and order_qty > 0:
            # Round up to nearest case
            order_qty = ((order_qty + item.case_size - 1) // item.case_size) * item.case_size

        # Determine reason codes, confidence, and notes
        reason_codes = []
        confidence = "high"
        notes = ""

        # Check for data issues first
        if row.get('anomaly_negative_usage', False):
            reason_codes.append("DATA_ISSUE_NEGATIVE")
            confidence = "low"
            notes += "⚠️ Negative usage detected. Verify inventory counts. "
            order_qty = 0  # Don't order if data is bad

        if row.get('anomaly_huge_jump', False):
            reason_codes.append("DATA_ISSUE_JUMP")
            if confidence == "high":
                confidence = "medium"
            notes += "⚠️ Usage jumped >5x average. Verify recent count. "

        if row.get('anomaly_missing_count', False):
            reason_codes.append("INSUFFICIENT_DATA")
            if confidence == "high":
                confidence = "low"
            notes += "ℹ️ Less than 4 weeks of data. "

        # Check for zero usage (discontinued items)
        if row.get('is_zero_usage', False):
            reason_codes.append("ZERO_USAGE")
            notes += "⚠️ No usage in last 4 weeks. Check if item is discontinued. "
            order_qty = 0  # Don't order zero-usage items

        # Stock level assessment
        if weeks_on_hand < 1.0 and avg_usage > 0:
            reason_codes.append("STOCKOUT_RISK")
            notes += "🔴 CRITICAL: Less than 1 week of inventory. "
        elif weeks_on_hand < target_weeks * 0.5 and avg_usage > 0:
            reason_codes.append("LOW_STOCK")
            notes += "🟡 Below 50% of target weeks. "

        if weeks_on_hand > target_weeks * 2:
            reason_codes.append("OVERSTOCK")
            notes += "🟢 Inventory exceeds 2x target. Consider reducing order. "
            # Reduce order if overstocked
            order_qty = int(order_qty * 0.5)  # Order 50% of calculated amount

        # Volatility assessment
        volatility = row.get('volatility', 0)
        if volatility > 1.0:
            reason_codes.append("VOLATILE")
            if confidence == "high":
                confidence = "medium"
            notes += "⚡ High volatility in usage pattern. "

        # Trend analysis
        if row.get('trend') == '↑':
            reason_codes.append("TRENDING_UP")
            notes += "📈 Usage trending upward. "
            # Increase order by 10% if trending up
            if order_qty > 0 and confidence in ["high", "medium"]:
                order_qty = int(order_qty * 1.1)
        elif row.get('trend') == '↓':
            reason_codes.append("TRENDING_DOWN")
            notes += "📉 Usage trending downward. "
            # Decrease order by 10% if trending down
            if order_qty > 0:
                order_qty = int(order_qty * 0.9)

        # Recent trend ratio
        recent_trend_ratio = row.get('recent_trend_ratio')
        if recent_trend_ratio and recent_trend_ratio > 1.3:
            reason_codes.append("ACCELERATING")
            notes += "🚀 Usage accelerating (recent 4 weeks vs prior). "
        elif recent_trend_ratio and recent_trend_ratio < 0.7:
            reason_codes.append("DECELERATING")
            notes += "🔻 Usage decelerating. "

        # Apply minimum order quantity constraint
        if 0 < order_qty < constraints.min_order_qty:
            order_qty = 0
            reason_codes.append("BELOW_MIN_QTY")

        # Default reason if no specific reason found
        if not reason_codes and order_qty > 0:
            reason_codes.append("ROUTINE_RESTOCK")

        if not reason_codes and order_qty == 0:
            reason_codes.append("NO_ORDER_NEEDED")
            notes += "✓ Adequate inventory levels. "

        recommendations.append({
            'item_id': item_id,
            'vendor': item.vendor,
            'category': item.category,
            'on_hand': round(on_hand, 2),
            'avg_usage': round(avg_usage, 2),
            'weeks_on_hand': round(weeks_on_hand, 1),
            'target_weeks': round(target_weeks, 1),
            'recommended_qty': order_qty,
            'reason_codes': reason_codes,  # Will be JSON-encoded when saved
            'confidence': confidence,
            'notes': notes.strip()
        })

    rec_df = pd.DataFrame(recommendations)

    if rec_df.empty:
        return rec_df

    # Sort: prioritize stockout risks, then by vendor, then by category
    rec_df['_priority'] = rec_df['reason_codes'].apply(
        lambda codes: 0 if 'STOCKOUT_RISK' in codes else
                     1 if 'LOW_STOCK' in codes else
                     2 if 'ROUTINE_RESTOCK' in codes else 3
    )
    rec_df = rec_df.sort_values(['_priority', 'vendor', 'category', 'item_id'])
    rec_df = rec_df.drop(columns=['_priority'])

    return rec_df


def generate_order_summary(recommendations_df: pd.DataFrame) -> dict:
    """
    Generate a summary of the order recommendations.

    Args:
        recommendations_df: DataFrame from recommend_order()

    Returns:
        Dictionary with summary metrics
    """
    items_to_order = recommendations_df[recommendations_df['recommended_qty'] > 0]

    summary = {
        'total_items': len(recommendations_df),
        'items_to_order': len(items_to_order),
        'total_qty': items_to_order['recommended_qty'].sum(),
        'items_by_vendor': items_to_order.groupby('vendor')['item_id'].count().to_dict(),
        'qty_by_vendor': items_to_order.groupby('vendor')['recommended_qty'].sum().to_dict(),
        'items_by_category': items_to_order.groupby('category')['item_id'].count().to_dict(),
        'stockout_risks': len(recommendations_df[
            recommendations_df['reason_codes'].apply(lambda x: 'STOCKOUT_RISK' in x)
        ]),
        'low_confidence': len(recommendations_df[recommendations_df['confidence'] == 'low']),
    }

    return summary
