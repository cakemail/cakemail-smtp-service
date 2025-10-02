# Deployment Documentation

This directory contains all deployment-related documentation for the SMTP Gateway.

## Quick Links

### Getting Started
- **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Complete deployment guide for all environments
  - Local k3d testing
  - Docker deployment
  - Kubernetes with Helm
  - Production deployment checklist

### AWS Deployment
- **[AWS_STAGING_VS_PRODUCTION.md](AWS_STAGING_VS_PRODUCTION.md)** - Compare staging and production configurations
  - Cost comparison ($90-110/month vs $260-350/month)
  - Resource allocation
  - Performance expectations
  - Migration path

- **[AWS_DEPLOYMENT_STATUS.md](AWS_DEPLOYMENT_STATUS.md)** - Current AWS deployment status
  - Infrastructure details
  - Network architecture
  - Next steps
  - Monitoring and costs

## Deployment Scripts

Located in project root:

- **`deploy-local.sh`** - Deploy to local k3d cluster for testing
- **`deploy-aws-staging.sh`** - Deploy to AWS EKS staging environment
- **`deploy-aws-production.sh`** - Deploy to AWS EKS production environment

## Quick Start Commands

### Local Testing (k3d)
```bash
./deploy-local.sh
```

### AWS Staging
```bash
./deploy-aws-staging.sh
```

### AWS Production
```bash
./deploy-aws-production.sh
```

## Documentation Structure

```
docs/
├── deployment/
│   ├── README.md (this file)
│   ├── DEPLOYMENT_GUIDE.md
│   ├── AWS_STAGING_VS_PRODUCTION.md
│   └── AWS_DEPLOYMENT_STATUS.md
├── architecture.md
├── brief.md
├── prd.md
├── EPIC_1_COMPLETE.md
├── EPIC_2_COMPLETE.md
└── PROJECT_STATUS.md
```

## Environment Comparison

| Environment | Cost/Month | Use Case |
|-------------|------------|----------|
| **Local k3d** | Free | Development, quick testing |
| **AWS Staging** | $90-110 | Integration testing, limited beta |
| **AWS Production** | $260-350 | Production workloads, high availability |

## Support

For deployment issues:
1. Check logs: `kubectl logs -n smtp-gateway -l app=smtp-gateway`
2. Review PROJECT_STATUS.md for known limitations
3. Consult architecture.md for system design
