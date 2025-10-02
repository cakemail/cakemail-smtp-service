# Cakemail SMTP Gateway

High-performance SMTP gateway that bridges SMTP clients to the Cakemail Email API. Enables seamless migration from SendGrid, Mandrill, Mailgun, and AWS SES without code changes.

## Overview

The Cakemail SMTP Gateway is a stateless, async Python service that accepts standard SMTP connections and forwards emails to the Cakemail Email API. It provides drop-in compatibility with existing SMTP implementations while delivering enterprise-grade performance.

### Key Features

- **Drop-in SMTP Compatibility**: Standard SMTP protocol on port 587 with STARTTLS
- **High Performance**: 1M+ emails/hour throughput with <2s p99 processing delay
- **Enterprise Scale**: Kubernetes-native with horizontal pod autoscaling
- **Zero Code Changes**: Replace SMTP hostname and credentials - no application changes needed
- **Canadian-Owned Infrastructure**: Deployed on OVH Private Cloud for PIPEDA compliance
- **Production Ready**: 99.99% uptime SLA, comprehensive observability, and security hardening

## Architecture

```
┌─────────────┐
│ SMTP Client │ (Nodemailer, smtplib, PHPMailer, etc.)
└──────┬──────┘
       │ SMTP/TLS (Port 587)
       ▼
┌──────────────────┐
│  SMTP Gateway    │
│  - aiosmtpd      │
│  - Python 3.11+  │
│  - Async I/O     │
└──────┬───────────┘
       │ HTTPS
       ▼
┌──────────────────┐
│ Cakemail API     │
│  Email Delivery  │
└──────────────────┘
```

### Component Design

- **Stateless Architecture**: No persistent storage, instant horizontal scaling
- **Async Processing**: Python asyncio with aiosmtpd for high concurrency
- **Protocol Translation**: SMTP → Cakemail Email API format transformation
- **Kubernetes Native**: Health probes, metrics, auto-scaling, multi-zone deployment

For detailed architecture documentation, see [docs/architecture.md](docs/architecture.md).

## Quick Start

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Local Development Setup

1. **Clone the repository**

```bash
git clone https://github.com/cakemail/smtp-gateway.git
cd smtp-gateway
```

2. **Create and activate virtual environment**

```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -e ".[dev]"
```

4. **Configure environment variables**

Create a `.env` file in the project root:

```bash
# Cakemail API Configuration
CAKEMAIL_API_URL=https://api.cakemail.com/v1
CAKEMAIL_AUTH_URL=https://api.cakemail.com/v1/auth

# SMTP Server Configuration
SMTP_HOST=0.0.0.0
SMTP_PORT=587
TLS_CERT_PATH=./certs/cert.pem
TLS_KEY_PATH=./certs/key.pem

# HTTP Server Configuration
HTTP_HOST=0.0.0.0
HTTP_PORT=8080

# Logging
LOG_LEVEL=INFO

# Rate Limiting
RATE_LIMIT_PER_IP=100
MAX_CONNECTIONS_PER_POD=1000
CONNECTION_TIMEOUT=300
MESSAGE_SIZE_LIMIT=26214400
```

5. **Generate self-signed certificate for local development**

```bash
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes -subj "/CN=localhost"
```

6. **Run the gateway**

```bash
python -m smtp_gateway
```

The gateway will start with:
- SMTP server on port 587
- HTTP health/metrics endpoints on port 8080

7. **Test the connection**

```bash
# Test SMTP connection with OpenSSL
openssl s_client -connect localhost:587 -starttls smtp

# Test health endpoint
curl http://localhost:8080/health/live
curl http://localhost:8080/health/ready
curl http://localhost:8080/metrics
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=smtp_gateway --cov-report=html

# Run only unit tests
pytest -m unit

# Run specific test file
pytest tests/unit/test_email_parser.py
```

### Code Quality Tools

```bash
# Format code with black
black src/ tests/

# Lint with ruff
ruff check src/ tests/

# Type check with mypy
mypy src/

# Run all pre-commit hooks
pre-commit run --all-files
```

### Install Pre-commit Hooks

```bash
pre-commit install
```

This will automatically run formatting and linting on every commit.

## Usage Example

### Sending Email via SMTP

**Python Example (smtplib):**

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Create message
msg = MIMEMultipart()
msg['From'] = 'sender@example.com'
msg['To'] = 'recipient@example.com'
msg['Subject'] = 'Test Email via Cakemail SMTP Gateway'

msg.attach(MIMEText('This is a test email body.', 'plain'))

# Connect and send
with smtplib.SMTP('smtp.cakemail.com', 587) as server:
    server.starttls()
    server.login('your-username', 'your-password')
    server.send_message(msg)
```

**Node.js Example (Nodemailer):**

```javascript
const nodemailer = require('nodemailer');

const transporter = nodemailer.createTransport({
  host: 'smtp.cakemail.com',
  port: 587,
  secure: false,
  auth: {
    user: 'your-username',
    pass: 'your-password'
  }
});

await transporter.sendMail({
  from: 'sender@example.com',
  to: 'recipient@example.com',
  subject: 'Test Email via Cakemail SMTP Gateway',
  text: 'This is a test email body.',
  html: '<p>This is a test email body.</p>'
});
```

**PHP Example (PHPMailer):**

```php
use PHPMailer\PHPMailer\PHPMailer;

$mail = new PHPMailer(true);
$mail->isSMTP();
$mail->Host = 'smtp.cakemail.com';
$mail->SMTPAuth = true;
$mail->Username = 'your-username';
$mail->Password = 'your-password';
$mail->SMTPSecure = PHPMailer::ENCRYPTION_STARTTLS;
$mail->Port = 587;

$mail->setFrom('sender@example.com');
$mail->addAddress('recipient@example.com');
$mail->Subject = 'Test Email via Cakemail SMTP Gateway';
$mail->Body = 'This is a test email body.';

$mail->send();
```

## Deployment

### Quick Local Testing (k3d)

For quick local testing with k3d Kubernetes cluster:

```bash
# Make sure Docker Desktop is running, then:
./deploy-local.sh
```

This script will:
1. Create/start k3d cluster
2. Build Docker image
3. Deploy with Helm
4. Verify health endpoints

Then access SMTP gateway:
```bash
# Port forward SMTP
kubectl port-forward -n smtp-gateway svc/smtp-gateway 587:587

# Test with your email client on localhost:587
```

### Docker

Build and run the Docker image:

```bash
# Build
docker build -t smtp-gateway:latest -f deployment/docker/Dockerfile .

# Run
docker run -p 587:587 -p 8080:8080 \
  -e CAKEMAIL_API_URL=https://api.cakemail.com/v1 \
  -e LOG_LEVEL=INFO \
  smtp-gateway:latest
```

### Kubernetes with Helm

Deploy to Kubernetes using Helm:

```bash
# Add Helm repository (if available)
helm repo add cakemail https://charts.cakemail.com
helm repo update

# Install
helm install smtp-gateway cakemail/smtp-gateway \
  --namespace smtp-gateway \
  --create-namespace \
  --values deployment/helm/smtp-gateway/values-prod.yaml

# Or install from local chart
helm install smtp-gateway deployment/helm/smtp-gateway \
  --namespace smtp-gateway \
  --create-namespace \
  --values deployment/helm/smtp-gateway/values-prod.yaml
```

For detailed deployment instructions, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `CAKEMAIL_API_URL` | Cakemail Email API base URL | - | Yes |
| `CAKEMAIL_AUTH_URL` | Cakemail Authentication API URL | - | Yes |
| `SMTP_HOST` | SMTP server bind address | `0.0.0.0` | No |
| `SMTP_PORT` | SMTP server port | `587` | No |
| `HTTP_HOST` | HTTP server bind address | `0.0.0.0` | No |
| `HTTP_PORT` | HTTP server port | `8080` | No |
| `TLS_CERT_PATH` | Path to TLS certificate | `/etc/smtp-gateway/tls/tls.crt` | Yes |
| `TLS_KEY_PATH` | Path to TLS private key | `/etc/smtp-gateway/tls/tls.key` | Yes |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` | No |
| `RATE_LIMIT_PER_IP` | Max emails per minute per IP | `100` | No |
| `MAX_CONNECTIONS_PER_POD` | Max concurrent connections | `1000` | No |
| `CONNECTION_TIMEOUT` | Connection idle timeout (seconds) | `300` | No |
| `MESSAGE_SIZE_LIMIT` | Max message size in bytes | `26214400` (25MB) | No |

### Performance Tuning

For optimal performance:

- Deploy 2+ pods for high availability
- Configure HPA to scale based on CPU (70% target) and emails/second
- Set resource requests: 500m CPU, 512Mi memory
- Set resource limits: 1000m CPU, 1Gi memory
- Use connection pooling (100 concurrent API connections per pod)

See [docs/architecture.md#performance-design](docs/architecture.md#performance-design) for detailed tuning guidance.

## Monitoring

### Health Endpoints

- `GET /health/live` - Liveness probe (returns 200 if process is running)
- `GET /health/ready` - Readiness probe (returns 200 if SMTP server is accepting connections)

### Metrics Endpoint

Prometheus metrics available at `GET /metrics`:

**Counters:**
- `smtp_connections_total` - Total SMTP connections
- `smtp_emails_received_total` - Total emails received
- `smtp_emails_forwarded_total` - Total emails forwarded to API
- `smtp_auth_failures_total` - Total authentication failures
- `smtp_api_errors_total` - Total API errors

**Histograms:**
- `smtp_processing_duration_seconds` - Email processing duration
- `smtp_api_latency_seconds` - Cakemail API latency
- `smtp_connection_duration_seconds` - Connection duration

**Gauges:**
- `smtp_active_connections` - Current active connections
- `smtp_api_key_cache_size` - API key cache size

For monitoring setup, see [docs/monitoring-guide.md](docs/monitoring-guide.md).

## Project Structure

```
smtp-gateway/
├── .github/
│   └── workflows/          # GitHub Actions CI/CD
├── deployment/
│   ├── helm/               # Helm charts for Kubernetes
│   ├── cert-manager/       # TLS certificate management
│   └── docker/             # Dockerfile
├── docs/                   # Documentation
├── src/
│   └── smtp_gateway/       # Main application code
│       ├── smtp/           # SMTP server and handlers
│       ├── email/          # Email parsing and transformation
│       ├── api/            # Cakemail API client
│       ├── http/           # Health and metrics endpoints
│       └── utils/          # Utilities
├── tests/
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── load/               # Load tests
├── pyproject.toml          # Python project configuration
└── README.md               # This file
```

## Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make changes and write tests
3. Run tests and linting: `pytest && black . && ruff check .`
4. Commit with pre-commit hooks: `git commit -m "feat: your feature"`
5. Push and create pull request

### Commit Message Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test changes
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `chore:` - Build/tooling changes

## Contributing

We welcome contributions! Please see our contribution guidelines for details.

### Development Setup

1. Fork the repository
2. Clone your fork
3. Create a feature branch
4. Make changes with tests
5. Submit a pull request

## Security

For security issues, please email security@cakemail.com instead of using the issue tracker.

## License

MIT License - see LICENSE file for details.

## Support

- Documentation: [docs/](docs/)
- Issues: [GitHub Issues](https://github.com/cakemail/smtp-gateway/issues)
- Email: support@cakemail.com

## Roadmap

### Current: MVP (v0.1.0)
- Core SMTP server with TLS
- Authentication and authorization
- Email parsing (headers, body, attachments)
- Cakemail API integration
- Kubernetes deployment

### Planned: Post-MVP
- Multi-region deployment
- Webhook support for delivery status
- Enhanced observability (distributed tracing)
- Rate limiting per customer
- Legacy port support (25, 465)

See [docs/prd.md](docs/prd.md) for full product roadmap.

## Performance Targets

- **Throughput**: 1M+ emails/hour
- **Latency**: <2s p99 processing delay
- **API Latency**: <100ms p95
- **Uptime**: 99.99% SLA
- **Scaling**: 2-20 pods with HPA

## Credits

Built with:
- [aiosmtpd](https://aiosmtpd.readthedocs.io/) - Async SMTP server
- [httpx](https://www.python-httpx.org/) - Async HTTP client
- [FastAPI](https://fastapi.tiangolo.com/) - HTTP framework
- [structlog](https://www.structlog.org/) - Structured logging
- [Prometheus](https://prometheus.io/) - Metrics and monitoring
