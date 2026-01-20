"""
Order Recommendation Service

Agentic ordering - generates smart recommendations based on usage patterns.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from smallcogs.models.inventory import Dataset, ItemStats
from smallcogs.models.orders import (
    Confidence,
    OrderConstraints,
    OrderExport,
    OrderTargets,
    ReasonCode,
    Recommendation,
    RecommendationRun,
    RecommendRequest,
)
from smallcogs.services.stats_service import StatsService

logger = logging.getLogger(__name__)


class OrderService:
    """Service for generating order recommendations."""

    def __init__(self):
        self.stats_service = StatsService()
        self._runs: Dict[str, RecommendationRun] = {}

    def generate_recommendations(
        self,
        dataset: Dataset,
        request: Optional[RecommendRequest] = None,
    ) -> RecommendationRun:
        """
        Generate order recommendations for a dataset.

        Analyzes usage patterns and generates suggestions based on targets.
        """
        # Use defaults if not provided
        targets = request.targets if request and request.targets else OrderTargets()
        constraints = request.constraints if request and request.constraints else OrderConstraints()

        # Compute stats for all items
        all_stats = self.stats_service.compute_all_stats(dataset)

        # Generate recommendations
        recommendations = []
        warnings = []
        data_issues = []

        for item_id, stats in all_stats.items():
            item = dataset.items.get(item_id)
            if not item:
                continue

            # Apply filters
            if request:
                if request.categories and item.category not in request.categories:
                    continue
                if request.vendors and item.vendor not in request.vendors:
                    continue
                if request.exclude_items and item_id in request.exclude_items:
                    continue

            # Check if excluded in targets
            if item_id in targets.exclude_items:
                continue

            # Get target weeks for this item
            target_weeks = targets.get_target(item_id, item.category)
            if target_weeks <= 0:
                continue

            # Generate recommendation
            rec = self._evaluate_item(item, stats, target_weeks, constraints)

            if rec:
                recommendations.append(rec)

                # Track data issues
                if stats.has_negative_usage or stats.has_gaps:
                    data_issues.append({
                        "item_id": item_id,
                        "item_name": item.name,
                        "issues": self._describe_issues(stats),
                    })

        # Apply constraints
        recommendations = self._apply_constraints(recommendations, constraints)

        # Sort by priority (stockout risk first)
        recommendations.sort(
            key=lambda r: (
                0 if r.reason == ReasonCode.STOCKOUT_RISK else 1,
                r.weeks_on_hand or 999
            )
        )

        # Build summary
        run = self._build_run(dataset, recommendations, targets, constraints, warnings, data_issues)
        self._runs[run.run_id] = run

        return run

    def _evaluate_item(
        self,
        item,
        stats: ItemStats,
        target_weeks: float,
        constraints: OrderConstraints,
    ) -> Optional[Recommendation]:
        """Evaluate a single item and generate recommendation if needed."""

        # Skip if no usage data
        if stats.avg_usage <= 0:
            return None

        weeks_on_hand = stats.weeks_on_hand or 0

        # Determine reason and confidence
        reason, reason_text, confidence = self._determine_reason(
            stats, target_weeks, constraints
        )

        if reason == ReasonCode.OVERSTOCK:
            return None  # Don't recommend ordering overstocked items

        # Calculate suggested quantity
        if weeks_on_hand >= target_weeks:
            return None  # Already at or above target

        weeks_needed = target_weeks - weeks_on_hand
        suggested_qty = max(1, round(weeks_needed * stats.avg_usage))

        # Adjust for trends
        if stats.trend_direction.value == "up" and stats.trend_pct_change > 10:
            suggested_qty = round(suggested_qty * 1.1)
            reason_text += " (adjusted +10% for upward trend)"
        elif stats.trend_direction.value == "down" and stats.trend_pct_change < -10:
            suggested_qty = max(1, round(suggested_qty * 0.9))
            reason_text += " (adjusted -10% for downward trend)"

        # Calculate cost
        unit_cost = item.unit_cost
        total_cost = unit_cost * suggested_qty if unit_cost else None

        return Recommendation(
            item_id=item.item_id,
            item_name=item.name,
            category=item.category,
            vendor=item.vendor,
            on_hand=stats.current_on_hand,
            avg_usage=stats.avg_usage,
            weeks_on_hand=weeks_on_hand,
            suggested_qty=suggested_qty,
            unit_cost=unit_cost,
            total_cost=total_cost,
            reason=reason,
            reason_text=reason_text,
            confidence=confidence,
            trend_direction=stats.trend_direction.value,
            trend_pct=stats.trend_pct_change,
            warnings=self._describe_issues(stats) if stats.has_negative_usage or stats.has_gaps else [],
        )

    def _determine_reason(
        self,
        stats: ItemStats,
        target_weeks: float,
        constraints: OrderConstraints,
    ) -> tuple:
        """Determine the reason code and confidence for a recommendation."""

        weeks_on_hand = stats.weeks_on_hand or 0

        # Stockout risk - critical
        if weeks_on_hand < constraints.low_stock_weeks:
            if weeks_on_hand < 0.5:
                return (
                    ReasonCode.STOCKOUT_RISK,
                    f"Critical: only {weeks_on_hand:.1f} weeks on hand",
                    Confidence.HIGH
                )
            return (
                ReasonCode.LOW_STOCK,
                f"Low stock: {weeks_on_hand:.1f} weeks on hand (threshold: {constraints.low_stock_weeks})",
                Confidence.HIGH
            )

        # Overstock
        if weeks_on_hand > constraints.overstock_weeks:
            return (
                ReasonCode.OVERSTOCK,
                f"Overstock: {weeks_on_hand:.1f} weeks on hand",
                Confidence.MEDIUM
            )

        # Trending up - may need more
        if stats.trend_direction.value == "up" and stats.trend_pct_change > 15:
            return (
                ReasonCode.TRENDING_UP,
                f"Usage trending up {stats.trend_pct_change:.0f}%",
                Confidence.MEDIUM
            )

        # Below target
        if weeks_on_hand < target_weeks:
            confidence = Confidence.HIGH if stats.data_quality_score > 0.8 else Confidence.MEDIUM
            return (
                ReasonCode.BELOW_TARGET,
                f"Below target: {weeks_on_hand:.1f} weeks (target: {target_weeks})",
                confidence
            )

        # Data quality issues
        if stats.has_negative_usage or stats.has_gaps:
            return (
                ReasonCode.DATA_QUALITY,
                "Data quality issues - review manually",
                Confidence.LOW
            )

        return (ReasonCode.BELOW_TARGET, "Reorder suggested", Confidence.MEDIUM)

    def _describe_issues(self, stats: ItemStats) -> List[str]:
        """Describe data quality issues for an item."""
        issues = []
        if stats.has_negative_usage:
            issues.append("Negative usage detected (data entry error?)")
        if stats.has_gaps:
            issues.append("Missing data periods")
        if stats.coefficient_of_variation > 1.0:
            issues.append("High usage variability")
        return issues

    def _apply_constraints(
        self,
        recommendations: List[Recommendation],
        constraints: OrderConstraints,
    ) -> List[Recommendation]:
        """Apply budget and vendor constraints."""

        result = recommendations.copy()

        # Max items
        if constraints.max_items and len(result) > constraints.max_items:
            result = result[:constraints.max_items]

        # Max spend
        if constraints.max_spend:
            total = 0.0
            filtered = []
            for rec in result:
                cost = rec.total_cost or 0
                if total + cost <= constraints.max_spend:
                    filtered.append(rec)
                    total += cost
            result = filtered

        return result

    def _build_run(
        self,
        dataset: Dataset,
        recommendations: List[Recommendation],
        targets: OrderTargets,
        constraints: OrderConstraints,
        warnings: List[str],
        data_issues: List[Dict],
    ) -> RecommendationRun:
        """Build the recommendation run with summary stats."""

        # Calculate totals
        total_spend = sum(r.total_cost or 0 for r in recommendations)

        # Group by vendor
        by_vendor: Dict[str, Dict[str, Any]] = {}
        for rec in recommendations:
            vendor = rec.vendor or "Unknown"
            if vendor not in by_vendor:
                by_vendor[vendor] = {"items": 0, "spend": 0.0}
            by_vendor[vendor]["items"] += 1
            by_vendor[vendor]["spend"] += rec.total_cost or 0

        # Group by category
        by_category: Dict[str, Dict[str, Any]] = {}
        for rec in recommendations:
            cat = rec.category or "Uncategorized"
            if cat not in by_category:
                by_category[cat] = {"items": 0, "spend": 0.0}
            by_category[cat]["items"] += 1
            by_category[cat]["spend"] += rec.total_cost or 0

        # Group by reason
        by_reason: Dict[str, int] = {}
        for rec in recommendations:
            reason = rec.reason.value
            by_reason[reason] = by_reason.get(reason, 0) + 1

        # Count alerts
        low_stock = sum(1 for r in recommendations if r.reason in [ReasonCode.STOCKOUT_RISK, ReasonCode.LOW_STOCK])
        overstock = sum(1 for r in recommendations if r.reason == ReasonCode.OVERSTOCK)

        return RecommendationRun(
            run_id=f"run_{uuid.uuid4().hex[:12]}",
            dataset_id=dataset.dataset_id,
            targets=targets,
            constraints=constraints,
            recommendations=recommendations,
            total_items=len(recommendations),
            total_spend=total_spend,
            low_stock_count=low_stock,
            overstock_count=overstock,
            by_vendor=by_vendor,
            by_category=by_category,
            by_reason=by_reason,
            warnings=warnings,
            data_issues=data_issues,
        )

    # =========================================================================
    # Run Management
    # =========================================================================

    def get_run(self, run_id: str) -> Optional[RecommendationRun]:
        """Get a recommendation run by ID."""
        return self._runs.get(run_id)

    def list_runs(self, dataset_id: Optional[str] = None) -> List[RecommendationRun]:
        """List all runs, optionally filtered by dataset."""
        runs = list(self._runs.values())
        if dataset_id:
            runs = [r for r in runs if r.dataset_id == dataset_id]
        return sorted(runs, key=lambda r: r.created_at, reverse=True)

    # =========================================================================
    # Export
    # =========================================================================

    def export_run(
        self,
        run_id: str,
        format: str = "csv",
        group_by_vendor: bool = True,
    ) -> Optional[OrderExport]:
        """Export recommendations for copy/paste or download."""

        run = self._runs.get(run_id)
        if not run:
            return None

        # Build items list
        items = []
        for rec in run.recommendations:
            items.append({
                "item_name": rec.item_name,
                "category": rec.category,
                "vendor": rec.vendor,
                "on_hand": rec.on_hand,
                "suggested_qty": rec.suggested_qty,
                "unit_cost": rec.unit_cost,
                "total_cost": rec.total_cost,
                "reason": rec.reason.value,
            })

        # Group by vendor
        by_vendor: Dict[str, List[Dict]] = {}
        if group_by_vendor:
            for item in items:
                vendor = item.get("vendor") or "Unknown"
                if vendor not in by_vendor:
                    by_vendor[vendor] = []
                by_vendor[vendor].append(item)

        # Generate CSV
        csv_lines = ["Item,Category,Vendor,On Hand,Order Qty,Unit Cost,Total Cost,Reason"]
        for item in items:
            csv_lines.append(
                f"{item['item_name']},{item['category']},{item['vendor']},"
                f"{item['on_hand']},{item['suggested_qty']},{item['unit_cost'] or ''},"
                f"{item['total_cost'] or ''},{item['reason']}"
            )
        csv_text = "\n".join(csv_lines)

        # Generate summary
        summary_lines = [
            f"Order Recommendations - {run.created_at.strftime('%Y-%m-%d')}",
            f"Total Items: {run.total_items}",
            f"Total Spend: ${run.total_spend:.2f}",
            "",
        ]

        if group_by_vendor:
            for vendor, vendor_items in by_vendor.items():
                vendor_total = sum(i.get("total_cost") or 0 for i in vendor_items)
                summary_lines.append(f"\n{vendor} (${vendor_total:.2f}):")
                for item in vendor_items:
                    summary_lines.append(f"  {item['item_name']}: {item['suggested_qty']}")

        summary_text = "\n".join(summary_lines)

        return OrderExport(
            run_id=run_id,
            items=items,
            total_items=run.total_items,
            total_spend=run.total_spend,
            csv_text=csv_text,
            summary_text=summary_text,
            by_vendor=by_vendor,
        )
