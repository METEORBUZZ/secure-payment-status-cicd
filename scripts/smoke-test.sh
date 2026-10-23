#!/usr/bin/env bash
# ==============================================================================
# Smoke Test Script for PuneFinTech Payment Status Service
# Validates cluster deployment health, endpoints, and transaction lifecycle.
# Returns exit code 0 on success, non-zero on any failure.
# ==============================================================================
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
ENV_NAME="${2:-dev}"
MAX_RETRIES="${3:-15}"
RETRY_DELAY="${4:-2}"

echo "=================================================================="
echo " Running Smoke Test Suite"
echo " Target Endpoint: ${BASE_URL}"
echo " Environment:     ${ENV_NAME}"
echo " Max Retries:     ${MAX_RETRIES}"
echo "=================================================================="

# Helper function: Retry HTTP probe until 200 or timeout
wait_for_service() {
    local url="${BASE_URL}/health"
    local count=1

    echo "Probing service health at: ${url}..."
    while [ "${count}" -le "${MAX_RETRIES}" ]; do
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${url}" || true)
        if [ "${HTTP_CODE}" = "200" ]; then
            echo "[PASS] Service reachable and responded with HTTP 200 on attempt ${count}."
            return 0
        fi
        echo "Attempt ${count}/${MAX_RETRIES}: Received HTTP ${HTTP_CODE}. Waiting ${RETRY_DELAY}s..."
        sleep "${RETRY_DELAY}"
        count=$((count + 1))
    done

    echo "[FAIL] Service failed to respond with HTTP 200 within timeout."
    return 1
}

# 1. Health Probe Verification
wait_for_service

echo "Verifying /health payload contents..."
HEALTH_BODY=$(curl -s "${BASE_URL}/health")
echo "Health Response: ${HEALTH_BODY}"

if ! echo "${HEALTH_BODY}" | grep -q '"status":"UP"'; then
    echo "[FAIL] Health payload missing 'status: UP'"
    exit 1
fi

if ! echo "${HEALTH_BODY}" | grep -q '"database":"CONNECTED"'; then
    echo "[FAIL] Health payload indicates database not connected"
    exit 1
fi
echo "[PASS] Health endpoint verified."

# 2. Payment Transaction Lifecycle Test (POST /api/v1/payments)
ORDER_REF="ORD-SMOKE-$(date +%s)"
CREATE_PAYLOAD=$(cat <<EOF
{
  "order_id": "${ORDER_REF}",
  "customer_id": "CUST-SMOKE-TEST",
  "amount": 2500.00,
  "currency": "INR",
  "payment_method": "UPI",
  "status": "SUCCESS"
}
EOF
)

echo "Initiating payment creation via POST /api/v1/payments..."
CREATE_RES=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/v1/payments" \
    -H "Content-Type: application/json" \
    -d "${CREATE_PAYLOAD}")

HTTP_STATUS=$(echo "${CREATE_RES}" | tail -n 1)
RESPONSE_BODY=$(echo "${CREATE_RES}" | sed '$d')

echo "Payment Creation Response (${HTTP_STATUS}): ${RESPONSE_BODY}"

if [ "${HTTP_STATUS}" != "201" ]; then
    echo "[FAIL] Expected HTTP 201 Created from POST /api/v1/payments, received: ${HTTP_STATUS}"
    exit 1
fi

PAYMENT_ID=$(echo "${RESPONSE_BODY}" | grep -o '"payment_id":"[^"]*' | cut -d'"' -f4)
if [ -z "${PAYMENT_ID}" ]; then
    echo "[FAIL] Response did not contain a valid payment_id"
    exit 1
fi
echo "[PASS] Payment created successfully with ID: ${PAYMENT_ID}"

# 3. Payment Lookup Verification (GET /api/v1/payments/{payment_id})
echo "Retrieving payment status via GET /api/v1/payments/${PAYMENT_ID}..."
GET_RES=$(curl -s -w "\n%{http_code}" "${BASE_URL}/api/v1/payments/${PAYMENT_ID}")
GET_HTTP_STATUS=$(echo "${GET_RES}" | tail -n 1)
GET_BODY=$(echo "${GET_RES}" | sed '$d')

echo "Lookup Response (${GET_HTTP_STATUS}): ${GET_BODY}"

if [ "${GET_HTTP_STATUS}" != "200" ]; then
    echo "[FAIL] Expected HTTP 200 OK from GET /api/v1/payments/${PAYMENT_ID}, received: ${GET_HTTP_STATUS}"
    exit 1
fi

if ! echo "${GET_BODY}" | grep -q '"status":"SUCCESS"'; then
    echo "[FAIL] Payment lookup returned incorrect status"
    exit 1
fi
echo "[PASS] Payment lookup verified."

# 4. Prometheus Metrics Verification (GET /metrics)
echo "Scraping Prometheus metrics from /metrics..."
METRICS_BODY=$(curl -s "${BASE_URL}/metrics")

if ! echo "${METRICS_BODY}" | grep -q "http_requests_total"; then
    echo "[FAIL] Prometheus metrics missing http_requests_total"
    exit 1
fi
echo "[PASS] Prometheus metrics endpoint operational."

echo "=================================================================="
echo " [SUCCESS] All Smoke Tests Passed for Environment: ${ENV_NAME}"
echo "=================================================================="
exit 0
