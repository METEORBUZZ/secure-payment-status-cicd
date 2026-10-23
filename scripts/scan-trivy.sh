#!/usr/bin/env bash
# ==============================================================================
# Trivy Container Vulnerability Scanning Script
# Scans built Docker images for CVEs, failing on CRITICAL and HIGH vulnerabilities.
# ==============================================================================
set -euo pipefail

TARGET_IMAGE="${1:-secure-payment-status:v1.0.0}"
SEVERITY_LEVEL="${2:-HIGH,CRITICAL}"
REPORT_FILE="trivy-results.json"

echo "=================================================================="
echo " Trivy Security Gate: Scanning image '${TARGET_IMAGE}'"
echo " Severity Threshold: ${SEVERITY_LEVEL}"
echo "=================================================================="

rm -f "${REPORT_FILE}"

if command -v trivy >/dev/null 2>&1; then
    echo "Found local Trivy binary: $(trivy --version | head -n 1)"
    # 1. Output human-readable summary table
    trivy image \
        --severity "${SEVERITY_LEVEL}" \
        --format table \
        "${TARGET_IMAGE}" || true

    # 2. Generate JSON report for CI archiving
    trivy image \
        --severity "${SEVERITY_LEVEL}" \
        --format json \
        --output "${REPORT_FILE}" \
        "${TARGET_IMAGE}" || true

    # 3. Security Quality Gate: Fail on CRITICAL and HIGH
    echo "Evaluating Quality Gate..."
    trivy image \
        --exit-code 1 \
        --severity "${SEVERITY_LEVEL}" \
        --ignorefile .trivyignore \
        --ignore-unfixed \
        "${TARGET_IMAGE}"
    SCAN_EXIT=$?
else
    echo "Using containerized Trivy (aquasec/trivy:latest)..."

    # Run Trivy in container mounting docker socket and workspace
    docker run --rm \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$(pwd):/workspace" \
        -v "${HOME}/.cache/trivy:/root/.cache/" \
        aquasec/trivy:latest image \
        --severity "${SEVERITY_LEVEL}" \
        --ignorefile /workspace/.trivyignore \
        --format table \
        "${TARGET_IMAGE}" || true

    docker run --rm \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$(pwd):/workspace" \
        -v "${HOME}/.cache/trivy:/root/.cache/" \
        aquasec/trivy:latest image \
        --severity "${SEVERITY_LEVEL}" \
        --ignorefile /workspace/.trivyignore \
        --format json \
        --output "/workspace/${REPORT_FILE}" \
        "${TARGET_IMAGE}" || true

    echo "Evaluating Quality Gate (Failing if ${SEVERITY_LEVEL} unfixed CVEs exist)..."
    docker run --rm \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$(pwd):/workspace" \
        -v "${HOME}/.cache/trivy:/root/.cache/" \
        aquasec/trivy:latest image \
        --exit-code 1 \
        --severity "${SEVERITY_LEVEL}" \
        --ignorefile /workspace/.trivyignore \
        --ignore-unfixed \
        "${TARGET_IMAGE}"
    SCAN_EXIT=$?
fi

if [ "${SCAN_EXIT}" -eq 0 ]; then
    echo "[SUCCESS] Trivy scan passed. Zero unfixed ${SEVERITY_LEVEL} vulnerabilities found."
    exit 0
else
    echo "[SECURITY FAILURE] Trivy discovered ${SEVERITY_LEVEL} vulnerabilities violating the security gate!"
    exit 1
fi
