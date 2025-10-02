#!/bin/bash
set -e

echo "=== SMTP Gateway - Local k3d Deployment ==="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    exit 1
fi

echo "✅ Docker is running"

# Check if k3d cluster exists
if ! k3d cluster list | grep -q profitcake; then
    echo "Creating k3d cluster 'profitcake'..."
    k3d cluster create profitcake \
        --port "587:587@loadbalancer" \
        --port "8080:8080@loadbalancer"
else
    echo "✅ k3d cluster 'profitcake' exists"
    # Start cluster if stopped
    k3d cluster start profitcake 2>/dev/null || true
fi

# Wait for cluster to be ready
echo "Waiting for cluster to be ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=60s

echo "✅ Cluster is ready"

# Build Docker image
echo ""
echo "Building Docker image..."
docker build -f deployment/docker/Dockerfile -t smtp-gateway:latest .

echo "✅ Docker image built"

# Import image into k3d
echo ""
echo "Importing image into k3d..."
k3d image import smtp-gateway:latest --cluster profitcake

echo "✅ Image imported to k3d"

# Create namespace
echo ""
echo "Creating namespace..."
kubectl create namespace smtp-gateway --dry-run=client -o yaml | kubectl apply -f -

# Install/upgrade with Helm
echo ""
echo "Installing with Helm..."

# Check if Helm is installed
if ! command -v helm &> /dev/null; then
    echo "❌ Helm is not installed. Installing Helm..."
    brew install helm
fi

# Create values for local deployment
cat > /tmp/values-local.yaml <<EOF
replicaCount: 1

image:
  repository: smtp-gateway
  tag: "latest"
  pullPolicy: Never

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 100m
    memory: 128Mi

autoscaling:
  enabled: false

config:
  cakemailApiUrl: "https://api.cakemail.com/v1"
  cakemailAuthUrl: "https://api.cakemail.com/v1/auth"
  logLevel: "DEBUG"
  smtpPort: 587
  healthPort: 8080

tls:
  enabled: false  # Auto-generate self-signed cert

service:
  type: LoadBalancer

serviceMonitor:
  enabled: false  # No Prometheus in local cluster

podDisruptionBudget:
  enabled: false
EOF

helm upgrade --install smtp-gateway \
  ./deployment/helm/smtp-gateway \
  -f /tmp/values-local.yaml \
  --namespace smtp-gateway \
  --wait \
  --timeout 2m

echo "✅ Helm deployment complete"

# Wait for pod to be ready
echo ""
echo "Waiting for pod to be ready..."
kubectl wait --for=condition=ready pod -l app=smtp-gateway -n smtp-gateway --timeout=60s

echo "✅ Pod is ready"

# Get service info
echo ""
echo "=== Deployment Complete ==="
echo ""
kubectl get pods -n smtp-gateway
echo ""
kubectl get svc -n smtp-gateway

echo ""
echo "=== Testing Health Endpoints ==="
echo ""

# Port forward for testing
kubectl port-forward -n smtp-gateway svc/smtp-gateway-health 8080:8080 &
PF_PID=$!
sleep 2

# Test health endpoint
echo "Testing /health/live..."
curl -s http://localhost:8080/health/live | jq . || echo "Health check failed"

echo ""
echo "Testing /health/ready..."
curl -s http://localhost:8080/health/ready | jq . || echo "Ready check failed"

echo ""
echo "Testing /metrics..."
curl -s http://localhost:8080/metrics | head -n 10

# Kill port forward
kill $PF_PID 2>/dev/null || true

echo ""
echo "=== SMTP Gateway is Ready! ==="
echo ""
echo "To access SMTP:"
echo "  kubectl port-forward -n smtp-gateway svc/smtp-gateway 587:587"
echo ""
echo "To view logs:"
echo "  kubectl logs -n smtp-gateway -l app=smtp-gateway -f"
echo ""
echo "To access health endpoint:"
echo "  kubectl port-forward -n smtp-gateway svc/smtp-gateway-health 8080:8080"
echo "  curl http://localhost:8080/health/live"
echo ""
echo "To delete deployment:"
echo "  helm uninstall smtp-gateway -n smtp-gateway"
echo "  kubectl delete namespace smtp-gateway"
echo ""
