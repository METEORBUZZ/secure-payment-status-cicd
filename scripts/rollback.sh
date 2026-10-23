#!/usr/bin/env bash
# ==============================================================================
# Automated Kubernetes Rollback Script
# Executes 'kubectl rollout undo' on deployment or smoke test failure.
# ==============================================================================
set -euo pipefail

DEPLOYMENT_NAME="${1:-payment-status}"
NAMESPACE="${2:-dev}"
MAX_WAIT_SECONDS="${3:-60}"

echo "=================================================================="
echo " [ROLLBACK TRIGGERED] Reverting deployment '${DEPLOYMENT_NAME}'"
echo " Target Namespace: ${NAMESPACE}"
echo "=================================================================="

# Check if deployment exists in target namespace
if ! kubectl get deployment "${DEPLOYMENT_NAME}" -n "${NAMESPACE}" >/dev/null 2>&1; then
    echo "[ERROR] Deployment '${DEPLOYMENT_NAME}' not found in namespace '${NAMESPACE}'."
    exit 1
fi

echo "Current deployment rollout history:"
kubectl rollout history deployment/"${DEPLOYMENT_NAME}" -n "${NAMESPACE}"

echo "Initiating rollback via 'kubectl rollout undo'..."
kubectl rollout undo deployment/"${DEPLOYMENT_NAME}" -n "${NAMESPACE}"

echo "Waiting for rollback rollout completion (timeout: ${MAX_WAIT_SECONDS}s)..."
if kubectl rollout status deployment/"${DEPLOYMENT_NAME}" -n "${NAMESPACE}" --timeout="${MAX_WAIT_SECONDS}s"; then
    echo "[SUCCESS] Rollback completed successfully to previous healthy revision."
    echo "Active pods after rollback:"
    kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=payment-status
    exit 0
else
    echo "[CRITICAL] Rollback failed to stabilize within ${MAX_WAIT_SECONDS} seconds!"
    echo "Pod events and descriptions:"
    kubectl describe pods -n "${NAMESPACE}" -l app.kubernetes.io/name=payment-status | tail -n 30
    exit 1
fi
