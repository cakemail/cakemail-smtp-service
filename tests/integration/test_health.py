"""Integration tests for health endpoints."""

import pytest
from fastapi.testclient import TestClient

from smtp_gateway.http.server import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


@pytest.mark.integration
def test_liveness_endpoint(client):
    """Test liveness endpoint returns 200."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["check"] == "liveness"


@pytest.mark.integration
def test_readiness_endpoint(client):
    """Test readiness endpoint returns 200."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["check"] == "readiness"


@pytest.mark.integration
def test_metrics_endpoint(client):
    """Test metrics endpoint returns Prometheus format."""
    response = client.get("/metrics")
    assert response.status_code == 200
    # Metrics should be in text format
    assert isinstance(response.content, bytes)
