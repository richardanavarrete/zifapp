"""Tests for the policy engine."""


import pytest

from houndcogs.models.common import Category, ReasonCode, Vendor
from houndcogs.models.inventory import Item, ItemFeatures
from houndcogs.models.orders import OrderConstraints, OrderTargets
from houndcogs.services.policy_engine import apply_policies


def create_test_item(
    item_id: str = "TEST Item",
    category: Category = Category.WHISKEY,
    vendor: Vendor = Vendor.BREAKTHRU,
) -> Item:
    """Create a test item."""
    return Item(
        item_id=item_id,
        display_name=item_id,
        category=category,
        vendor=vendor,
        unit_cost=25.0,
    )


def create_test_features(
    item_id: str = "TEST Item",
    current_on_hand: float = 5.0,
    weeks_on_hand: float = 2.0,
    avg_weekly_usage: float = 2.5,
    trend: str = "stable",
) -> ItemFeatures:
    """Create test features."""
    return ItemFeatures(
        item_id=item_id,
        avg_weekly_usage_ytd=avg_weekly_usage,
        avg_weekly_usage_10wk=avg_weekly_usage,
        avg_weekly_usage_4wk=avg_weekly_usage,
        avg_weekly_usage_2wk=avg_weekly_usage,
        current_on_hand=current_on_hand,
        weeks_on_hand=weeks_on_hand,
        coefficient_of_variation=0.2,
        trend_direction=trend,
        trend_strength=0.1,
        has_negative_usage=False,
        has_data_gaps=False,
        weeks_of_data=12,
    )


class TestStockoutRisk:
    """Tests for stockout risk detection."""

    def test_flags_low_stock_items(self):
        """Items below 1 week should be flagged as stockout risk."""
        from houndcogs.models.inventory import InventoryDataset

        item = create_test_item()
        features = create_test_features(
            item_id=item.item_id,
            current_on_hand=2.0,
            weeks_on_hand=0.5,  # Half a week
            avg_weekly_usage=4.0,
        )

        dataset = InventoryDataset(
            dataset_id="test",
            name="Test",
            items={item.item_id: item},
            records=[],
        )

        results = apply_policies(
            dataset=dataset,
            features={item.item_id: features},
            targets=OrderTargets(),
            constraints=OrderConstraints(),
        )

        assert len(results) == 1
        assert results[0].reason_code == ReasonCode.STOCKOUT_RISK
        assert results[0].suggested_quantity > 0


class TestBelowTarget:
    """Tests for below-target detection."""

    def test_orders_when_below_target(self):
        """Items below target weeks should get order recommendations."""
        from houndcogs.models.inventory import InventoryDataset

        item = create_test_item()
        features = create_test_features(
            item_id=item.item_id,
            current_on_hand=6.0,
            weeks_on_hand=2.0,  # Below 4-week target for liquor
            avg_weekly_usage=3.0,
        )

        targets = OrderTargets(weeks_by_category={"Whiskey": 4.0})

        dataset = InventoryDataset(
            dataset_id="test",
            name="Test",
            items={item.item_id: item},
            records=[],
        )

        results = apply_policies(
            dataset=dataset,
            features={item.item_id: features},
            targets=targets,
            constraints=OrderConstraints(),
        )

        assert len(results) == 1
        assert results[0].reason_code == ReasonCode.BELOW_TARGET
        # Should order enough to reach 4 weeks: (4 * 3) - 6 = 6 units
        assert results[0].suggested_quantity == pytest.approx(6, abs=1)


class TestTrendAdjustments:
    """Tests for trend-based adjustments."""

    def test_increases_order_for_upward_trend(self):
        """Orders should increase 10% for trending up items."""
        from houndcogs.models.inventory import InventoryDataset

        item = create_test_item()
        features = create_test_features(
            item_id=item.item_id,
            current_on_hand=2.0,
            weeks_on_hand=0.5,
            avg_weekly_usage=4.0,
            trend="up",
        )
        features.trend_strength = 0.3

        dataset = InventoryDataset(
            dataset_id="test",
            name="Test",
            items={item.item_id: item},
            records=[],
        )

        results = apply_policies(
            dataset=dataset,
            features={item.item_id: features},
            targets=OrderTargets(),
            constraints=OrderConstraints(),
        )

        assert len(results) == 1
        assert "trend" in str(results[0].adjustments).lower()


class TestNeverOrderList:
    """Tests for never-order list handling."""

    def test_skips_never_order_items(self):
        """Items on never-order list should not get recommendations."""
        from houndcogs.models.inventory import InventoryDataset

        item = create_test_item(item_id="DISCONTINUED Item")
        features = create_test_features(
            item_id=item.item_id,
            weeks_on_hand=0.1,  # Very low, would normally order
        )

        targets = OrderTargets(never_order=["DISCONTINUED Item"])

        dataset = InventoryDataset(
            dataset_id="test",
            name="Test",
            items={item.item_id: item},
            records=[],
        )

        results = apply_policies(
            dataset=dataset,
            features={item.item_id: features},
            targets=targets,
            constraints=OrderConstraints(),
        )

        assert len(results) == 1
        assert results[0].reason_code == ReasonCode.NO_ORDER
        assert results[0].suggested_quantity == 0
