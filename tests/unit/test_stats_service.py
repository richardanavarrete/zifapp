"""Tests for stats service."""

from datetime import date

import pytest

from smallcogs.models.common import TrendDirection
from smallcogs.models.inventory import Item, Record
from smallcogs.services.stats_service import StatsService


@pytest.fixture
def stats_service():
    return StatsService()


@pytest.fixture
def sample_item():
    return Item(
        item_id="test_item",
        name="Test Item",
        category="Test Category",
    )


@pytest.fixture
def sample_records():
    """Sample records with increasing usage (trending up)."""
    return [
        Record(item_id="test_item", record_date=date(2024, 1, 1), on_hand=100, usage=10),
        Record(item_id="test_item", record_date=date(2024, 1, 8), on_hand=90, usage=12),
        Record(item_id="test_item", record_date=date(2024, 1, 15), on_hand=78, usage=14),
        Record(item_id="test_item", record_date=date(2024, 1, 22), on_hand=64, usage=16),
        Record(item_id="test_item", record_date=date(2024, 1, 29), on_hand=48, usage=18),
        Record(item_id="test_item", record_date=date(2024, 2, 5), on_hand=30, usage=20),
        Record(item_id="test_item", record_date=date(2024, 2, 12), on_hand=10, usage=22),
        Record(item_id="test_item", record_date=date(2024, 2, 19), on_hand=5, usage=24),
    ]


def test_compute_item_stats_basic(stats_service, sample_item, sample_records):
    """Test basic stats computation."""
    stats = stats_service.compute_item_stats(sample_item, sample_records)

    assert stats.item_id == "test_item"
    assert stats.item_name == "Test Item"
    assert stats.category == "Test Category"
    assert stats.current_on_hand == 5
    assert stats.record_count == 8


def test_compute_item_stats_usage(stats_service, sample_item, sample_records):
    """Test usage statistics."""
    stats = stats_service.compute_item_stats(sample_item, sample_records)

    assert stats.total_usage == 136  # 10+12+14+16+18+20+22+24
    assert stats.avg_usage == 17.0  # 136/8
    assert stats.min_usage == 10
    assert stats.max_usage == 24


def test_compute_item_stats_trend_up(stats_service, sample_item, sample_records):
    """Test trend detection for increasing usage."""
    stats = stats_service.compute_item_stats(sample_item, sample_records, recent_periods=4)

    # Recent avg (18,20,22,24) = 21
    # Earlier avg (10,12,14,16) = 13
    # Change = (21-13)/13 = 61.5% -> UP
    assert stats.trend_direction == TrendDirection.UP
    assert stats.trend_percent_change > 50


def test_compute_item_stats_empty_records(stats_service, sample_item):
    """Test with no records."""
    stats = stats_service.compute_item_stats(sample_item, [])

    assert stats.item_id == "test_item"
    assert stats.record_count == 0
    assert stats.current_on_hand == 0


def test_compute_item_stats_negative_usage(stats_service, sample_item):
    """Test detection of negative usage."""
    records = [
        Record(item_id="test_item", record_date=date(2024, 1, 1), on_hand=100, usage=-5),
        Record(item_id="test_item", record_date=date(2024, 1, 8), on_hand=105, usage=10),
    ]

    stats = stats_service.compute_item_stats(sample_item, records)

    assert stats.has_negative_usage is True
