"""Unit tests for Prometheus metrics scraping."""


def test_metrics_endpoint(client):
    """Verify that /metrics exports valid Prometheus format metrics."""
    # Generate some HTTP traffic first
    client.get("/health")

    # Scrape metrics
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]

    body = response.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert "payment_transactions_total" in body
