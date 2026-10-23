"""Unit tests for payment lifecycle, validation, and error scenarios."""


def test_create_payment_success(client):
    """Test successful payment creation with valid data."""
    payload = {
        "order_id": "ORD-PUNE-1001",
        "customer_id": "CUST-MH-9921",
        "amount": 1499.50,
        "currency": "INR",
        "payment_method": "UPI",
        "status": "SUCCESS",
    }
    response = client.post("/api/v1/payments", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["order_id"] == "ORD-PUNE-1001"
    assert data["customer_id"] == "CUST-MH-9921"
    assert data["amount"] == 1499.50
    assert data["currency"] == "INR"
    assert data["payment_method"] == "UPI"
    assert data["status"] == "SUCCESS"
    assert data["payment_id"].startswith("pay_")
    assert "created_at" in data
    assert "updated_at" in data


def test_create_payment_validation_negative_amount(client):
    """Test validation rejection when amount is zero or negative."""
    payload = {
        "order_id": "ORD-PUNE-1002",
        "customer_id": "CUST-MH-9921",
        "amount": -50.00,
        "currency": "INR",
        "payment_method": "UPI",
    }
    response = client.post("/api/v1/payments", json=payload)
    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"


def test_create_payment_validation_invalid_currency(client):
    """Test validation rejection when currency is invalid."""
    payload = {
        "order_id": "ORD-PUNE-1003",
        "customer_id": "CUST-MH-9921",
        "amount": 500.00,
        "currency": "12$",
        "payment_method": "CARD",
    }
    response = client.post("/api/v1/payments", json=payload)
    assert response.status_code == 422


def test_create_payment_validation_invalid_method(client):
    """Test validation rejection when payment method is unsupported."""
    payload = {
        "order_id": "ORD-PUNE-1004",
        "customer_id": "CUST-MH-9921",
        "amount": 250.00,
        "currency": "INR",
        "payment_method": "CRYPTO_COIN",
    }
    response = client.post("/api/v1/payments", json=payload)
    assert response.status_code == 422


def test_create_payment_missing_required_fields(client):
    """Test validation rejection when required fields are omitted."""
    payload = {
        "amount": 250.00,
    }
    response = client.post("/api/v1/payments", json=payload)
    assert response.status_code == 422


def test_get_payment_success(client):
    """Test retrieval of an existing payment by payment_id."""
    # First create
    create_payload = {
        "order_id": "ORD-GET-01",
        "customer_id": "CUST-01",
        "amount": 750.00,
        "currency": "INR",
        "payment_method": "NETBANKING",
        "status": "PENDING",
    }
    create_res = client.post("/api/v1/payments", json=create_payload)
    payment_id = create_res.json()["payment_id"]

    # Now get
    get_res = client.get(f"/api/v1/payments/{payment_id}")
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["payment_id"] == payment_id
    assert retrieved["order_id"] == "ORD-GET-01"
    assert retrieved["status"] == "PENDING"


def test_get_payment_not_found(client):
    """Test retrieval with a non-existent payment_id returns 404."""
    response = client.get("/api/v1/payments/pay_nonexistent99999")
    assert response.status_code == 404
    assert response.json()["error"] == "HTTP_ERROR"
    assert "was not found" in response.json()["detail"]


def test_list_payments_filtering_and_pagination(client):
    """Test list endpoint with customer and status filtering."""
    cust_id = "CUST-FILTER-TEST"

    # Create 3 payments: 2 SUCCESS, 1 FAILED
    for i, status_val in enumerate(["SUCCESS", "SUCCESS", "FAILED"]):
        client.post(
            "/api/v1/payments",
            json={
                "order_id": f"ORD-F-{i}",
                "customer_id": cust_id,
                "amount": 100.0 * (i + 1),
                "currency": "INR",
                "payment_method": "UPI",
                "status": status_val,
            },
        )

    # Filter by customer
    res = client.get(f"/api/v1/payments?customer_id={cust_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    # Filter by customer and status=SUCCESS
    res_success = client.get(f"/api/v1/payments?customer_id={cust_id}&status=SUCCESS")
    assert res_success.status_code == 200
    assert res_success.json()["total"] == 2

    # Filter by customer and status=FAILED
    res_failed = client.get(f"/api/v1/payments?customer_id={cust_id}&status=FAILED")
    assert res_failed.status_code == 200
    assert res_failed.json()["total"] == 1

    # Test pagination limit
    res_paged = client.get(f"/api/v1/payments?customer_id={cust_id}&limit=2&offset=0")
    assert res_paged.status_code == 200
    assert len(res_paged.json()["items"]) == 2
    assert res_paged.json()["limit"] == 2
    assert res_paged.json()["offset"] == 0
