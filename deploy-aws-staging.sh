#!/bin/bash
set -e

echo "=== SMTP Gateway - AWS Staging Deployment ==="
echo ""

# Configuration
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="639799576130"
ECR_REPOSITORY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/smtp-gateway"
CLUSTER_NAME="smtp-gateway-staging"
IMAGE_TAG="staging-$(date +%Y%m%d-%H%M%S)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Step 1: Verify Prerequisites${NC}"
echo ""

# Check Docker
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker is running${NC}"

# Check AWS credentials
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo -e "${RED}❌ AWS credentials not configured${NC}"
    exit 1
fi
echo -e "${GREEN}✅ AWS credentials configured${NC}"

echo ""
echo -e "${YELLOW}Step 2: Create Staging EKS Cluster${NC}"
echo ""

# Check if cluster exists
if aws eks describe-cluster --name ${CLUSTER_NAME} --region ${AWS_REGION} &>/dev/null; then
    echo -e "${GREEN}✅ EKS cluster already exists${NC}"
else
    echo "Creating staging EKS cluster (this takes ~15 minutes)..."
    eksctl create cluster -f deployment/aws/eks-staging-config.yaml
    echo -e "${GREEN}✅ EKS cluster created${NC}"
fi

# Update kubeconfig
aws eks update-kubeconfig --name ${CLUSTER_NAME} --region ${AWS_REGION}
echo -e "${GREEN}✅ Kubeconfig updated${NC}"

# Wait for nodes
kubectl wait --for=condition=Ready nodes --all --timeout=300s
echo -e "${GREEN}✅ Nodes ready${NC}"

echo ""
echo -e "${YELLOW}Step 3: Build and Push Docker Image${NC}"
echo ""

# Login to ECR
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REPOSITORY}

# Build
docker build -f deployment/docker/Dockerfile \
  -t ${ECR_REPOSITORY}:${IMAGE_TAG} \
  -t ${ECR_REPOSITORY}:staging \
  .

# Push
docker push ${ECR_REPOSITORY}:${IMAGE_TAG}
docker push ${ECR_REPOSITORY}:staging

echo -e "${GREEN}✅ Image pushed: ${IMAGE_TAG}${NC}"

echo ""
echo -e "${YELLOW}Step 4: Deploy SMTP Gateway${NC}"
echo ""

kubectl create namespace smtp-gateway --dry-run=client -o yaml | kubectl apply -f -

# Staging values
cat > /tmp/values-staging.yaml <<EOF
replicaCount: 1  # Single replica for staging

image:
  repository: ${ECR_REPOSITORY}
  tag: "${IMAGE_TAG}"
  pullPolicy: Always

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 100m
    memory: 128Mi

autoscaling:
  enabled: false  # Disabled for staging

config:
  cakemailApiUrl: "https://api.cakemail.com/v1"
  cakemailAuthUrl: "https://api.cakemail.com/v1/auth"
  logLevel: "DEBUG"
  smtpPort: 587
  healthPort: 8080

tls:
  enabled: false  # Self-signed cert

service:
  type: LoadBalancer
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"

serviceMonitor:
  enabled: false

podDisruptionBudget:
  enabled: false
EOF

helm upgrade --install smtp-gateway \
  ./deployment/helm/smtp-gateway \
  -f /tmp/values-staging.yaml \
  --namespace smtp-gateway \
  --wait

echo -e "${GREEN}✅ SMTP Gateway deployed${NC}"

echo ""
echo -e "${YELLOW}Step 5: Get Service Info${NC}"
echo ""

kubectl wait --for=condition=ready pod -l app=smtp-gateway -n smtp-gateway --timeout=120s

echo "Waiting for LoadBalancer..."
sleep 20

kubectl get svc -n smtp-gateway
kubectl get pods -n smtp-gateway

SMTP_LB=$(kubectl get svc smtp-gateway -n smtp-gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "pending")
HEALTH_LB=$(kubectl get svc smtp-gateway-health -n smtp-gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "pending")

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   STAGING DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Cluster: ${CLUSTER_NAME}"
echo "Image: ${IMAGE_TAG}"
echo ""
echo "SMTP: ${SMTP_LB}:587"
echo "Health: http://${HEALTH_LB}:8080"
echo ""
echo "Estimated Cost: ~\$50-70/month"
echo ""
echo "To test:"
echo "  kubectl logs -n smtp-gateway -l app=smtp-gateway -f"
echo ""
