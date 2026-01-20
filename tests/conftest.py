"""Pytest configuration and fixtures."""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

# Set test environment before importing app
os.environ["DEBUG"] = "true"
os.environ["API_KEYS"] = ""
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Get the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def api_client() -> Generator[TestClient, None, None]:
    """Create a FastAPI test client."""
    from api.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_items() -> dict:
    """Sample inventory items for testing."""
    return {
        "WHISKEY Buffalo Trace": {
            "item_id": "WHISKEY Buffalo Trace",
            "display_name": "Buffalo Trace",
            "category": "Whiskey",
            "vendor": "Breakthru",
            "unit_cost": 22.50,
        },
        "VODKA Tito's": {
            "item_id": "VODKA Tito's",
            "display_name": "Tito's Vodka",
            "category": "Vodka",
            "vendor": "Southern",
            "unit_cost": 18.00,
        },
        "TEQUILA Patron Silver": {
            "item_id": "TEQUILA Patron Silver",
            "display_name": "Patron Silver",
            "category": "Tequila",
            "vendor": "Breakthru",
            "unit_cost": 45.00,
        },
    }


@pytest.fixture
def sample_records() -> list:
    """Sample weekly records for testing."""
    return [
        {"item_id": "WHISKEY Buffalo Trace", "week_date": "2024-03-01", "on_hand": 5, "usage": 3},
        {"item_id": "WHISKEY Buffalo Trace", "week_date": "2024-03-08", "on_hand": 4, "usage": 4},
        {"item_id": "WHISKEY Buffalo Trace", "week_date": "2024-03-15", "on_hand": 3, "usage": 3},
        {"item_id": "WHISKEY Buffalo Trace", "week_date": "2024-03-22", "on_hand": 2, "usage": 4},
        {"item_id": "VODKA Tito's", "week_date": "2024-03-01", "on_hand": 8, "usage": 2},
        {"item_id": "VODKA Tito's", "week_date": "2024-03-08", "on_hand": 7, "usage": 2},
        {"item_id": "VODKA Tito's", "week_date": "2024-03-15", "on_hand": 6, "usage": 2},
        {"item_id": "VODKA Tito's", "week_date": "2024-03-22", "on_hand": 5, "usage": 2},
    ]
