# Operational Runbook: PuneFinTech Payment Status Service

This runbook details operational procedures for provisioning, deploying, verifying, monitoring, and troubleshooting the `secure-payment-status-cicd` application.

---

## 1. Environment & Cluster Lifecycle

### 1.1 Provisioning the Local Kind Cluster
To provision the Kind cluster with control-plane port mappings:
```bash
# Verify Docker is running
docker info --format '{{.ServerVersion}}'

# Create the cluster using the repository configuration
kind create cluster --config kind-config.yaml

# Verify cluster connectivity
kubectl cluster-info --context kind-payment-cluster
kubectl get nodes
```

### 1.2 Creating Namespaces
```bash
kubectl create namespace dev --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace staging --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
```

### 1.3 Tearing Down the Environment
```bash
kind delete cluster --name payment-cluster
```

---

## 2. Building & Packaging

### 2.1 Running Tests and Coverage Locally
```bash
# Activate virtual environment
source .venv/bin/activate

# Execute linter
flake8 app tests

# Run unit tests with coverage gate (>70%)
pytest --cov=app --cov-report=term-missing --cov-fail-under=70
```

### 2.2 Building the Production Docker Image
```bash
docker build -t secure-payment-status:v1.0.0 -t secure-payment-status:latest .

# Verify image size is below 150 MB (target achieved: ~122 MB)
docker images secure-payment-status:v1.0.0 --format "Size: {{.Size}}"
```

### 2.3 Running Pre-Deployment Security Scans
```bash
# Secret leak scan
./scripts/scan-secrets.sh

# Container vulnerability scan
./scripts/scan-trivy.sh secure-payment-status:v1.0.0 CRITICAL
```

---

## 3. Application Deployment via Helm

### 3.1 Loading Docker Image into Kind
Because Kind nodes run inside Docker containers, local images must be loaded onto the nodes:
```bash
kind load docker-image secure-payment-status:v1.0.0 --name payment-cluster
```

### 3.2 Deploying to DEV Environment
```bash
helm upgrade --install payment-status-dev helm/payment-status/ \
  -f helm/payment-status/values-dev.yaml \
  -n dev \
  --set image.pullPolicy=Never \
  --set image.tag=v1.0.0 \
  --wait
```

### 3.3 Deploying to STAGING Environment
```bash
helm upgrade --install payment-status-staging helm/payment-status/ \
  -f helm/payment-status/values-staging.yaml \
  -n staging \
  --set image.pullPolicy=Never \
  --set image.tag=v1.0.0 \
  --wait
```

---

## 4. Verification & Health Inspection

### 4.1 Inspecting Running Pods & Services
```bash
# Check DEV pods and services
kubectl get pods,svc -n dev

# Check STAGING pods (2 replicas)
kubectl get pods,svc -n staging

# Verify non-root user UID 10001
kubectl exec -n dev deployment/payment-status-dev -- id
```

### 4.2 Viewing Live Application Logs
```bash
# Stream DEV application logs
kubectl logs -n dev deployment/payment-status-dev -f

# Stream STAGING logs
kubectl logs -n staging deployment/payment-status-staging -f --tail=50
```

### 4.3 Executing the Automated Smoke Test Suite
```bash
# Forward DEV port to localhost:8080
kubectl port-forward -n dev svc/payment-status-dev 8080:8000 &
PF_PID=$!
sleep 2

# Run smoke test script
./scripts/smoke-test.sh http://localhost:8080 dev
kill $PF_PID

# Forward STAGING port to localhost:8081
kubectl port-forward -n staging svc/payment-status-staging 8081:8000 &
PF_PID=$!
sleep 2

# Run staging smoke test
./scripts/smoke-test.sh http://localhost:8081 staging
kill $PF_PID
```

---

## 5. Automated Rollback Procedures

### 5.1 Triggering Rollback Manually
If a bad configuration or defect bypasses upstream validation and causes runtime failures:
```bash
# Rollback DEV deployment
./scripts/rollback.sh payment-status-dev dev 60

# Rollback STAGING deployment
./scripts/rollback.sh payment-status-staging staging 60
```

### 5.2 Inspecting Rollout History
```bash
kubectl rollout history deployment/payment-status-dev -n dev
kubectl rollout history deployment/payment-status-staging -n staging
```

---

## 6. Observability: Prometheus & Grafana

### 6.1 Deploying the Monitoring Stack
```bash
kubectl apply -f monitoring/prometheus/prometheus-deployment.yaml
kubectl apply -f monitoring/grafana/grafana-deployment.yaml
kubectl get pods -n monitoring
```

### 6.2 Accessing Prometheus
```bash
kubectl port-forward -n monitoring svc/prometheus 9090:9090 &
# Open in browser: http://localhost:9090
# Check active scrape targets: http://localhost:9090/targets
# Check alert rules: http://localhost:9090/alerts
```

### 6.3 Accessing Grafana
```bash
kubectl port-forward -n monitoring svc/grafana 3000:3000 &
# Open in browser: http://localhost:3000
# Default credentials: admin / admin
# Dashboard import: Navigate to Dashboards -> Import -> Select 'monitoring/grafana/dashboards/payment-service-dashboard.json'
```

---

## 7. Incident Troubleshooting Guide

| Symptom | Probable Cause | Action |
| :--- | :--- | :--- |
| **CrashLoopBackOff** | Non-root filesystem write failure or DB path error. | Check `kubectl logs -n <ns> <pod> --previous`. Ensure `DB_PATH` is set to `/data/payments.db` and `/data` is mounted. |
| **Readiness Probe Failure (503)** | Database connection check failed or service overloaded. | Check `curl http://localhost:8000/health`. Check if container CPU/memory limits throttled the worker. |
| **ErrImageNeverPull** | Built image not loaded onto Kind node. | Run `kind load docker-image secure-payment-status:<tag> --name payment-cluster`. |
| **Trivy Gate Failure** | High/Critical vulnerability detected in base image or dependency. | Review `trivy-results.json`. Update `requirements.txt` or document acceptable risk in `.trivyignore`. |
| **Gitleaks Gate Failure** | Detected token or private key string in repository. | Check `gitleaks-report.json`. Redact sensitive token immediately and invalidate credential upstream. |
