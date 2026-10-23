# Security Architecture & Threat Model

**Project**: `secure-payment-status-cicd`  
**Organization**: PuneFinTech Internal Systems  
**Security Classification**: High (FinTech Payment Status REST API)

---

## 1. Overview of Security Controls

This repository implements a multi-layered defense-in-depth security model across the software development lifecycle (SDLC), container packaging, CI/CD pipeline, and Kubernetes runtime.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Code & Deps     │ ──> │ Container Image │ ──> │ CI/CD Pipeline  │ ──> │ K8s Runtime     │
│ - Pinned deps   │     │ - Multi-stage   │     │ - Gitleaks      │     │ - Non-root      │
│ - Zero secrets  │     │ - Alpine base   │     │ - Trivy gates   │     │ - Read-only FS  │
│ - Input schema  │     │ - UID 10001     │     │ - Automated undo│     │ - Drop ALL caps │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## 2. Implemented Security Controls

### 2.1 Unprivileged Non-Root Container Execution
- **Implementation**: The container explicitly creates an unprivileged system user (`appuser`, UID `10001`) and group (`appgroup`, GID `10001`) in the `Dockerfile` and switches execution using `USER 10001:10001`.
- **Why It Matters**: By default, Docker containers run as UID 0 (`root`). If an attacker escapes a container running as root, they inherit root privileges on the underlying host kernel. Running as non-root mitigates container breakout vectors and restricts filesystem tampering.

### 2.2 Pinned Base Image & Deterministic Dependencies
- **Implementation**:
  - The `Dockerfile` pins `python:3.11.9-alpine3.20`.
  - All production packages in `requirements.txt` are strictly pinned with exact versions (`==`).
- **Why It Matters**: Floating dependencies (`fastapi>=0.100.0`) introduce non-deterministic builds and supply chain risk. A compromised upstream package release can silently inject malware or vulnerabilities during standard CI builds without altering repository code. Pinning guarantees reproducible builds and establishes an immutable baseline.

### 2.3 Secret Leak Prevention (Gitleaks)
- **Implementation**: Integrated automated scanner (`scripts/scan-secrets.sh`) using custom regex rules in `.gitleaks.toml` targeting private keys, high-entropy tokens, Stripe/Razorpay keys, and database passwords.
- **Why It Matters**: Hardcoded credentials in source control are one of the most common causes of data breaches. Secret scanning acts as a blocking pre-commit and CI gate preventing credentials from ever reaching production or artifact registries.

### 2.4 Container Vulnerability Scanning (Trivy)
- **Implementation**: Container image vulnerability analysis via `scripts/scan-trivy.sh` before deployment.
- **Quality Gate**: Blocks deployment (non-zero exit code) on **CRITICAL** and **HIGH** Common Vulnerabilities and Exposures (CVEs). Suppressions require documented rationale in `.trivyignore`.
- **Why It Matters**: Detects known CVEs in installed OS libraries and language packages before container artifacts are distributed to cluster nodes.

### 2.5 Hardened Kubernetes SecurityContext
The Helm chart enforces strict pod and container-level security contexts:
- `readOnlyRootFilesystem: true`: Prevents attackers or malware from writing binaries, modifying libraries, or installing backdoors into the container root filesystem.
- `capabilities.drop: ["ALL"]`: Drops all default Linux capabilities (`CAP_NET_RAW`, `CAP_CHOWN`, etc.), restricting container processes strictly to unprivileged user space.
- `allowPrivilegeEscalation: false`: Blocks setuid binaries from elevating privileges.
- `seccompProfile.type: RuntimeDefault`: Restricts syscalls to safe default profile.
- `automountServiceAccountToken: false`: Prevents pods from obtaining automatic Kubernetes API credentials, reducing lateral movement risk inside the cluster.

### 2.6 Dynamic Secret Injection (Outside Git)
- **Implementation**: Helm values define sensitive keys through Kubernetes Secrets (`templates/secret.yaml`) populated at deployment time via Jenkins credentials, environment flags, or external secret managers (HashiCorp Vault / AWS Secrets Manager). No plain-text production secrets exist in Git.

### 2.7 Resource Quotas & Limits
- **Implementation**: Every pod defines explicit CPU and memory `requests` and `limits`.
- **Why It Matters**: Mitigates resource exhaustion and Denial of Service (DoS) attacks where a single runaway or compromised container monopolizes node CPU or triggers out-of-memory (OOM) panics across neighboring workloads.

---

## 3. What These Controls DO NOT Catch

DevOps engineers must maintain a realistic understanding of security boundaries. Automated scanners and container isolation do **NOT** protect against the following threat categories:

| Threat Category | Explanation | Remediation Strategy |
| :--- | :--- | :--- |
| **Business Logic Flaws** | Scanners check for known CVEs and syntax, not application logic flaws (e.g. allowing customer A to query customer B's payment status or unauthorized refunds). | Mandatory peer code reviews, domain-specific unit/integration tests, ABAC/RBAC authorization checks. |
| **Zero-Day Vulnerabilities** | Trivy only detects CVEs already registered in vulnerability databases. A zero-day exploit in FastAPI, Uvicorn, or the Linux kernel has no published CVE. | Defense-in-depth: read-only filesystem, dropping capabilities, runtime anomaly detection (Falco, Tetragon). |
| **Runtime Attacks & In-Memory Injections** | Scanners inspect static images at build time. They cannot detect dynamic SQL injection via crafted strings, in-memory buffer attacks, or compromised third-party HTTP endpoints during runtime. | Input validation (Pydantic), parameterized SQL statements, Web Application Firewalls (WAF), egress network filtering. |
| **Misconfigured External Systems** | A perfectly secure container deployed into a Kubernetes cluster with insecure RBAC, public NodePorts, or unauthenticated cloud storage can still be compromised. | Infrastructure as Code (IaC) policy auditing (OPA Gatekeeper, Kyverno, kube-bench). |
| **Compromised Credentials Outside Git** | If an operator's Jenkins admin token or cloud IAM credentials are leaked via phishing or workstation malware, static repository secret scanners cannot detect it. | Multi-factor authentication (MFA), short-lived IAM session tokens, secret rotation policies. |
| **Unknown Scanner Vulnerabilities** | Scanners may experience false negatives due to database sync delays or unsupported package formats. | Periodic recurring vulnerability audits, SBOM generation, and independent red-team exercises. |
