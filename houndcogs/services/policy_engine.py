"""
Policy Engine

Applies business rules to determine order recommendations.
Each rule evaluates an item and returns a decision.
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from houndcogs.models.inventory import InventoryDataset, ItemFeatures
from houndcogs.models.orders import OrderTargets, OrderConstraints
from houndcogs.models.common import ReasonCode, Confidence

logger = logging.getLogger(__name__)


@dataclass
class PolicyResult:
    """Result of policy evaluation for an item."""
    item_id: str
    suggested_quantity: int
    reason_code: ReasonCode
    reason_text: str
    confidence: Confidence
    adjustments: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def apply_policies(
    dataset: InventoryDataset,
    features: Dict[str, ItemFeatures],
    targets: OrderTargets,
    constraints: OrderConstraints,
) -> List[PolicyResult]:
    """
    Apply policy rules to all items and return order decisions.

    Args:
        dataset: The inventory dataset
        features: Computed features by item_id
        targets: Order target configuration
        constraints: Order constraints

    Returns:
        List of PolicyResult for each item
    """
    results = []

    for item_id in dataset.get_unique_items():
        item = dataset.get_item(item_id)
        feature = features.get(item_id)

        if not item or not feature:
            continue

        # Skip items on never_order list
        if item_id in targets.never_order:
            results.append(PolicyResult(
                item_id=item_id,
                suggested_quantity=0,
                reason_code=ReasonCode.NO_ORDER,
                reason_text="Item on never-order list",
                confidence=Confidence.HIGH,
            ))
            continue

        result = _evaluate_item(item, feature, targets, constraints)
        results.append(result)

    return results


def _evaluate_item(
    item,
    feature: ItemFeatures,
    targets: OrderTargets,
    constraints: OrderConstraints,
) -> PolicyResult:
    """Evaluate a single item against all policies."""
    category = item.category.value if hasattr(item.category, 'value') else str(item.category)
    target_weeks = targets.get_target_weeks(item.item_id, category)

    adjustments = []
    warnings = []

    # Check data quality first
    if feature.has_negative_usage:
        warnings.append("Negative usage detected - data quality issue")

    if feature.has_data_gaps:
        warnings.append("Data gaps detected - estimates may be inaccurate")

    if feature.weeks_of_data < 4:
        warnings.append(f"Limited data: only {feature.weeks_of_data} weeks")

    # Determine confidence based on data quality
    if feature.has_negative_usage or feature.weeks_of_data < 4:
        confidence = Confidence.LOW
    elif feature.has_data_gaps or feature.coefficient_of_variation > 0.5:
        confidence = Confidence.MEDIUM
    else:
        confidence = Confidence.HIGH

    # Rule 1: Stockout Risk (< 1 week on hand)
    if feature.weeks_on_hand < 1.0 and feature.avg_weekly_usage_4wk > 0:
        quantity = _calculate_order_quantity(feature, target_weeks)

        # Adjust up for trending items
        if feature.trend_direction == "up":
            original = quantity
            quantity = int(quantity * 1.1)
            if quantity > original:
                adjustments.append(f"Increased 10% for upward trend")

        return PolicyResult(
            item_id=item.item_id,
            suggested_quantity=quantity,
            reason_code=ReasonCode.STOCKOUT_RISK,
            reason_text=f"Below 1 week supply ({feature.weeks_on_hand:.1f} weeks), high recent usage",
            confidence=confidence,
            adjustments=adjustments,
            warnings=warnings,
        )

    # Rule 2: Below Target
    if feature.weeks_on_hand < target_weeks:
        quantity = _calculate_order_quantity(feature, target_weeks)

        # Adjust for trends
        if feature.trend_direction == "up":
            original = quantity
            quantity = int(quantity * 1.1)
            if quantity > original:
                adjustments.append("Increased 10% for upward trend")
        elif feature.trend_direction == "down":
            original = quantity
            quantity = max(1, int(quantity * 0.9))
            if quantity < original:
                adjustments.append("Decreased 10% for downward trend")

        return PolicyResult(
            item_id=item.item_id,
            suggested_quantity=quantity,
            reason_code=ReasonCode.BELOW_TARGET,
            reason_text=f"Below {target_weeks} week target ({feature.weeks_on_hand:.1f} weeks on hand)",
            confidence=confidence,
            adjustments=adjustments,
            warnings=warnings,
        )

    # Rule 3: Trending Up (above target but increasing demand)
    if feature.trend_direction == "up" and feature.trend_strength > 0.2:
        # Proactive order even if above target
        if feature.weeks_on_hand < target_weeks * 1.5:
            quantity = _calculate_order_quantity(feature, target_weeks * 0.5)  # Partial order

            return PolicyResult(
                item_id=item.item_id,
                suggested_quantity=quantity,
                reason_code=ReasonCode.TRENDING_UP,
                reason_text=f"Demand trending up ({feature.trend_strength:.0%}), proactive restock",
                confidence=Confidence.MEDIUM,
                adjustments=adjustments,
                warnings=warnings,
            )

    # Rule 4: Overstock Warning (no order, but flag)
    if feature.weeks_on_hand > target_weeks * 2:
        return PolicyResult(
            item_id=item.item_id,
            suggested_quantity=0,
            reason_code=ReasonCode.OVERSTOCK,
            reason_text=f"Overstocked: {feature.weeks_on_hand:.1f} weeks on hand (target: {target_weeks})",
            confidence=confidence,
            adjustments=[],
            warnings=warnings,
        )

    # Default: No order needed
    return PolicyResult(
        item_id=item.item_id,
        suggested_quantity=0,
        reason_code=ReasonCode.NO_ORDER,
        reason_text=f"Adequate stock: {feature.weeks_on_hand:.1f} weeks on hand",
        confidence=confidence,
        adjustments=[],
        warnings=warnings,
    )


def _calculate_order_quantity(feature: ItemFeatures, target_weeks: float) -> int:
    """Calculate how many units to order to reach target weeks."""
    current = feature.current_on_hand
    avg_usage = feature.avg_weekly_usage_4wk

    if avg_usage <= 0:
        return 0

    target_inventory = avg_usage * target_weeks
    needed = target_inventory - current

    # Round up to whole units
    return max(0, int(needed + 0.5))
