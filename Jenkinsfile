// ==============================================================================
// Jenkinsfile: Declarative CI/CD Pipeline for secure-payment-status-cicd
// Target SLA: Build and Deployment under 8 minutes with multi-stage security gates.
// ==============================================================================
pipeline {
    agent any

    options {
        timeout(time: 15, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
        disableConcurrentBuilds()
        timestamps()
        ansiColor('xterm')
    }

    environment {
        APP_NAME           = 'secure-payment-status'
        IMAGE_TAG          = "v1.0.0-${BUILD_NUMBER}"
        DOCKER_BUILDKIT    = '1'
        KIND_CLUSTER       = 'payment-cluster'
        MIN_COVERAGE       = '70'
        SEVERITY_GATE      = 'CRITICAL'
        DEV_NAMESPACE      = 'dev'
        STAGING_NAMESPACE  = 'staging'
        DEPLOY_FAILED      = 'false'
        FAILED_ENV         = ''
    }

    stages {
        // Stage 1: Checkout
        stage('1. Checkout') {
            steps {
                echo '=== Stage 1: SCM Checkout ==='
                checkout scm
            }
        }

        // Stage 2: Environment Validation
        stage('2. Environment Validation') {
            steps {
                echo '=== Stage 2: Tooling & Environment Verification ==='
                sh '''
                    echo "Validating required CLI binaries in PATH..."
                    python3 --version
                    docker --version
                    helm version --short
                    echo "Validating Kind cluster accessibility..."
                    kubectl cluster-info --context kind-${KIND_CLUSTER}
                '''
            }
        }

        // Stage 3: Install Dependencies
        stage('3. Install Dependencies') {
            steps {
                echo '=== Stage 3: Python Virtual Environment & Dependency Caching ==='
                sh '''
                    if [ ! -d ".venv" ]; then
                        python3 -m venv .venv
                    fi
                    . .venv/bin/activate
                    pip install --upgrade pip
                    pip install --cache-dir .pip-cache -r requirements-dev.txt
                '''
            }
        }

        // Stage 4: Lint
        stage('4. Lint') {
            steps {
                echo '=== Stage 4: Static Code Quality Analysis (Flake8) ==='
                sh '''
                    . .venv/bin/activate
                    flake8 app tests
                '''
            }
        }

        // Stage 5: Unit Tests
        stage('5. Unit Tests') {
            steps {
                echo '=== Stage 5: Pytest Execution ==='
                sh '''
                    . .venv/bin/activate
                    pytest tests -v
                '''
            }
        }

        // Stage 6: Coverage
        stage('6. Coverage') {
            steps {
                echo "=== Stage 6: Code Coverage Gate (Enforcing >${MIN_COVERAGE}%) ==="
                sh """
                    . .venv/bin/activate
                    pytest tests --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=${MIN_COVERAGE}
                """
            }
        }

        // Stage 7: Secret Scan
        stage('7. Secret Scan') {
            steps {
                echo '=== Stage 7: Repository Secret Leak Scanning (Gitleaks) ==='
                sh '''
                    chmod +x scripts/scan-secrets.sh
                    ./scripts/scan-secrets.sh
                '''
            }
        }

        // Stage 8: Docker Build
        stage('8. Docker Build') {
            steps {
                echo "=== Stage 8: Multi-Stage Secure Docker Build (${APP_NAME}:${IMAGE_TAG}) ==="
                sh """
                    docker build \
                        --build-arg BUILDKIT_INLINE_CACHE=1 \
                        -t ${APP_NAME}:${IMAGE_TAG} \
                        -t ${APP_NAME}:latest .
                    echo "Checking built image size..."
                    docker images ${APP_NAME}:${IMAGE_TAG} --format "Image Size: {{.Size}}"
                """
            }
        }

        // Stage 9: Trivy Scan
        stage('9. Trivy Scan') {
            steps {
                echo "=== Stage 9: Vulnerability Scanning Gate (${SEVERITY_GATE}) ==="
                sh """
                    chmod +x scripts/scan-trivy.sh
                    ./scripts/scan-trivy.sh ${APP_NAME}:${IMAGE_TAG} ${SEVERITY_GATE}
                """
            }
        }

        // Stage 10: Deploy to Dev
        stage('10. Deploy to Dev') {
            steps {
                echo "=== Stage 10: Loading Image & Deploying to DEV Namespace ==="
                script {
                    try {
                        sh """
                            echo "Loading Docker image into Kind cluster '${KIND_CLUSTER}'..."
                            kind load docker-image ${APP_NAME}:${IMAGE_TAG} --name ${KIND_CLUSTER}

                            echo "Applying Helm deployment to '${DEV_NAMESPACE}'..."
                            helm upgrade --install payment-status-dev helm/payment-status/ \
                                -f helm/payment-status/values-dev.yaml \
                                -n ${DEV_NAMESPACE} \
                                --set image.repository=${APP_NAME} \
                                --set image.tag=${IMAGE_TAG} \
                                --set image.pullPolicy=Never \
                                --wait \
                                --timeout=90s
                        """
                    } catch (Exception err) {
                        env.DEPLOY_FAILED = 'true'
                        env.FAILED_ENV = 'dev'
                        error "Deployment to DEV failed: ${err.message}"
                    }
                }
            }
        }

        // Stage 11: Smoke Test
        stage('11. Smoke Test') {
            steps {
                echo '=== Stage 11: DEV End-to-End Smoke Tests ==='
                script {
                    try {
                        sh '''
                            chmod +x scripts/smoke-test.sh
                            # Start port-forward to background and capture PID
                            kubectl port-forward -n dev svc/payment-status-dev 8080:8000 >/dev/null 2>&1 &
                            PF_PID=$!
                            sleep 2

                            # Execute smoke tests
                            ./scripts/smoke-test.sh http://localhost:8080 dev || { kill $PF_PID; exit 1; }
                            kill $PF_PID || true
                        '''
                    } catch (Exception err) {
                        env.DEPLOY_FAILED = 'true'
                        env.FAILED_ENV = 'dev'
                        error "DEV Smoke Test failed: ${err.message}"
                    }
                }
            }
        }

        // Stage 12: Deploy to Staging
        stage('12. Deploy to Staging') {
            steps {
                echo "=== Stage 12: Promoting to STAGING Environment ==="
                script {
                    try {
                        sh """
                            echo "Applying Helm deployment to '${STAGING_NAMESPACE}'..."
                            helm upgrade --install payment-status-staging helm/payment-status/ \
                                -f helm/payment-status/values-staging.yaml \
                                -n ${STAGING_NAMESPACE} \
                                --set image.repository=${APP_NAME} \
                                --set image.tag=${IMAGE_TAG} \
                                --set image.pullPolicy=Never \
                                --wait \
                                --timeout=90s
                        """
                    } catch (Exception err) {
                        env.DEPLOY_FAILED = 'true'
                        env.FAILED_ENV = 'staging'
                        error "Deployment to STAGING failed: ${err.message}"
                    }
                }
            }
        }

        // Stage 13: Staging Smoke Test
        stage('13. Staging Smoke Test') {
            steps {
                echo '=== Stage 13: STAGING End-to-End Smoke Tests ==='
                script {
                    try {
                        sh '''
                            chmod +x scripts/smoke-test.sh
                            # Start port-forward to background and capture PID
                            kubectl port-forward -n staging svc/payment-status-staging 8081:8000 >/dev/null 2>&1 &
                            PF_PID=$!
                            sleep 2

                            # Execute smoke tests
                            ./scripts/smoke-test.sh http://localhost:8081 staging || { kill $PF_PID; exit 1; }
                            kill $PF_PID || true
                        '''
                    } catch (Exception err) {
                        env.DEPLOY_FAILED = 'true'
                        env.FAILED_ENV = 'staging'
                        error "STAGING Smoke Test failed: ${err.message}"
                    }
                }
            }
        }

        // Stage 14: Rollback on Failure
        stage('14. Rollback on Failure') {
            when {
                expression { env.DEPLOY_FAILED == 'true' }
            }
            steps {
                echo "=== Stage 14: Automated Kubernetes Rollback for Environment '${FAILED_ENV}' ==="
                sh """
                    chmod +x scripts/rollback.sh
                    ./scripts/rollback.sh payment-status-${FAILED_ENV} ${FAILED_ENV} 90
                """
            }
        }

        // Stage 15: Cleanup
        stage('15. Cleanup') {
            always {
                echo '=== Stage 15: Pipeline Teardown and Artifact Preservation ==='
                sh '''
                    echo "Killing any dangling port-forward background processes..."
                    pkill -f "kubectl port-forward" 2>/dev/null || true
                    echo "Pruning temporary dangling Docker layers..."
                    docker image prune -f --filter "label=service=payment-status-service" 2>/dev/null || true
                '''
                archiveArtifacts artifacts: 'coverage.xml,trivy-results.json,gitleaks-report.json', allowEmptyArchive: true
                junit testResults: 'test-reports/*.xml', allowEmptyResults: true
            }
        }
    }

    post {
        failure {
            script {
                if (env.DEPLOY_FAILED == 'true') {
                    echo "CRITICAL: Triggering post-failure emergency rollback for ${env.FAILED_ENV}..."
                    sh "chmod +x scripts/rollback.sh && ./scripts/rollback.sh payment-status-${env.FAILED_ENV} ${env.FAILED_ENV} 90 || true"
                }
            }
        }
    }
}
