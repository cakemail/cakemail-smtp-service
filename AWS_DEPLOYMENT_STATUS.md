# AWS Production Deployment - Status

**Date**: October 2, 2025
**Cluster**: smtp-gateway-prod
**Region**: us-east-1
**Account ID**: 639799576130

## Current Status

### ✅ Completed

1. **AWS Credentials Verified**
   - Account: 639799576130
   - User: kb-platform-deploy
   - Region: us-east-1

2. **ECR Repository Created**
   - Repository: `smtp-gateway`
   - URI: `639799576130.dkr.ecr.us-east-1.amazonaws.com/smtp-gateway`
   - Image scanning: Enabled (scanOnPush)
   - Encryption: AES256

3. **EKS Cluster Configuration Created**
   - File: `deployment/aws/eks-cluster-config.yaml`
   - Cluster name: `smtp-gateway-prod`
   - Kubernetes version: 1.28
   - Node group: `smtp-gateway-nodes` (t3.medium, 2-6 nodes)
   - VPC CIDR: 10.0.0.0/16
   - Availability zones: us-east-1c, us-east-1d

4. **Deployment Script Created**
   - File: `deploy-aws-production.sh`
   - Automated deployment workflow ready

### ⏳ In Progress

**EKS Cluster Creation** - Started at 13:23 (EDT)
- CloudFormation stack deploying
- Estimated completion: 15-20 minutes
- Monitor progress: AWS CloudFormation console

### ⏸️ Pending (Waiting for Prerequisites)

1. **Docker Daemon** - Needs to be started
   - Required for building and pushing images
   - Action: Start Docker Desktop

2. **Docker Image Build & Push** - Waits for Docker + EKS
   - Build image from Dockerfile
   - Tag: v1.0.0 and latest
   - Push to ECR

3. **Kubernetes Deployment** - Waits for EKS cluster
   - Update kubeconfig
   - Install cert-manager
   - Deploy SMTP Gateway with Helm
   - Configure LoadBalancers

## Infrastructure Details

### EKS Cluster Configuration

```yaml
Cluster Name: smtp-gateway-prod
Kubernetes: 1.28
Region: us-east-1
Zones: us-east-1c, us-east-1d

Node Group: smtp-gateway-nodes
  Instance Type: t3.medium
  Min Size: 2
  Max Size: 6
  Desired: 2
  Volume: 50 GB gp3
  Networking: Private subnets

Addons:
  - vpc-cni (latest)
  - coredns (latest)
  - kube-proxy (latest)
  - aws-ebs-csi-driver (latest)
  - metrics-server

Logging:
  - api
  - audit
  - authenticator
  - controllerManager
  - scheduler

IAM:
  - OIDC enabled
  - Auto-scaler policy
  - EBS CSI policy
  - CloudWatch policy
  - ALB Ingress policy
```

### Network Architecture

```
Internet
   │
   ├─── Public Subnets (us-east-1c, us-east-1d)
   │    ├─ 10.0.0.0/19 (1c)
   │    ├─ 10.0.32.0/19 (1d)
   │    └─ NAT Gateway
   │
   └─── Private Subnets (us-east-1c, us-east-1d)
        ├─ 10.0.64.0/19 (1c)
        ├─ 10.0.96.0/19 (1d)
        └─ EKS Nodes (t3.medium)
             └─ SMTP Gateway Pods
```

### Application Configuration

```yaml
SMTP Gateway Deployment:
  Replicas: 2 (HPA: 2-10)
  Resources:
    Requests: 500m CPU, 512Mi RAM
    Limits: 1000m CPU, 1Gi RAM

  Services:
    - SMTP (port 587) - NLB
    - Health (port 8080) - NLB

  Autoscaling:
    Target CPU: 70%
    Target Memory: 75%

  High Availability:
    PodDisruptionBudget: minAvailable=1
    Multi-AZ deployment
```

## Next Steps (After EKS is Ready)

### 1. Start Docker Desktop
```bash
# Manual step - open Docker Desktop GUI
```

### 2. Run Automated Deployment
```bash
./deploy-aws-production.sh
```

This script will:
1. ✅ Verify Docker is running
2. ✅ Wait for EKS cluster to be ACTIVE
3. ✅ Update kubeconfig
4. ✅ Build Docker image
5. ✅ Push to ECR
6. ✅ Install Helm (if needed)
7. ✅ Install cert-manager
8. ✅ Create Let's Encrypt ClusterIssuers
9. ✅ Deploy SMTP Gateway
10. ✅ Wait for LoadBalancers
11. ✅ Display endpoints and next steps

### 3. Configure DNS (Manual)

Once LoadBalancer is provisioned:
```bash
# Get LoadBalancer hostname
kubectl get svc smtp-gateway -n smtp-gateway

# Create DNS CNAME record:
# smtp.yourdomain.com -> <NLB-HOSTNAME>
```

### 4. Enable Production TLS (Optional)

Update Helm values to use cert-manager:
```yaml
tls:
  certManager:
    enabled: true
    issuerName: "letsencrypt-prod"
    commonName: "smtp.yourdomain.com"
```

### 5. Verify Deployment

```bash
# Check pods
kubectl get pods -n smtp-gateway

# Check services
kubectl get svc -n smtp-gateway

# View logs
kubectl logs -n smtp-gateway -l app=smtp-gateway -f

# Test health endpoint
HEALTH_LB=$(kubectl get svc smtp-gateway-health -n smtp-gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
curl http://${HEALTH_LB}:8080/health/live
curl http://${HEALTH_LB}:8080/health/ready
curl http://${HEALTH_LB}:8080/metrics
```

### 6. Test SMTP Connection

```bash
# Get SMTP endpoint
SMTP_LB=$(kubectl get svc smtp-gateway -n smtp-gateway -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

# Test with telnet
telnet ${SMTP_LB} 587

# Or test with Python
python3 <<EOF
import smtplib
from email.mime.text import MIMEText

msg = MIMEText("Test email body")
msg['Subject'] = 'Test Email'
msg['From'] = 'sender@example.com'
msg['To'] = 'recipient@example.com'

server = smtplib.SMTP('${SMTP_LB}', 587)
server.starttls()
server.login('your-username', 'your-password')
server.send_message(msg)
server.quit()
print("Email sent successfully!")
EOF
```

## Monitoring

### CloudWatch Logs

EKS cluster logs are sent to CloudWatch:
- Log Group: `/aws/eks/smtp-gateway-prod/cluster`
- Enabled: api, audit, authenticator, controllerManager, scheduler

### Prometheus Metrics

Access via port-forward:
```bash
kubectl port-forward -n smtp-gateway svc/smtp-gateway-health 8080:8080
curl http://localhost:8080/metrics
```

## Cost Estimation

**Monthly AWS Costs** (approximate):

| Resource | Quantity | Unit Cost | Monthly Cost |
|----------|----------|-----------|--------------|
| EKS Control Plane | 1 | $0.10/hour | $73 |
| t3.medium nodes | 2-6 | $0.0416/hour | $60-180 |
| NLB | 2 | $0.0225/hour | $33 |
| EBS volumes (gp3) | 100 GB | $0.08/GB | $8 |
| Data transfer | ~100 GB | $0.09/GB | $9 |
| CloudWatch Logs | 10 GB | $0.50/GB | $5 |
| **Total** | | | **$188-308/month** |

*Costs vary based on actual usage and auto-scaling*

## Cleanup (If Needed)

To delete everything:
```bash
# Delete Helm deployment
helm uninstall smtp-gateway -n smtp-gateway

# Delete namespace
kubectl delete namespace smtp-gateway
kubectl delete namespace cert-manager

# Delete EKS cluster (THIS WILL DELETE EVERYTHING!)
eksctl delete cluster --name smtp-gateway-prod --region us-east-1

# Delete ECR repository
aws ecr delete-repository --repository-name smtp-gateway --region us-east-1 --force
```

## Support

- EKS Cluster Status: `eksctl get cluster --name smtp-gateway-prod --region us-east-1`
- CloudFormation: https://console.aws.amazon.com/cloudformation
- EKS Console: https://console.aws.amazon.com/eks
- ECR Console: https://console.aws.amazon.com/ecr

## Current Limitations (Epic 4 - To Be Implemented)

- ❌ No rate limiting (per-IP/per-user)
- ❌ No circuit breaker (API protection)
- ❌ No load testing validation
- ❌ No error recovery queue
- ❌ No Grafana dashboards

**Recommendation**: Monitor initial deployment closely, start with limited traffic, implement Epic 4 features before full production load.
