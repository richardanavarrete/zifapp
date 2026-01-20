"""Pytest configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.config import Settings


@pytest.fixture
def client():
    """Test client for the API."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Headers with test API key."""
    return {"X-API-Key": "test-key"}
