#!/bin/bash
set -e

echo "=== SMTP Gateway - AWS Production Deployment ==="
echo ""

# Configuration
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="639799576130"
ECR_REPOSITORY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/smtp-gateway"
CLUSTER_NAME="smtp-gateway-prod"
IMAGE_TAG="v1.0.0"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Step 1: Verify Prerequisites${NC}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop first.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker is running${NC}"

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo -e "${RED}❌ AWS credentials not configured${NC}"
    exit 1
fi
echo -e "${GREEN}✅ AWS credentials configured${NC}"

# Check if EKS cluster exists
echo ""
echo -e "${YELLOW}Step 2: Wait for EKS cluster to be ready${NC}"
echo "Checking cluster status..."

while true; do
    CLUSTER_STATUS=$(aws eks describe-cluster --name ${CLUSTER_NAME} --region ${AWS_REGION} --query 'cluster.status' --output text 2>/dev/null || echo "NOT_FOUND")

    if [ "$CLUSTER_STATUS" = "ACTIVE" ]; then
        echo -e "${GREEN}✅ EKS cluster is ACTIVE${NC}"
        break
    elif [ "$CLUSTER_STATUS" = "NOT_FOUND" ]; then
        echo -e "${RED}❌ EKS cluster not found. Still creating...${NC}"
        echo "Waiting 30 seconds before checking again..."
        sleep 30
    elif [ "$CLUSTER_STATUS" = "CREATING" ]; then
        echo "Cluster is still being created. Status: $CLUSTER_STATUS"
        echo "Waiting 30 seconds..."
        sleep 30
    else
        echo -e "${RED}❌ Unexpected cluster status: $CLUSTER_STATUS${NC}"
        exit 1
    fi
done

# Update kubeconfig
echo ""
echo "Updating kubeconfig..."
aws eks update-kubeconfig --name ${CLUSTER_NAME} --region ${AWS_REGION}
echo -e "${GREEN}✅ Kubeconfig updated${NC}"

# Wait for nodes to be ready
echo ""
echo "Waiting for nodes to be ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=300s || true
echo -e "${GREEN}✅ Nodes are ready${NC}"

echo ""
echo -e "${YELLOW}Step 3: Build and Push Docker Image${NC}"
echo ""

# Login to ECR
echo "Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REPOSITORY}
echo -e "${GREEN}✅ Logged into ECR${NC}"

# Build Docker image
echo ""
echo "Building Docker image..."
docker build -f deployment/docker/Dockerfile \
  -t ${ECR_REPOSITORY}:${IMAGE_TAG} \
  -t ${ECR_REPOSITORY}:latest \
  .
echo -e "${GREEN}✅ Docker image built${NC}"

# Push Docker image
echo ""
echo "Pushing Docker image to ECR..."
docker push ${ECR_REPOSITORY}:${IMAGE_TAG}
docker push ${ECR_REPOSITORY}:latest
echo -e "${GREEN}✅ Docker image pushed to ECR${NC}"

echo ""
echo -e "${YELLOW}Step 4: Install Helm and cert-manager${NC}"
echo ""

# Check if Helm is installed
if ! command -v helm &> /dev/null; then
    echo "Installing Helm..."
    brew install helm
fi
echo -e "${GREEN}✅ Helm is installed${NC}"

# Install cert-manager
echo ""
echo "Installing cert-manager..."
kubectl create namespace cert-manager --dry-run=client -o yaml | kubectl apply -f -

helm repo add jetstack https://charts.jetstack.io --force-update
helm repo update

helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --version v1.13.0 \
  --set installCRDs=true \
  --wait \
  --timeout 5m

echo -e "${GREEN}✅ cert-manager installed${NC}"

# Wait for cert-manager to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=cert-manager -n cert-manager --timeout=120s

echo ""
echo -e "${YELLOW}Step 5: Create ClusterIssuer for Let's Encrypt${NC}"
echo ""

cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: devops@cakemail.com
    privateKeySecretRef:
      name: letsencrypt-staging
    solvers:
    - http01:
        ingress:
          class: nginx
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: devops@cakemail.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF

echo -e "${GREEN}✅ ClusterIssuers created${NC}"

echo ""
echo -e "${YELLOW}Step 6: Deploy SMTP Gateway with Helm${NC}"
echo ""

# Create namespace
kubectl create namespace smtp-gateway --dry-run=client -o yaml | kubectl apply -f -

# Create production values file
cat > /tmp/values-aws-prod.yaml <<EOF
replicaCount: 2

image:
  repository: ${ECR_REPOSITORY}
  tag: "${IMAGE_TAG}"
  pullPolicy: Always

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 500m
    memory: 512Mi

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 75

config:
  cakemailApiUrl: "https://api.cakemail.com/v1"
  cakemailAuthUrl: "https://api.cakemail.com/v1/auth"
  logLevel: "INFO"
  smtpPort: 587
  healthPort: 8080
  maxRecipients: 100

tls:
  enabled: false  # Will use self-signed cert for now
  # For production with domain, uncomment:
  # certManager:
  #   enabled: true
  #   issuerName: "letsencrypt-prod"
  #   commonName: "smtp.yourdomain.com"

service:
  type: LoadBalancer
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
    service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
    service.beta.kubernetes.io/aws-load-balancer-backend-protocol: "tcp"

serviceMonitor:
  enabled: false  # Enable if Prometheus is installed

podDisruptionBudget:
  enabled: true
  minAvailable: 1

networkPolicy:
  enabled: false  # Enable for production
EOF

# Deploy with Helm
echo "Deploying SMTP Gateway..."
helm upgrade --install smtp-gateway \
  ./deployment/helm/smtp-gateway \
  -f /tmp/values-aws-prod.yaml \
  --namespace smtp-gateway \
  --wait \
  --timeout 5m

echo -e "${GREEN}✅ SMTP Gateway deployed${NC}"

echo ""
echo -e "${YELLOW}Step 7: Wait for Deployment${NC}"
echo ""

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=smtp-gateway -n smtp-gateway --timeout=120s

echo -e "${GREEN}✅ Pods are ready${NC}"

# Get LoadBalancer info
echo ""
echo -e "${YELLOW}Step 8: Get Service Information${NC}"
echo ""

echo "Waiting for LoadBalancer to be provisioned (this may take 2-3 minutes)..."
sleep 10

kubectl get svc -n smtp-gateway

echo ""
echo "Getting LoadBalancer external IP..."
SMTP_LB=""
for i in {1..30}; do
    SMTP_LB=$(kubectl get svc smtp-gateway -n smtp-gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")
    if [ -n "$SMTP_LB" ]; then
        break
    fi
    echo "Waiting for LoadBalancer... (attempt $i/30)"
    sleep 10
done

HEALTH_LB=$(kubectl get svc smtp-gateway-health -n smtp-gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "")

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   DEPLOYMENT SUCCESSFUL!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "SMTP Service:"
if [ -n "$SMTP_LB" ]; then
    echo -e "  ${GREEN}SMTP Endpoint: ${SMTP_LB}:587${NC}"
else
    echo -e "  ${YELLOW}SMTP LoadBalancer is still being provisioned${NC}"
    echo "  Run: kubectl get svc smtp-gateway -n smtp-gateway"
fi

echo ""
echo "Health Service:"
if [ -n "$HEALTH_LB" ]; then
    echo -e "  ${GREEN}Health Endpoint: http://${HEALTH_LB}:8080/health/live${NC}"
else
    echo -e "  ${YELLOW}Health LoadBalancer is still being provisioned${NC}"
fi

echo ""
echo "Pods:"
kubectl get pods -n smtp-gateway

echo ""
echo "To view logs:"
echo "  kubectl logs -n smtp-gateway -l app=smtp-gateway -f"

echo ""
echo "To test SMTP connection:"
echo "  telnet ${SMTP_LB} 587"

echo ""
echo "To update DNS:"
echo "  Create CNAME record: smtp.yourdomain.com -> ${SMTP_LB}"

echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Configure DNS to point to LoadBalancer"
echo "2. Enable TLS with cert-manager for production domain"
echo "3. Monitor logs and metrics"
echo "4. Run integration tests"
echo ""
