"""
Stats Service - Computes usage statistics and trends

Pure functions for computing analytics from inventory data.
"""

import statistics
from typing import Dict, List, Optional

from smallcogs.models.common import TrendDirection
from smallcogs.models.inventory import Dataset, Item, ItemDetail, ItemStats, Record, UsageTrend


class StatsService:
    """Computes usage statistics and trends."""

    def compute_item_stats(
        self,
        item: Item,
        records: List[Record],
        recent_periods: int = 4
    ) -> ItemStats:
        """Compute statistics for a single item."""

        # Sort records by date
        sorted_records = sorted(records, key=lambda r: r.record_date)

        if not sorted_records:
            return ItemStats(
                item_id=item.item_id,
                item_name=item.name,
                category=item.category,
            )

        # Basic stats
        usages = [r.usage for r in sorted_records if r.usage is not None]

        current_on_hand = sorted_records[-1].on_hand
        last_count_date = sorted_records[-1].record_date

        # Usage statistics
        total_usage = sum(usages) if usages else 0.0
        avg_usage = statistics.mean(usages) if usages else 0.0
        min_usage = min(usages) if usages else 0.0
        max_usage = max(usages) if usages else 0.0

        # Recent average (last N periods)
        recent_usages = usages[-recent_periods:] if len(usages) >= recent_periods else usages
        avg_usage_recent = statistics.mean(recent_usages) if recent_usages else 0.0

        # Weeks/days on hand
        weeks_on_hand = None
        days_on_hand = None
        if avg_usage > 0:
            weeks_on_hand = round(current_on_hand / avg_usage, 1)
            days_on_hand = round(current_on_hand / (avg_usage / 7), 1)

        # Trend analysis
        trend_direction, trend_change = self._compute_trend(usages, recent_periods)

        # Volatility
        std_dev = statistics.stdev(usages) if len(usages) > 1 else 0.0
        cv = (std_dev / avg_usage) if avg_usage > 0 else 0.0

        # Data quality
        has_negative = any(u < 0 for u in usages)
        has_gaps = self._check_gaps(sorted_records)

        return ItemStats(
            item_id=item.item_id,
            item_name=item.name,
            category=item.category,
            current_on_hand=current_on_hand,
            last_count_date=last_count_date,
            total_usage=total_usage,
            avg_usage=round(avg_usage, 2),
            avg_usage_recent=round(avg_usage_recent, 2),
            min_usage=min_usage,
            max_usage=max_usage,
            weeks_on_hand=weeks_on_hand,
            days_on_hand=days_on_hand,
            trend_direction=trend_direction,
            trend_percent_change=round(trend_change, 1),
            std_deviation=round(std_dev, 2),
            coefficient_of_variation=round(cv, 2),
            record_count=len(sorted_records),
            has_negative_usage=has_negative,
            has_gaps=has_gaps,
        )

    def compute_all_stats(
        self,
        dataset: Dataset,
        recent_periods: int = 4
    ) -> Dict[str, ItemStats]:
        """Compute stats for all items in a dataset."""
        stats = {}
        for item_id, item in dataset.items.items():
            records = dataset.get_item_records(item_id)
            stats[item_id] = self.compute_item_stats(item, records, recent_periods)
        return stats

    def get_item_detail(
        self,
        dataset: Dataset,
        item_id: str,
        recent_periods: int = 4
    ) -> Optional[ItemDetail]:
        """Get complete item detail with history and stats."""
        item = dataset.get_item(item_id)
        if not item:
            return None

        records = dataset.get_item_records(item_id)
        stats = self.compute_item_stats(item, records, recent_periods)

        # Build history
        sorted_records = sorted(records, key=lambda r: r.record_date)
        history = [
            UsageTrend(
                date=r.record_date,
                usage=r.usage or 0.0,
                on_hand=r.on_hand,
                period_name=r.period_name,
            )
            for r in sorted_records
        ]

        # Rolling averages for chart
        usages = [r.usage or 0.0 for r in sorted_records]
        rolling_4wk = self._rolling_average(usages, 4)

        return ItemDetail(
            item=item,
            stats=stats,
            history=history,
            rolling_avg_4wk=rolling_4wk,
        )

    def get_category_summary(
        self,
        dataset: Dataset,
        all_stats: Optional[Dict[str, ItemStats]] = None
    ) -> Dict[str, Dict]:
        """Get summary statistics grouped by category."""
        if all_stats is None:
            all_stats = self.compute_all_stats(dataset)

        summary = {}
        for item_id, stats in all_stats.items():
            category = stats.category or "Uncategorized"
            if category not in summary:
                summary[category] = {
                    "category": category,
                    "items_count": 0,
                    "total_on_hand": 0.0,
                    "total_usage": 0.0,
                    "avg_weeks_on_hand": [],
                    "items": [],
                }

            summary[category]["items_count"] += 1
            summary[category]["total_on_hand"] += stats.current_on_hand
            summary[category]["total_usage"] += stats.total_usage
            if stats.weeks_on_hand:
                summary[category]["avg_weeks_on_hand"].append(stats.weeks_on_hand)
            summary[category]["items"].append(stats)

        # Compute averages
        for cat_data in summary.values():
            woh_list = cat_data["avg_weeks_on_hand"]
            cat_data["avg_weeks_on_hand"] = (
                round(statistics.mean(woh_list), 1) if woh_list else None
            )

        return summary

    def _compute_trend(
        self,
        usages: List[float],
        recent_periods: int
    ) -> tuple[TrendDirection, float]:
        """Compute trend direction and percent change."""
        if len(usages) < recent_periods * 2:
            return TrendDirection.STABLE, 0.0

        recent = usages[-recent_periods:]
        earlier = usages[-(recent_periods * 2):-recent_periods]

        recent_avg = statistics.mean(recent)
        earlier_avg = statistics.mean(earlier)

        if earlier_avg == 0:
            return TrendDirection.STABLE, 0.0

        pct_change = ((recent_avg - earlier_avg) / earlier_avg) * 100

        if pct_change > 10:
            return TrendDirection.UP, pct_change
        elif pct_change < -10:
            return TrendDirection.DOWN, pct_change
        else:
            return TrendDirection.STABLE, pct_change

    def _check_gaps(self, sorted_records: List[Record]) -> bool:
        """Check if there are gaps in the data."""
        if len(sorted_records) < 2:
            return False

        dates = [r.record_date for r in sorted_records]
        for i in range(1, len(dates)):
            gap = (dates[i] - dates[i - 1]).days
            if gap > 14:  # More than 2 weeks gap
                return True
        return False

    def _rolling_average(self, values: List[float], window: int) -> List[float]:
        """Compute rolling average."""
        if len(values) < window:
            return values

        result = []
        for i in range(len(values)):
            start = max(0, i - window + 1)
            window_values = values[start:i + 1]
            result.append(round(statistics.mean(window_values), 2))
        return result
