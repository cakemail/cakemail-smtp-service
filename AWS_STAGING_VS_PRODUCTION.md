# AWS Deployment: Staging vs Production Comparison

## Overview

This document compares the staging and production deployment configurations for the SMTP Gateway on AWS EKS.

## Cost Comparison

| Component | Staging | Production | Monthly Savings |
|-----------|---------|------------|-----------------|
| **EKS Control Plane** | $73 | $73 | $0 |
| **EC2 Instances** | 1-3x t3.small | 2-6x t3.medium | ~$120 |
| **Storage (EBS)** | 20-60 GB | 100-300 GB | ~$10 |
| **Network Load Balancers** | 2x NLB | 2x NLB | $0 |
| **Data Transfer** | ~10 GB | ~100 GB | ~$8 |
| **CloudWatch Logs** | 1 GB | 10 GB | ~$4 |
| **TOTAL** | **~$90-110/month** | **~$260-350/month** | **~$170-240** |

## Resource Comparison

### Compute Resources

| Metric | Staging | Production |
|--------|---------|------------|
| **Instance Type** | t3.small (2 vCPU, 2GB) | t3.medium (2 vCPU, 4GB) |
| **Node Count** | 1-3 nodes | 2-6 nodes |
| **Pod Replicas** | 1 replica | 2-4 replicas |
| **Auto-scaling** | Disabled | Enabled (HPA) |
| **CPU per Pod** | 100m-500m | 500m-1000m |
| **Memory per Pod** | 128Mi-512Mi | 512Mi-1Gi |

### Storage

| Metric | Staging | Production |
|--------|---------|------------|
| **Volume Size** | 20 GB/node | 50 GB/node |
| **Volume Type** | gp3 | gp3 |
| **Total Storage** | 20-60 GB | 100-300 GB |

### Network

| Metric | Staging | Production |
|--------|---------|------------|
| **VPC CIDR** | 10.1.0.0/16 | 10.0.0.0/16 |
| **Availability Zones** | 2 (us-east-1c, 1d) | 2 (us-east-1c, 1d) |
| **NAT Gateways** | 1 (single) | 1 (single, consider 2 for HA) |
| **Load Balancers** | 2x NLB | 2x NLB |
| **Public Access** | Yes | Yes |

### Observability

| Feature | Staging | Production |
|---------|---------|------------|
| **CloudWatch Logs** | API + Audit only | All types (API, Audit, Auth, Controller, Scheduler) |
| **Prometheus** | Optional | Recommended |
| **ServiceMonitor** | Disabled | Enabled |
| **Log Retention** | 7 days | 30 days |

## Configuration Files

### Staging
- **Cluster Config**: `deployment/aws/eks-staging-config.yaml`
- **Deployment Script**: `deploy-aws-staging.sh`
- **Cluster Name**: `smtp-gateway-staging`

### Production
- **Cluster Config**: `deployment/aws/eks-cluster-config.yaml`
- **Deployment Script**: `deploy-aws-production.sh`
- **Cluster Name**: `smtp-gateway-prod`

## Use Cases

### Staging Environment

**Best for:**
- ✅ Development and testing
- ✅ Limited beta testing (< 100 emails/day)
- ✅ Integration testing
- ✅ CI/CD validation
- ✅ Feature validation before production
- ✅ Cost-sensitive deployments

**Limitations:**
- ⚠️ Single replica (no HA)
- ⚠️ Limited throughput (~50-100 emails/hour)
- ⚠️ No auto-scaling
- ⚠️ Minimal logging
- ⚠️ Single point of failure

**Recommended for:**
- Initial deployment and testing
- Proof of concept
- Development iterations

### Production Environment

**Best for:**
- ✅ Production workloads (> 1000 emails/day)
- ✅ High availability requirements
- ✅ Auto-scaling needs
- ✅ Multi-region failover
- ✅ Compliance and audit requirements
- ✅ SLA commitments

**Features:**
- ✅ Multiple replicas (HA)
- ✅ Auto-scaling (2-6 nodes)
- ✅ Comprehensive logging
- ✅ PodDisruptionBudget
- ✅ Better resource allocation

**Recommended for:**
- Customer-facing production service
- After successful staging validation
- When scaling beyond 100 emails/hour

## Performance Expectations

### Staging

| Metric | Expected Value |
|--------|----------------|
| **Max Throughput** | ~50-100 emails/hour |
| **Concurrent Connections** | ~50-100 |
| **Latency (p95)** | < 500ms |
| **Latency (p99)** | < 1000ms |
| **Uptime SLA** | Best effort (no SLA) |

### Production

| Metric | Expected Value |
|--------|----------------|
| **Max Throughput** | ~500-1000 emails/hour (per node) |
| **Concurrent Connections** | ~500-1000 |
| **Latency (p95)** | < 200ms |
| **Latency (p99)** | < 500ms |
| **Uptime SLA** | 99.9% target |

## Migration Path: Staging → Production

### Step 1: Validate in Staging (1-2 weeks)
```bash
# Deploy staging
./deploy-aws-staging.sh

# Run tests
- Integration tests
- Load tests (limited)
- Feature validation
- Monitor for 1-2 weeks
```

### Step 2: Production Deployment
```bash
# Once staging is stable
./deploy-aws-production.sh

# Gradual rollout:
- Start with 10% traffic
- Monitor metrics and logs
- Increase to 50% if stable
- Full cutover after 24 hours
```

### Step 3: Monitoring & Optimization
```bash
# Monitor production
- CloudWatch dashboards
- Prometheus metrics
- Alert on errors
- Optimize based on load
```

## Quick Start Commands

### Deploy Staging
```bash
# Prerequisites: Docker Desktop running
./deploy-aws-staging.sh
```

### Deploy Production
```bash
# Prerequisites: Docker Desktop running, staging validated
./deploy-aws-production.sh
```

### Switch Between Environments
```bash
# Staging
aws eks update-kubeconfig --name smtp-gateway-staging --region us-east-1

# Production
aws eks update-kubeconfig --name smtp-gateway-prod --region us-east-1
```

## Cleanup Commands

### Delete Staging
```bash
helm uninstall smtp-gateway -n smtp-gateway
eksctl delete cluster --name smtp-gateway-staging --region us-east-1
```

### Delete Production
```bash
helm uninstall smtp-gateway -n smtp-gateway
eksctl delete cluster --name smtp-gateway-prod --region us-east-1
```

## Recommendations

### For Initial Deployment
1. **Start with Staging** - Deploy staging environment first
2. **Test Thoroughly** - Run integration tests, validate features
3. **Monitor Costs** - Track AWS costs for 1-2 weeks
4. **Optimize** - Adjust resources based on actual usage
5. **Graduate to Production** - Only after staging proves stable

### For Cost Optimization
1. **Staging Only** - Use staging for development/testing only
2. **Production On-Demand** - Create production cluster only when needed
3. **Fargate Option** - Consider Fargate for even lower costs (no EC2 management)
4. **Spot Instances** - Use spot instances for non-critical workloads

### For High Availability
1. **Multi-AZ** - Production uses 2 AZs (can expand to 3)
2. **Multiple NAT Gateways** - Consider 2 NAT gateways for production HA
3. **Cross-Region** - For DR, deploy to multiple regions
4. **Database** - If adding persistence, use RDS Multi-AZ

## Current Status

- ✅ **Staging Config Created**: Ready to deploy
- ✅ **Production Config Created**: Available if needed
- ✅ **ECR Repository**: Ready for images
- ✅ **Deployment Scripts**: Automated workflows ready
- ⏸️ **Clusters**: None currently deployed (old prod cluster being deleted)

**Next Step**: Deploy staging environment
```bash
./deploy-aws-staging.sh
```
