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

# Constants for keg adjustment scoring
MAX_WEEKS_SCORE = 10  # Maximum weeks on hand for scoring purposes
ALREADY_ORDERING_BONUS = 5  # Bonus score for items already being ordered
TRENDING_UP_BONUS = 3  # Bonus score for items trending upward


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

    # Vendor-specific keg order maximums
    # Crescent and Hensley have 21-keg maximum order size
    # When stockout risk exists, order exactly 21 kegs to rebalance inventory
    vendor_keg_max_order: Dict[str, int] = field(default_factory=dict)

    # Threshold for triggering 21-keg rebalancing order
    keg_rebalance_threshold: float = 1.0  # weeks on hand

    def __post_init__(self):
        # Set default keg maximums if not provided
        if not self.vendor_keg_max_order:
            self.vendor_keg_max_order = {
                "Crescent": 21,
                "Hensley": 21,
            }


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


def calculate_vendor_keg_totals(
    recommendations_df: pd.DataFrame,
    constraints: OrderConstraints
) -> Dict[str, dict]:
    """
    Analyze keg inventory and determine if 21-keg rebalancing order is needed.

    The 21-keg rule: When any draft beers won't make it to next week, place a
    21-keg order (the maximum allowed) and distribute it to rebalance inventory
    levels across all draft items.

    Args:
        recommendations_df: DataFrame from recommend_order()
        constraints: OrderConstraints with vendor_keg_max_order and threshold

    Returns:
        Dictionary with vendor keg analysis:
        {
            'Crescent': {
                'total_kegs': 18,
                'max_order_size': 21,
                'needs_rebalancing': True,
                'stockout_items': 3,
                'min_weeks_on_hand': 0.5,
                'items': ['BEER DFT ...', ...]
            },
            ...
        }
    """
    # Filter to draft beer items only (kegs)
    keg_items = recommendations_df[
        recommendations_df['category'].isin(['Draft Beer'])
    ]

    vendor_keg_info = {}

    for vendor, max_order in constraints.vendor_keg_max_order.items():
        vendor_kegs = keg_items[keg_items['vendor'] == vendor].copy()

        if vendor_kegs.empty:
            continue

        total_kegs = vendor_kegs['recommended_qty'].sum()
        min_weeks = vendor_kegs['weeks_on_hand'].min()

        # Check if any items are below rebalance threshold
        stockout_items = vendor_kegs[
            vendor_kegs['weeks_on_hand'] < constraints.keg_rebalance_threshold
        ]
        needs_rebalancing = len(stockout_items) > 0

        # If rebalancing needed and current order is less than max, suggest 21-keg order
        kegs_to_add = 0
        if needs_rebalancing and total_kegs < max_order:
            kegs_to_add = max_order - total_kegs

        vendor_keg_info[vendor] = {
            'total_kegs': int(total_kegs),
            'max_order_size': max_order,
            'needs_rebalancing': needs_rebalancing,
            'stockout_items': len(stockout_items),
            'min_weeks_on_hand': float(min_weeks),
            'kegs_to_add': int(kegs_to_add),
            'items': vendor_kegs['item_id'].tolist(),
            'stockout_item_ids': stockout_items['item_id'].tolist() if needs_rebalancing else []
        }

    return vendor_keg_info


def get_keg_adjustment_suggestions(
    recommendations_df: pd.DataFrame,
    vendor: str,
    kegs_to_add: int,
    dataset: 'InventoryDataset'
) -> List[dict]:
    """
    Suggest how to distribute additional kegs to rebalance inventory levels.

    The goal is to bring all draft items to a more balanced weeks_on_hand level
    by prioritizing items with the lowest inventory.

    Strategy:
    1. Prioritize items with lowest weeks on hand (most urgent)
    2. Distribute kegs to bring items closer to average level
    3. Focus on preventing stockouts first

    Args:
        recommendations_df: DataFrame from recommend_order()
        vendor: Vendor name (Crescent or Hensley)
        kegs_to_add: Number of additional kegs to distribute (usually to reach 21)
        dataset: InventoryDataset for item metadata

    Returns:
        List of suggestions with item_id, current_qty, suggested_add, reason
    """
    if kegs_to_add <= 0:
        return []

    suggestions = []
    remaining_kegs = kegs_to_add

    # Get all draft beer items from this vendor
    vendor_items = recommendations_df[
        (recommendations_df['vendor'] == vendor) &
        (recommendations_df['category'] == 'Draft Beer')
    ].copy()

    if vendor_items.empty:
        return []

    # Calculate target weeks on hand for balancing
    # Use median as target to avoid outliers
    target_weeks = vendor_items['weeks_on_hand'].median()

    # Calculate gap from target for each item
    vendor_items['_gap'] = target_weeks - vendor_items['weeks_on_hand']

    # Only consider items below target (negative gap means above target)
    items_below_target = vendor_items[vendor_items['_gap'] > 0].copy()

    if items_below_target.empty:
        # If all items are above target, distribute to lowest weeks items anyway
        items_below_target = vendor_items.copy()

    # Sort by weeks_on_hand ascending (lowest first - most urgent)
    items_below_target = items_below_target.sort_values('weeks_on_hand', ascending=True)

    # Distribute kegs starting with most urgent items
    for _, row in items_below_target.iterrows():
        if remaining_kegs <= 0:
            break

        item_id = row['item_id']
        current_qty = row['recommended_qty']
        weeks_on_hand = row['weeks_on_hand']
        avg_usage = row['avg_usage']

        # Determine how many to add based on gap and urgency
        if weeks_on_hand < 0.5:
            # Critical - add multiple if needed
            add_qty = min(2, remaining_kegs)
            reason = f"CRITICAL: {weeks_on_hand:.1f} weeks remaining"
        elif weeks_on_hand < 1.0:
            # Urgent - add at least 1
            add_qty = min(2, remaining_kegs)
            reason = f"Urgent: {weeks_on_hand:.1f} weeks, rebalancing needed"
        else:
            # Below target but not critical
            add_qty = 1
            reason = f"Rebalancing: {weeks_on_hand:.1f} weeks → target {target_weeks:.1f} weeks"

        # Calculate new weeks on hand after adding
        if avg_usage > 0:
            new_on_hand = row['on_hand'] + (current_qty + add_qty)
            new_weeks = new_on_hand / avg_usage
        else:
            new_weeks = weeks_on_hand

        suggestions.append({
            'item_id': item_id,
            'current_qty': int(current_qty),
            'suggested_add': int(add_qty),
            'new_total': int(current_qty + add_qty),
            'current_weeks': round(weeks_on_hand, 1),
            'projected_weeks': round(new_weeks, 1),
            'reason': reason
        })

        remaining_kegs -= add_qty

    return suggestions


def calculate_kegs_needed_for_target_weeks(
    recommendations_df: pd.DataFrame,
    vendor: str,
    target_weeks: float
) -> int:
    """
    Calculate how many kegs are needed to bring all items to target weeks on hand.

    Args:
        recommendations_df: DataFrame from recommend_order()
        vendor: Vendor name (Crescent or Hensley)
        target_weeks: Target weeks on hand to achieve

    Returns:
        Total number of kegs needed
    """
    vendor_items = recommendations_df[
        (recommendations_df['vendor'] == vendor) &
        (recommendations_df['category'] == 'Draft Beer')
    ].copy()

    if vendor_items.empty:
        return 0

    total_kegs = 0
    for _, row in vendor_items.iterrows():
        if row['avg_usage'] > 0:
            target_on_hand = row['avg_usage'] * target_weeks
            current_on_hand = row['on_hand']
            gap = target_on_hand - current_on_hand
            kegs_needed = max(0, math.ceil(gap))
            total_kegs += kegs_needed

    return total_kegs


def calculate_projected_weeks_from_kegs(
    recommendations_df: pd.DataFrame,
    vendor: str,
    total_kegs: int
) -> float:
    """
    Calculate the minimum weeks on hand that will result from distributing kegs evenly.

    Args:
        recommendations_df: DataFrame from recommend_order()
        vendor: Vendor name (Crescent or Hensley)
        total_kegs: Total kegs to distribute

    Returns:
        Minimum projected weeks on hand across all items
    """
    vendor_items = recommendations_df[
        (recommendations_df['vendor'] == vendor) &
        (recommendations_df['category'] == 'Draft Beer') &
        (recommendations_df['avg_usage'] > 0)
    ].copy()

    if vendor_items.empty or total_kegs <= 0:
        return 0.0

    # Simulate distribution
    vendor_items['distributed_qty'] = 0

    for _ in range(total_kegs):
        vendor_items['projected_on_hand'] = (
            vendor_items['on_hand'] + vendor_items['distributed_qty']
        )
        vendor_items['projected_weeks'] = (
            vendor_items['projected_on_hand'] / vendor_items['avg_usage']
        )
        min_idx = vendor_items['projected_weeks'].idxmin()
        vendor_items.at[min_idx, 'distributed_qty'] += 1

    # Calculate final projected weeks
    vendor_items['final_weeks'] = (
        (vendor_items['on_hand'] + vendor_items['distributed_qty']) / vendor_items['avg_usage']
    )

    return float(vendor_items['final_weeks'].min())


def distribute_kegs_to_target(
    recommendations_df: pd.DataFrame,
    vendor: str,
    total_kegs: int,
    target_weeks: float = 4.0
) -> pd.DataFrame:
    """
    Distribute a fixed number of kegs across draft items to achieve balanced inventory.

    This implements the 21-keg rule: order kegs in 21-keg increments (21, 42, 63, etc.)
    and distribute them to balance weeks on hand evenly across all items.

    Strategy:
    1. Iteratively add one keg at a time to the item with lowest weeks on hand
    2. Continue until all kegs are distributed
    3. This ensures all items end up with similar weeks on hand

    Args:
        recommendations_df: DataFrame from recommend_order()
        vendor: Vendor name (Crescent or Hensley)
        total_kegs: Total kegs to distribute (should be 21, 42, 63, etc.)
        target_weeks: Target weeks on hand to achieve (default 4.0)

    Returns:
        DataFrame with updated recommended_qty for draft items
    """
    # Get all draft beer items from this vendor
    vendor_items = recommendations_df[
        (recommendations_df['vendor'] == vendor) &
        (recommendations_df['category'] == 'Draft Beer')
    ].copy()

    if vendor_items.empty or total_kegs <= 0:
        return recommendations_df

    # Initialize distributed quantity
    vendor_items['distributed_qty'] = 0

    # Filter to items with positive usage (can't balance items we don't sell)
    active_items = vendor_items[vendor_items['avg_usage'] > 0].copy()

    if active_items.empty:
        # No active items, distribute evenly to all items
        kegs_per_item = total_kegs // len(vendor_items)
        vendor_items['distributed_qty'] = kegs_per_item
    else:
        # Iteratively distribute kegs to balance weeks on hand
        for _ in range(total_kegs):
            # Calculate current weeks on hand for each active item
            active_items['projected_on_hand'] = (
                active_items['on_hand'] + active_items['distributed_qty']
            )
            active_items['projected_weeks'] = (
                active_items['projected_on_hand'] / active_items['avg_usage']
            )

            # Find item with lowest projected weeks on hand
            min_idx = active_items['projected_weeks'].idxmin()

            # Give that item one more keg
            active_items.at[min_idx, 'distributed_qty'] += 1

        # Update vendor_items with distributed quantities from active_items
        for idx in active_items.index:
            vendor_items.at[idx, 'distributed_qty'] = active_items.at[idx, 'distributed_qty']

    # Update the main recommendations DataFrame
    result_df = recommendations_df.copy()
    for idx, row in vendor_items.iterrows():
        item_id = row['item_id']
        new_qty = int(row['distributed_qty'])
        result_df.loc[result_df['item_id'] == item_id, 'recommended_qty'] = new_qty

    return result_df
