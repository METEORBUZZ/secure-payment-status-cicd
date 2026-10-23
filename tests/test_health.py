"""Unit tests for service health and probe endpoints."""

from unittest.mock import patch


def test_health_check_healthy(client):
    """Verify that /health returns 200 OK with expected payload in normal conditions."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "UP"
    assert data["database"] == "CONNECTED"
    assert data["environment"] == "test"
    assert "version" in data
    assert "timestamp" in data


def test_health_check_degraded(client):
    """Verify that /health returns 503 Service Unavailable when DB is unreachable."""
    with patch("app.routes.health.check_db_health", return_value=False):
        response = client.get("/health")
        assert response.status_code == 503

        data = response.json()
        assert data["status"] == "DEGRADED"
        assert data["database"] == "UNAVAILABLE"
