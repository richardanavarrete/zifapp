"""Integration tests for health endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_returns_ok(self, api_client: TestClient):
        """Basic health check should return OK."""
        response = api_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_ready_returns_status(self, api_client: TestClient):
        """Readiness check should return dependency status."""
        response = api_client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["ready", "degraded"]
        assert "checks" in data
        assert "version" in data

    def test_info_returns_service_info(self, api_client: TestClient):
        """Info endpoint should return service metadata."""
        response = api_client.get("/health/info")

        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
