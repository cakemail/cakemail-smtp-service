# SMTP Gateway - Production Deployment Guide

## Prerequisites

### Infrastructure Requirements
- Kubernetes cluster (v1.24+)
- Helm 3.x installed
- kubectl configured with cluster access
- Docker registry access (e.g., registry.cakemail.com)
- TLS certificate for SMTP (or cert-manager installed)

### Required Secrets
- Cakemail API credentials/endpoints
- TLS certificate and key (if not using cert-manager)
- Container registry credentials (if private registry)

## Quick Start - Local k3d Testing

### 1. Start Local Cluster
```bash
# Start Docker Desktop first
# Then start k3d cluster
k3d cluster start profitcake

# Verify cluster is running
kubectl cluster-info
```

### 2. Build and Load Image
```bash
# Build Docker image
docker build -f deployment/docker/Dockerfile -t smtp-gateway:latest .

# Import image into k3d
k3d image import smtp-gateway:latest --cluster profitcake
```

### 3. Deploy with kubectl
```bash
# Create namespace
kubectl create namespace smtp-gateway

# Create TLS secret (for testing - uses self-signed cert)
kubectl create secret generic smtp-gateway-tls \
  --from-literal=tls.crt="" \
  --from-literal=tls.key="" \
  -n smtp-gateway

# Deploy application
kubectl apply -f deployment/kubernetes/ -n smtp-gateway

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=smtp-gateway -n smtp-gateway --timeout=60s
```

### 4. Test Locally
```bash
# Port forward SMTP port
kubectl port-forward -n smtp-gateway svc/smtp-gateway 587:587 &

# Port forward health endpoint
kubectl port-forward -n smtp-gateway svc/smtp-gateway-health 8080:8080 &

# Test health endpoint
curl http://localhost:8080/health/live

# Test SMTP (requires mail client)
# Connect to localhost:587
```

## Production Deployment

### 1. Build and Push Image

```bash
# Set your registry
export REGISTRY="registry.cakemail.com"
export IMAGE_TAG="v1.0.0"

# Build image
docker build -f deployment/docker/Dockerfile \
  -t ${REGISTRY}/smtp-gateway:${IMAGE_TAG} \
  -t ${REGISTRY}/smtp-gateway:latest .

# Login to registry
docker login ${REGISTRY}

# Push image
docker push ${REGISTRY}/smtp-gateway:${IMAGE_TAG}
docker push ${REGISTRY}/smtp-gateway:latest
```

### 2. Install Helm (if needed)

```bash
# macOS
brew install helm

# Or download from https://helm.sh/docs/intro/install/
```

### 3. Prepare TLS Certificates

#### Option A: Use cert-manager (Recommended)
```bash
# Install cert-manager if not already installed
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer (Let's Encrypt production)
cat <<EOF | kubectl apply -f -
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
```

#### Option B: Use Existing Certificate
```bash
# Create TLS secret from existing certificate
kubectl create secret tls smtp-gateway-tls-prod \
  --cert=/path/to/smtp.cakemail.com.crt \
  --key=/path/to/smtp.cakemail.com.key \
  -n smtp-gateway
```

### 4. Configure Values

Create `values-production.yaml`:
```yaml
replicaCount: 4

image:
  repository: registry.cakemail.com/smtp-gateway
  tag: "v1.0.0"
  pullPolicy: Always

resources:
  limits:
    cpu: 2000m
    memory: 2Gi
  requests:
    cpu: 1000m
    memory: 1Gi

autoscaling:
  enabled: true
  minReplicas: 4
  maxReplicas: 20
  targetCPUUtilizationPercentage: 70

config:
  cakemailApiUrl: "https://api.cakemail.com/v1"
  cakemailAuthUrl: "https://api.cakemail.com/v1/auth"
  logLevel: "INFO"
  smtpPort: 587
  healthPort: 8080
  maxRecipients: 100

tls:
  enabled: true
  secretName: "smtp-gateway-tls-prod"
  # OR use cert-manager
  # certManager:
  #   enabled: true
  #   issuerName: "letsencrypt-prod"

service:
  type: LoadBalancer
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"  # AWS
    # cloud.google.com/load-balancer-type: "Internal"        # GCP
    # service.beta.kubernetes.io/azure-load-balancer-internal: "true"  # Azure

serviceMonitor:
  enabled: true
  interval: 15s

podDisruptionBudget:
  enabled: true
  minAvailable: 2
```

### 5. Deploy with Helm

```bash
# Create namespace
kubectl create namespace smtp-gateway

# Install/upgrade deployment
helm upgrade --install smtp-gateway \
  ./deployment/helm/smtp-gateway \
  -f values-production.yaml \
  --namespace smtp-gateway \
  --wait \
  --timeout 5m

# Check deployment status
kubectl get pods -n smtp-gateway
kubectl get svc -n smtp-gateway
```

### 6. Verify Deployment

```bash
# Check pod status
kubectl get pods -n smtp-gateway

# Check logs
kubectl logs -n smtp-gateway -l app=smtp-gateway --tail=50

# Test health endpoint
HEALTH_IP=$(kubectl get svc smtp-gateway-health -n smtp-gateway -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl http://${HEALTH_IP}:8080/health/live
curl http://${HEALTH_IP}:8080/health/ready

# Check metrics
curl http://${HEALTH_IP}:8080/metrics

# Get SMTP service external IP
SMTP_IP=$(kubectl get svc smtp-gateway -n smtp-gateway -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "SMTP Gateway available at: ${SMTP_IP}:587"
```

## DNS Configuration

Point your SMTP domain to the LoadBalancer IP:

```bash
# Get LoadBalancer IP
kubectl get svc smtp-gateway -n smtp-gateway

# Create DNS A record
# smtp.cakemail.com -> <LOADBALANCER_IP>
```

## Testing Production Deployment

### 1. Test with Python
```python
import smtplib
from email.mime.text import MIMEText

msg = MIMEText("Test email body")
msg['Subject'] = 'Test Email'
msg['From'] = 'sender@example.com'
msg['To'] = 'recipient@example.com'

server = smtplib.SMTP('smtp.cakemail.com', 587)
server.starttls()
server.login('your-username', 'your-password')
server.send_message(msg)
server.quit()

print("Email sent successfully!")
```

### 2. Test with swaks (Swiss Army Knife for SMTP)
```bash
swaks --to recipient@example.com \
  --from sender@example.com \
  --server smtp.cakemail.com:587 \
  --tls \
  --auth LOGIN \
  --auth-user your-username \
  --auth-password your-password \
  --header "Subject: Test Email" \
  --body "This is a test email"
```

### 3. Monitor Logs
```bash
# Follow logs from all pods
kubectl logs -n smtp-gateway -l app=smtp-gateway -f

# Check for errors
kubectl logs -n smtp-gateway -l app=smtp-gateway | grep -i error
```

## Monitoring

### Access Prometheus Metrics
```bash
# Port forward to access metrics
kubectl port-forward -n smtp-gateway svc/smtp-gateway-health 8080:8080

# View metrics
curl http://localhost:8080/metrics

# Key metrics to monitor:
# - smtp_connections_total
# - smtp_auth_attempts_total
# - smtp_emails_submitted_total
# - smtp_email_submission_duration_seconds
# - smtp_api_errors_total
```

### Grafana Dashboard (if available)
- Import dashboard from `/deployment/monitoring/grafana-dashboard.json`
- Monitor: throughput, latency, error rates, pod health

## Rollback

If issues occur:

```bash
# Rollback to previous version
helm rollback smtp-gateway -n smtp-gateway

# Or scale down to zero
kubectl scale deployment smtp-gateway -n smtp-gateway --replicas=0
```

## Troubleshooting

### Pods not starting
```bash
kubectl describe pod -n smtp-gateway -l app=smtp-gateway
kubectl logs -n smtp-gateway -l app=smtp-gateway
```

### TLS certificate issues
```bash
# Check TLS secret
kubectl get secret smtp-gateway-tls-prod -n smtp-gateway
kubectl describe certificate smtp-gateway-tls -n smtp-gateway

# Check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager
```

### Service not accessible
```bash
# Check service
kubectl get svc -n smtp-gateway
kubectl describe svc smtp-gateway -n smtp-gateway

# Check network policies
kubectl get networkpolicy -n smtp-gateway
```

### High memory/CPU usage
```bash
# Check resource usage
kubectl top pods -n smtp-gateway

# Check HPA status
kubectl get hpa -n smtp-gateway

# Scale manually if needed
kubectl scale deployment smtp-gateway -n smtp-gateway --replicas=6
```

## Security Checklist

Before production launch:

- [ ] TLS certificates from trusted CA (not self-signed)
- [ ] Network policies enabled
- [ ] Pod Security Standards enforced
- [ ] Resource limits configured
- [ ] PodDisruptionBudget configured
- [ ] ServiceAccount with minimal permissions
- [ ] Secrets managed via external secrets operator (optional)
- [ ] Container image scanned for vulnerabilities
- [ ] Rate limiting configured (TODO: Epic 4)
- [ ] Monitoring and alerting configured

## Limited Production Testing Checklist

For initial beta testing:

- [ ] Docker image builds successfully
- [ ] Kubernetes cluster accessible
- [ ] TLS certificates configured
- [ ] DNS record created
- [ ] Health endpoints responding
- [ ] Test email sent successfully
- [ ] Logs show no errors
- [ ] Metrics being collected
- [ ] HPA configured (autoscaling works)
- [ ] PDB prevents all pods going down

## Next Steps

After successful deployment:

1. **Monitor for 24-48 hours** - Watch logs, metrics, errors
2. **Test with real traffic** - Start with small subset of users
3. **Add Epic 4 features**:
   - Rate limiting (Story 4.3)
   - Circuit breaker (Story 4.4)
   - Load testing (Story 4.5)
4. **Set up alerting** - PagerDuty, Slack notifications
5. **Document runbooks** - Common issues and fixes
6. **Gradually increase traffic** - Ramp up over 1-2 weeks

## Support

For issues or questions:
- Check logs: `kubectl logs -n smtp-gateway -l app=smtp-gateway`
- Check metrics: `curl http://<HEALTH_IP>:8080/metrics`
- Review PROJECT_STATUS.md for known limitations
- Check Epic 3 completion: All email features working
- Missing: Rate limiting, circuit breaker, load testing (Epic 4)
