"""Unit tests for edge cases and global exception handlers."""

from unittest.mock import patch


def test_empty_payment_id_whitespace(client):
    """Verify that an empty/whitespace payment_id triggers validation error or 400."""
    response = client.get("/api/v1/payments/%20%20%20")
    assert response.status_code in (400, 404)
    assert response.json()["error"] == "HTTP_ERROR"


def test_unhandled_exception_returns_500(client):
    """Verify that unhandled exceptions are caught and return a clean 500 JSON response."""
    with patch("app.routes.payments.list_payments", side_effect=RuntimeError("Database query crash")):
        response = client.get("/api/v1/payments")
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "INTERNAL_SERVER_ERROR"
        assert "unexpected server error" in data["detail"]


def test_route_not_found_returns_404(client):
    """Verify non-existent route returns 404."""
    response = client.get("/non-existent-endpoint")
    assert response.status_code == 404
