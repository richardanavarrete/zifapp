"""Tests for the feature engine."""

import pytest
from datetime import date

from houndcogs.models.inventory import Item, WeeklyRecord, InventoryDataset
from houndcogs.services.feature_engine import (
    compute_features,
    compute_features_for_item,
    get_feature_summary,
)


def create_test_dataset(items: dict, records: list) -> InventoryDataset:
    """Create a test dataset from items and records."""
    item_objects = {
        item_id: Item(**data) for item_id, data in items.items()
    }
    record_objects = [
        WeeklyRecord(
            item_id=r["item_id"],
            week_date=date.fromisoformat(r["week_date"]),
            on_hand=r["on_hand"],
            usage=r["usage"],
        )
        for r in records
    ]

    return InventoryDataset(
        dataset_id="test_ds",
        name="Test Dataset",
        items=item_objects,
        records=record_objects,
        items_count=len(item_objects),
        weeks_count=4,
    )


class TestComputeFeatures:
    """Tests for compute_features function."""

    def test_computes_features_for_all_items(self, sample_items, sample_records):
        """Test that features are computed for all items."""
        dataset = create_test_dataset(sample_items, sample_records)
        features = compute_features(dataset)

        # Should have features for items with records
        item_ids = {f.item_id for f in features}
        assert "WHISKEY Buffalo Trace" in item_ids
        assert "VODKA Tito's" in item_ids

    def test_computes_rolling_averages(self, sample_items, sample_records):
        """Test rolling average calculations."""
        dataset = create_test_dataset(sample_items, sample_records)
        features = compute_features(dataset)

        whiskey_features = next(f for f in features if f.item_id == "WHISKEY Buffalo Trace")

        # 4-week average of [3, 4, 3, 4] = 3.5
        assert whiskey_features.avg_weekly_usage_4wk == pytest.approx(3.5, rel=0.1)
        assert whiskey_features.avg_weekly_usage_ytd == pytest.approx(3.5, rel=0.1)

    def test_computes_weeks_on_hand(self, sample_items, sample_records):
        """Test weeks on hand calculation."""
        dataset = create_test_dataset(sample_items, sample_records)
        features = compute_features(dataset)

        whiskey_features = next(f for f in features if f.item_id == "WHISKEY Buffalo Trace")

        # Current on_hand = 2, avg_usage = 3.5
        # weeks_on_hand = 2 / 3.5 = 0.57
        assert whiskey_features.current_on_hand == 2.0
        assert whiskey_features.weeks_on_hand == pytest.approx(0.57, rel=0.1)

    def test_detects_negative_usage(self, sample_items):
        """Test that negative usage is flagged."""
        records = [
            {"item_id": "WHISKEY Buffalo Trace", "week_date": "2024-03-01", "on_hand": 5, "usage": -2},
            {"item_id": "WHISKEY Buffalo Trace", "week_date": "2024-03-08", "on_hand": 4, "usage": 3},
        ]
        dataset = create_test_dataset(sample_items, records)
        features = compute_features(dataset)

        whiskey_features = next(f for f in features if f.item_id == "WHISKEY Buffalo Trace")
        assert whiskey_features.has_negative_usage is True

    def test_handles_empty_dataset(self):
        """Test handling of empty dataset."""
        dataset = InventoryDataset(
            dataset_id="empty",
            name="Empty",
            items={},
            records=[],
        )
        features = compute_features(dataset)
        assert features == []


class TestFeatureSummary:
    """Tests for get_feature_summary function."""

    def test_counts_items_by_status(self, sample_items, sample_records):
        """Test summary statistics."""
        dataset = create_test_dataset(sample_items, sample_records)
        features = compute_features(dataset)
        summary = get_feature_summary(features)

        assert summary["total_items"] == 2
        assert summary["items_with_negative_usage"] == 0
        # Whiskey has 0.57 weeks on hand, so should be flagged as low stock
        assert summary["items_low_stock"] >= 1
