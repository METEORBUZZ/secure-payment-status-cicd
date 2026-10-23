#!/usr/bin/env bash
# ==============================================================================
# Secret Scanning Script
# Detects hardcoded secrets, tokens, API keys, and credentials before deployment.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

echo "=================================================================="
echo " Starting Secret Scan Gate: secure-payment-status-cicd"
echo "=================================================================="

SCAN_REPORT="gitleaks-report.json"
rm -f "${SCAN_REPORT}"

if command -v gitleaks >/dev/null 2>&1; then
    echo "Found local gitleaks binary: $(gitleaks version)"
    gitleaks detect \
        --source . \
        --config .gitleaks.toml \
        --report-path "${SCAN_REPORT}" \
        --report-format json \
        --verbose \
        --redact
    SCAN_STATUS=$?
elif command -v docker >/dev/null 2>&1; then
    echo "Running Gitleaks via containerized scanner (zricethezav/gitleaks)..."
    docker run --rm \
        -v "${ROOT_DIR}:/repo:ro" \
        zricethezav/gitleaks:latest detect \
        --source="/repo" \
        --config="/repo/.gitleaks.toml" \
        --report-format=json \
        --verbose \
        --redact
    SCAN_STATUS=$?
else
    echo "Running native regex security pattern scan..."
    # Check for potential private keys, passwords, and sensitive strings
    SUSPICIOUS=$(git grep -E -I -n "(AKIA[0-9A-Z]{16}|BEGIN PRIVATE KEY|BEGIN RSA PRIVATE KEY|stripe[_-]?secret|password\s*=\s*['\"][^'\"]{8,})" -- . \
        ':!tests' ':!.venv' ':!requirements*' ':!*.md' ':!scripts/scan-secrets.sh' || true)

    if [ -n "${SUSPICIOUS}" ]; then
        echo "[SECURITY ALERT] Potential secret strings detected:"
        echo "${SUSPICIOUS}"
        exit 1
    fi
    SCAN_STATUS=0
fi

if [ "${SCAN_STATUS}" -eq 0 ]; then
    echo "[SUCCESS] Secret scan passed. No leaked credentials or keys detected."
    exit 0
else
    echo "[SECURITY FAILURE] Secrets or credentials detected! Build rejected."
    exit 1
fi
