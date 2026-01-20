"""
Ordering Agent

Orchestrates the order recommendation process:
1. Load dataset
2. Compute features
3. Apply policy rules
4. Generate recommendations
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from houndcogs.models.common import Confidence, ReasonCode
from houndcogs.models.inventory import InventoryDataset
from houndcogs.models.orders import (
    AgentRun,
    AgentRunSummary,
    OrderConstraints,
    OrderTargets,
    Recommendation,
    VendorSummary,
)
from houndcogs.services.feature_engine import compute_features
from houndcogs.services.policy_engine import apply_policies

logger = logging.getLogger(__name__)


def run_agent(
    dataset: InventoryDataset,
    targets: Optional[OrderTargets] = None,
    constraints: Optional[OrderConstraints] = None,
    run_id: Optional[str] = None,
) -> AgentRun:
    """
    Run the ordering agent to generate recommendations.

    Args:
        dataset: The inventory dataset to analyze
        targets: Order target configuration (uses defaults if not provided)
        constraints: Order constraints (uses defaults if not provided)
        run_id: Optional run ID (generated if not provided)

    Returns:
        AgentRun with all recommendations and summary
    """
    run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
    targets = targets or OrderTargets()
    constraints = constraints or OrderConstraints()

    logger.info(f"Starting agent run {run_id} for dataset {dataset.dataset_id}")

    # Step 1: Compute features
    features = compute_features(dataset)
    features_by_item = {f.item_id: f for f in features}

    logger.info(f"Computed features for {len(features)} items")

    # Step 2: Apply policies to get order decisions
    policy_results = apply_policies(
        dataset=dataset,
        features=features_by_item,
        targets=targets,
        constraints=constraints,
    )

    logger.info(f"Policy engine returned {len(policy_results)} decisions")

    # Step 3: Convert to recommendations
    recommendations = []
    warnings = []

    for result in policy_results:
        item = dataset.get_item(result.item_id)
        if not item:
            warnings.append({
                "item_id": result.item_id,
                "message": "Item not found in dataset"
            })
            continue

        feature = features_by_item.get(result.item_id)

        rec = Recommendation(
            item_id=result.item_id,
            display_name=item.display_name,
            category=item.category.value if hasattr(item.category, 'value') else str(item.category),
            vendor=item.vendor.value if hasattr(item.vendor, 'value') else str(item.vendor),
            current_on_hand=feature.current_on_hand if feature else 0.0,
            weeks_on_hand=feature.weeks_on_hand if feature else 0.0,
            avg_weekly_usage=feature.avg_weekly_usage_4wk if feature else 0.0,
            suggested_order=result.suggested_quantity,
            unit_cost=item.unit_cost,
            total_cost=result.suggested_quantity * item.unit_cost,
            reason_code=result.reason_code,
            reason_text=result.reason_text,
            confidence=result.confidence,
            adjustments=result.adjustments,
            warnings=result.warnings,
        )

        recommendations.append(rec)

        # Collect warnings
        for warning in result.warnings:
            warnings.append({
                "item_id": result.item_id,
                "message": warning
            })

    # Step 4: Build summary
    summary = _build_summary(recommendations)

    # Step 5: Apply constraints (budget limits, vendor minimums)
    recommendations = _apply_constraints(recommendations, constraints, warnings)

    # Rebuild summary after constraints
    summary = _build_summary(recommendations)

    return AgentRun(
        run_id=run_id,
        dataset_id=dataset.dataset_id,
        created_at=datetime.utcnow(),
        targets=targets,
        constraints=constraints,
        summary=summary,
        recommendations=recommendations,
        warnings=warnings,
    )


def _build_summary(recommendations: List[Recommendation]) -> AgentRunSummary:
    """Build summary statistics from recommendations."""
    by_vendor: Dict[str, VendorSummary] = {}
    by_category: Dict[str, int] = {}
    by_reason: Dict[str, int] = {}

    for rec in recommendations:
        if rec.suggested_order == 0:
            continue

        # By vendor
        if rec.vendor not in by_vendor:
            by_vendor[rec.vendor] = VendorSummary(
                vendor=rec.vendor,
                items_count=0,
                total_spend=0.0,
            )
        by_vendor[rec.vendor].items_count += 1
        by_vendor[rec.vendor].total_spend += rec.total_cost

        # By category
        by_category[rec.category] = by_category.get(rec.category, 0) + 1

        # By reason
        reason_key = rec.reason_code.value if hasattr(rec.reason_code, 'value') else str(rec.reason_code)
        by_reason[reason_key] = by_reason.get(reason_key, 0) + 1

    total_items = sum(1 for r in recommendations if r.suggested_order > 0)
    total_spend = sum(r.total_cost for r in recommendations)
    items_with_warnings = sum(1 for r in recommendations if r.warnings)

    return AgentRunSummary(
        total_items=total_items,
        total_spend=round(total_spend, 2),
        items_with_warnings=items_with_warnings,
        by_vendor=by_vendor,
        by_category=by_category,
        by_reason=by_reason,
    )


def _apply_constraints(
    recommendations: List[Recommendation],
    constraints: OrderConstraints,
    warnings: List[Dict],
) -> List[Recommendation]:
    """Apply budget and vendor constraints to recommendations."""
    # Sort by priority (stockout risk first, then by confidence)
    priority_order = {
        ReasonCode.STOCKOUT_RISK: 0,
        ReasonCode.BELOW_TARGET: 1,
        ReasonCode.TRENDING_UP: 2,
        ReasonCode.VENDOR_MINIMUM: 3,
        ReasonCode.REBALANCE: 4,
    }

    def sort_key(r: Recommendation) -> tuple:
        reason = r.reason_code if isinstance(r.reason_code, ReasonCode) else ReasonCode.NO_ORDER
        return (
            priority_order.get(reason, 99),
            0 if r.confidence == Confidence.HIGH else (1 if r.confidence == Confidence.MEDIUM else 2),
            -r.total_cost,  # Higher cost items first within same priority
        )

    sorted_recs = sorted(recommendations, key=sort_key)

    # Apply budget constraint
    if constraints.max_total_spend:
        running_total = 0.0
        for rec in sorted_recs:
            if running_total + rec.total_cost > constraints.max_total_spend:
                if rec.suggested_order > 0:
                    rec.suggested_order = 0
                    rec.total_cost = 0.0
                    rec.adjustments.append(f"Removed due to budget constraint (${constraints.max_total_spend})")
            else:
                running_total += rec.total_cost

    # Check vendor minimums
    vendor_totals = {}
    for rec in sorted_recs:
        if rec.suggested_order > 0:
            vendor_totals[rec.vendor] = vendor_totals.get(rec.vendor, 0) + rec.total_cost

    for vendor, minimum in constraints.vendor_minimums.items():
        if vendor in vendor_totals and vendor_totals[vendor] < minimum:
            warnings.append({
                "vendor": vendor,
                "message": f"Order total ${vendor_totals[vendor]:.2f} below minimum ${minimum}"
            })

    return sorted_recs
