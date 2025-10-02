# Cakemail SMTP Gateway Product Requirements Document (PRD)

## Goals and Background Context

### Goals

- Enable seamless SMTP-based email delivery for developers migrating from SendGrid, Mandrill, Mailgun, and AWS SES without code changes
- Achieve enterprise-grade performance supporting 1M+ emails/hour for both transactional and marketing campaigns
- Provide Canadian-owned SMTP infrastructure alternative for data sovereignty and PIPEDA compliance
- Reduce customer onboarding friction from weeks (API migration) to minutes (SMTP configuration)
- Establish foundation for converting SMTP users to Cakemail REST API adoption over time

### Background Context

Many developers and organizations rely on SMTP protocol for email delivery through providers like SendGrid, Mandrill, Mailgun, and AWS SES. When considering migration to Cakemail's Email API, they face substantial barriers: existing applications are built around SMTP integration, legacy systems cannot adopt REST APIs, and migration requires weeks of development effort with significant risk. This creates acquisition friction for Cakemail, even when the platform offers superior features or pricing. Additionally, Canadian companies increasingly seek Canadian-owned infrastructure to comply with PIPEDA and avoid US-based services.

The Cakemail SMTP Gateway solves this by acting as a protocol translation layer—accepting standard SMTP connections and forwarding emails to the Cakemail Email API via HTTPS. This enables drop-in replacement: developers simply change their SMTP hostname and credentials without touching application code. The gateway is designed for enterprise scale (1M+ emails/hour, 99.99% uptime) while maintaining simplicity through a stateless Python async architecture deployed on OVH Private Cloud Kubernetes in Canadian data centers.

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-09-30 | 1.0 | Initial PRD based on Project Brief | PM (John) |

## Requirements

### Functional

**FR1:** The gateway MUST accept SMTP connections on port 587 with mandatory STARTTLS encryption

**FR2:** The gateway MUST authenticate users via username/password credentials that map to Cakemail account API keys

**FR3:** The gateway MUST parse standard SMTP email messages including headers (From, To, CC, BCC, Subject, Reply-To), body (plain text and/or HTML), and MIME attachments

**FR4:** The gateway MUST transform parsed SMTP data into Cakemail Email API format and submit via HTTPS to https://docs.cakemail.com/en/api/email-api#submit-an-email

**FR5:** The gateway MUST return standard SMTP response codes: 250 (success), 535 (authentication failure), 550 (API error), 451 (temporary failure/rate limit)

**FR6:** The gateway MUST support concurrent SMTP connections to achieve 1M+ emails/hour throughput

**FR7:** The gateway MUST validate SMTP credentials against Cakemail API on initial connection and cache results in-memory per pod

**FR8:** The gateway MUST forward API errors from Cakemail Email API to SMTP clients with appropriate SMTP error codes

**FR9:** The gateway MUST support standard SMTP commands: EHLO, STARTTLS, AUTH PLAIN, AUTH LOGIN, MAIL FROM, RCPT TO, DATA, QUIT

**FR10:** The gateway MUST handle multiple recipients (To, CC, BCC) by making individual API calls per recipient as required by Cakemail Email API

### Non Functional

**NFR1:** The gateway MUST achieve 99.99% uptime SLA over rolling 30-day periods

**NFR2:** The gateway MUST process emails with <2s p99 processing delay (SMTP accept to API response)

**NFR3:** The gateway MUST achieve <100ms p95 latency for Cakemail API forwarding (excluding network time)

**NFR4:** The gateway MUST horizontally scale via Kubernetes HPA to handle traffic spikes and maintain performance targets

**NFR5:** The gateway MUST be stateless with no persistent storage requirements for horizontal scaling

**NFR6:** The gateway MUST expose Prometheus metrics endpoint for monitoring (emails/sec, latency, error rates, connection counts)

**NFR7:** The gateway MUST emit structured JSON logs to stdout for Kubernetes logging aggregation

**NFR8:** The gateway MUST implement health check endpoints (liveness and readiness probes) for Kubernetes orchestration

**NFR9:** The gateway MUST deploy to OVH Private Cloud Kubernetes in Canadian data centers for PIPEDA compliance

**NFR10:** The gateway MUST use TLS certificates from Let's Encrypt managed by cert-manager for SMTP connections

**NFR11:** The gateway MUST protect against credential theft by never storing credentials persistently and clearing in-memory cache on pod restart

**NFR12:** The gateway MUST implement connection throttling and rate limiting to prevent abuse (spam relay attempts)

## Technical Assumptions

### Repository Structure: Single Repository

The gateway will use a single repository structure. A monorepo is unnecessary for a single-service architecture.

### Service Architecture

**Stateless Monolith with Horizontal Scaling**

The gateway is architected as a stateless monolith deployed on Kubernetes with horizontal pod autoscaling (HPA):

- Multiple gateway pods behind a Kubernetes Service (load balancer)
- Auto-scaling based on CPU/memory utilization and custom metrics (emails/second)
- Async processing model using Python asyncio: Each pod handles thousands of concurrent SMTP connections
- No shared state between pods—all authentication and session data is ephemeral

**Technology Stack:**
- **Language**: Python 3.11+
- **SMTP Server**: aiosmtpd (async SMTP server library)
- **HTTP Client**: httpx (async HTTP client for Cakemail API calls)
- **Metrics/Health**: FastAPI for /health and /metrics endpoints
- **Infrastructure**: OVH Private Cloud Kubernetes, cert-manager, Helm

**Rationale:** Stateless monolith provides simplicity for a 1-3 developer team while achieving enterprise performance through horizontal scaling. Python async with aiosmtpd and httpx delivers high concurrency with clean, maintainable code.

### Testing Requirements

**Full Testing Pyramid:**
- **Unit Tests**: Core logic (SMTP parsing, API transformation, error handling) with pytest
- **Integration Tests**: SMTP-to-API flow testing with real Cakemail API staging environment
- **Load Tests**: Performance validation using k6 or Locust to simulate 1M+ emails/hour
- **Manual Smoke Tests**: Pre-production validation of SMTP compatibility with popular libraries (Nodemailer, smtplib, PHPMailer)

**Rationale:** Given performance targets (99.99% uptime, 1M+ emails/hour) and migration-critical use case, comprehensive testing is essential to prevent production issues.

### Additional Technical Assumptions and Requests

- **Authentication API Endpoint**: Assumes Cakemail Email API provides an endpoint to validate SMTP credentials (username/password) and return corresponding API keys. If this endpoint does not exist, it must be built before gateway development begins.
- **Cakemail API Capacity**: Assumes Cakemail Email API can handle sustained load of 1M+ emails/hour from gateway traffic. Early load testing against staging API required.
- **OVH Multi-Zone Availability**: Assumes OVH Private Cloud Kubernetes supports multi-zone deployment for achieving 99.99% uptime. Architect must validate and design for zone redundancy.
- **TLS Certificate Automation**: Assumes cert-manager and Let's Encrypt integration will work on OVH infrastructure. Fallback: manual certificate management if automation unavailable.
- **Prometheus + Grafana Stack**: Assumes OVH environment has or can deploy Prometheus for metrics collection. Gateway will expose metrics endpoint; monitoring infrastructure setup is out of scope for gateway development.
- **No Message Queuing**: Gateway forwards emails synchronously to Cakemail API. Retry logic and delivery guarantees are delegated to Cakemail Email API. If API is unavailable, gateway returns SMTP 451 (temporary failure) to client for client-side retry.
- **Connection Limits**: Architect should define per-pod connection limits and overall system capacity to prevent resource exhaustion.

## Epic List

**Epic 1: Foundation & Core SMTP Server**
Establish project infrastructure (repo, CI/CD, Kubernetes manifests) and implement basic SMTP server that accepts connections, performs TLS handshake, and returns health checks. First deployable increment with canary functionality.

**Epic 2: Authentication & Cakemail API Integration**
Implement SMTP authentication (username/password), integrate with Cakemail Email API for credential validation, and establish basic email forwarding to API (single recipient, plain text only).

**Epic 3: Full Email Message Support**
Add complete SMTP message parsing (multi-recipient, HTML bodies, MIME attachments, all standard headers) and transform to Cakemail Email API format. Support all production email use cases.

**Epic 4: Production Readiness & Observability**
Implement comprehensive observability (Prometheus metrics, structured logging, distributed tracing), error handling, connection throttling, and performance optimization to meet SLA targets (99.99% uptime, 1M+ emails/hour, <2s p99).

## Epic 1: Foundation & Core SMTP Server

**Epic Goal:** Establish the foundational project infrastructure and deploy a basic SMTP server to Kubernetes that can accept connections, perform TLS handshakes, and respond to health checks. This epic delivers the first deployable increment, validating that the infrastructure works end-to-end even before email functionality is implemented.

### Story 1.1: Project Setup and Repository Structure

As a **developer**,
I want the project repository initialized with Python structure and dev tooling,
so that the team can start development with consistent standards.

**Acceptance Criteria:**

1. Repository created with Python 3.11+ project structure (src/, tests/, docs/, deployment/)
2. pyproject.toml configured with dependencies (aiosmtpd, httpx, fastapi, pytest, black, ruff)
3. .gitignore configured for Python projects
4. README.md includes project description, local dev setup instructions, and architecture overview
5. Pre-commit hooks configured for black (formatting) and ruff (linting)
6. GitHub Actions workflow created for CI (lint, format check, unit tests)

### Story 1.2: Basic SMTP Server Implementation

As a **developer**,
I want a basic SMTP server that accepts connections on port 587,
so that I can validate SMTP protocol handling works locally.

**Acceptance Criteria:**

1. Python aiosmtpd server accepts TCP connections on port 587
2. Server responds to EHLO command with server capabilities
3. Server accepts QUIT command and closes connection gracefully
4. Server runs locally via `python -m smtp_gateway.server`
5. Basic logging to stdout for connection events (connect, EHLO, QUIT)
6. Unit tests for server initialization and basic SMTP command handling

### Story 1.3: TLS/STARTTLS Support

As a **security-conscious user**,
I want SMTP connections encrypted via STARTTLS,
so that email content and credentials are protected in transit.

**Acceptance Criteria:**

1. Server responds to STARTTLS command and upgrades connection to TLS
2. Self-signed certificate generated for local development
3. TLS context configured with secure defaults (TLS 1.2+, strong cipher suites)
4. Server rejects plaintext authentication before STARTTLS
5. Integration test verifies successful TLS handshake using Python smtplib client
6. Documentation added for TLS certificate requirements

### Story 1.4: Health Check and Metrics Endpoints

As a **DevOps engineer**,
I want health check endpoints for Kubernetes probes,
so that K8s can manage pod lifecycle correctly.

**Acceptance Criteria:**

1. FastAPI HTTP server runs alongside SMTP server on port 8080
2. GET /health/live returns 200 OK (liveness probe)
3. GET /health/ready returns 200 OK when SMTP server is accepting connections (readiness probe)
4. GET /metrics returns Prometheus format metrics (basic: process_cpu, process_memory, smtp_connections_total)
5. Both HTTP and SMTP servers run in same async event loop
6. Unit tests for health endpoints

### Story 1.5: Dockerfile and Container Build

As a **DevOps engineer**,
I want a production-ready Docker image,
so that the gateway can be deployed to Kubernetes.

**Acceptance Criteria:**

1. Multi-stage Dockerfile created (build stage + runtime stage)
2. Image based on python:3.11-slim for minimal size
3. Non-root user configured for container security
4. Image includes only runtime dependencies (no dev tools)
5. GitHub Actions workflow builds and pushes image to container registry on main branch
6. Image tagged with git commit SHA and "latest"
7. Local docker build and run succeeds: `docker build -t smtp-gateway . && docker run -p 587:587 -p 8080:8080 smtp-gateway`

### Story 1.6: Kubernetes Deployment Manifests

As a **DevOps engineer**,
I want Kubernetes manifests to deploy the gateway to OVH,
so that the service runs in production infrastructure.

**Acceptance Criteria:**

1. Helm chart created in deployment/helm/smtp-gateway/
2. Deployment manifest defines pod spec with liveness/readiness probes
3. Service manifest exposes SMTP (587) and HTTP (8080) ports
4. ConfigMap for non-sensitive configuration (log level, API endpoints)
5. Secret manifest template for sensitive values (API keys, credentials)
6. HorizontalPodAutoscaler configured for CPU-based scaling (min: 2, max: 10, target: 70% CPU)
7. ResourceRequests and Limits defined (requests: 500m CPU/512Mi memory, limits: 1000m CPU/1Gi memory)
8. Documentation for deploying to OVH Kubernetes with helm install command

### Story 1.7: cert-manager Integration for TLS Certificates

As a **DevOps engineer**,
I want automated TLS certificate management via cert-manager,
so that the gateway uses valid certificates without manual intervention.

**Acceptance Criteria:**

1. cert-manager ClusterIssuer manifest created for Let's Encrypt (production and staging)
2. Certificate CRD manifest created for smtp.cakemail.com (or configured domain)
3. Deployment updated to mount certificate secret as volume
4. SMTP server configured to load TLS certificate from mounted path
5. Certificate automatically renews before expiration (validated via staging Let's Encrypt)
6. Documentation added for cert-manager prerequisites and DNS configuration
7. Fallback documentation for manual certificate management if cert-manager unavailable

## Epic 2: Authentication & Cakemail API Integration

**Epic Goal:** Implement SMTP authentication (username/password), integrate with Cakemail Email API for credential validation, and establish the first end-to-end email forwarding flow from SMTP to the Cakemail API. This epic focuses on the simplest case (single recipient, plain text body) to validate the core protocol translation works before adding complexity.

### Story 2.1: SMTP AUTH Command Implementation

As a **developer**,
I want the SMTP server to support AUTH PLAIN and AUTH LOGIN commands,
so that clients can authenticate before sending emails.

**Acceptance Criteria:**

1. Server advertises AUTH PLAIN and AUTH LOGIN in EHLO response (only after STARTTLS)
2. Server parses AUTH PLAIN credentials (base64-encoded username/password)
3. Server parses AUTH LOGIN credentials (interactive base64 challenge/response)
4. Server stores decoded credentials in session state for authentication validation
5. Server rejects AUTH commands before STARTTLS with 530 error
6. Unit tests for AUTH PLAIN and AUTH LOGIN parsing with valid and invalid inputs
7. Integration test verifies smtplib client can authenticate successfully

### Story 2.2: Cakemail Authentication API Client

As a **developer**,
I want to validate SMTP credentials against Cakemail API,
so that only authorized users can send emails.

**Acceptance Criteria:**

1. HTTP client module created using httpx for async API calls
2. Function `validate_credentials(username, password)` calls Cakemail auth endpoint
3. Function returns API key on success, raises AuthenticationError on failure
4. API endpoint URL configurable via environment variable
5. Timeout configured (5 seconds) with retry logic (2 retries with exponential backoff)
6. Unit tests with mocked httpx responses (success, auth failure, timeout, 500 error)
7. Integration test against Cakemail staging API validates real credentials

### Story 2.3: SMTP Authentication Flow Integration

As a **user**,
I want SMTP authentication to validate my Cakemail credentials,
so that I can securely send emails through the gateway.

**Acceptance Criteria:**

1. After successful AUTH command, server calls `validate_credentials()` with SMTP username/password
2. On auth success: store API key in session, return 235 SMTP code, allow MAIL FROM command
3. On auth failure: return 535 SMTP code with message "Authentication failed", close connection
4. On API timeout/error: return 451 SMTP code "Temporary authentication failure, try again"
5. Authenticated API key cached in-memory (per session) to avoid redundant API calls
6. MAIL FROM command rejected with 530 "Authentication required" if client not authenticated
7. Integration test: full SMTP session from connection → STARTTLS → AUTH → MAIL FROM success

### Story 2.4: Simple Email Message Parsing

As a **developer**,
I want to parse basic SMTP email messages (DATA command),
so that I can extract email content for API forwarding.

**Acceptance Criteria:**

1. Server accepts DATA command after RCPT TO and receives message content until ".\r\n"
2. Parse email headers: From, To, Subject (using Python email.parser module)
3. Extract plain text body (single part, non-MIME messages only)
4. Store parsed email in structured format: `{from, to, subject, body_text}`
5. Server returns 250 "Message accepted" after DATA completion
6. Unit tests for parsing valid and malformed email messages
7. **Out of scope for this story**: Multi-recipient, HTML, attachments, MIME (deferred to Epic 3)

### Story 2.5: Cakemail Email API Integration

As a **developer**,
I want to transform SMTP email data into Cakemail Email API format and submit,
so that emails are delivered via Cakemail infrastructure.

**Acceptance Criteria:**

1. Function `submit_email(api_key, email_data)` transforms SMTP format to Cakemail API format
2. Makes POST request to https://docs.cakemail.com/en/api/email-api#submit-an-email using httpx
3. Uses authenticated API key from SMTP session in Authorization header
4. API request format matches Cakemail Email API spec (single recipient, plain text)
5. Returns API response (success with message ID, or error with reason)
6. Timeout configured (10 seconds) with single retry on network error
7. Unit tests with mocked API responses (success, 400 validation error, 429 rate limit, 500 error)
8. Integration test submits real email to Cakemail staging API and verifies delivery

### Story 2.6: End-to-End Email Forwarding Flow

As a **user**,
I want to send a simple email via SMTP and have it delivered via Cakemail,
so that I can validate the gateway works end-to-end.

**Acceptance Criteria:**

1. Complete SMTP session: EHLO → STARTTLS → AUTH → MAIL FROM → RCPT TO → DATA → QUIT
2. On successful API submission: return 250 "Message accepted for delivery: {api_message_id}"
3. On API validation error (400): return 550 "Message rejected: {api_error_reason}"
4. On API rate limit (429): return 451 "Rate limit exceeded, try again later"
5. On API server error (500): return 451 "Temporary failure, try again later"
6. On network error: return 451 "Service temporarily unavailable"
7. Log complete flow: connection → auth success → API submission → response
8. Integration test: Send email via Python smtplib → verify appears in Cakemail staging inbox
9. **Limitation**: Only single recipient, plain text body supported (Epic 3 adds full support)

### Story 2.7: Error Handling and Connection Management

As a **developer**,
I want robust error handling and connection cleanup,
so that the gateway remains stable under error conditions.

**Acceptance Criteria:**

1. Catch and log all exceptions in SMTP handler methods
2. Return appropriate SMTP error codes for all exception types (auth errors → 535, API errors → 451, etc.)
3. Close connection gracefully on critical errors
4. Connection timeout configured (5 minutes idle, closes with 421 "Timeout")
5. Max message size enforced (10MB limit, returns 552 "Message too large")
6. Clean up session state and close API connections on QUIT or connection close
7. Unit tests verify error handling for each error scenario

## Epic 3: Full Email Message Support

**Epic Goal:** Add complete SMTP message parsing and transformation capabilities to support all production email use cases: multiple recipients (To, CC, BCC), HTML bodies, MIME attachments, and comprehensive email headers. This epic completes the feature set required for real-world email sending.

### Story 3.1: Multiple Recipient Support

As a **user**,
I want to send emails to multiple recipients via To, CC, and BCC,
so that I can communicate with multiple people in one message.

**Acceptance Criteria:**

1. Accept multiple RCPT TO commands in SMTP session (up to 100 recipients)
2. Parse To, CC, BCC headers from email message
3. For each recipient, make individual Cakemail API call (API may require per-recipient submission)
4. Track success/failure per recipient and aggregate results
5. Return 250 success if at least one recipient succeeds, log failures for others
6. Return 550 failure if all recipients fail with error details
7. Unit tests for multi-recipient parsing and API call batching
8. Integration test: Send email to 3 recipients → verify all receive email via Cakemail

### Story 3.2: HTML Email Body Support

As a **user**,
I want to send HTML-formatted emails,
so that I can create visually appealing marketing and transactional emails.

**Acceptance Criteria:**

1. Parse multipart/alternative MIME messages (plain text + HTML parts)
2. Extract both plain text and HTML body content
3. Transform both parts into Cakemail API format (API supports both text and HTML)
4. Preserve HTML structure and inline CSS
5. Fall back to plain text if HTML parsing fails
6. Unit tests for HTML email parsing (simple HTML, complex HTML with CSS, malformed HTML)
7. Integration test: Send HTML email → verify renders correctly in recipient inbox

### Story 3.3: MIME Attachment Support

As a **user**,
I want to send email attachments,
so that I can share files with recipients.

**Acceptance Criteria:**

1. Parse multipart/mixed MIME messages with attachments
2. Extract attachment metadata (filename, content-type, size)
3. Base64-decode attachment content
4. Transform attachments into Cakemail API format (inline or as attachment)
5. Enforce attachment size limits (10MB per attachment, 25MB total per email)
6. Return 552 "Message too large" if limits exceeded
7. Unit tests for attachment parsing (single attachment, multiple attachments, various MIME types)
8. Integration test: Send email with PDF attachment → verify recipient receives file

### Story 3.4: Comprehensive Email Header Support

As a **developer**,
I want to parse and forward all standard email headers,
so that email clients display messages correctly.

**Acceptance Criteria:**

1. Parse additional headers: Reply-To, CC, BCC, Date, Message-ID, In-Reply-To, References
2. Generate Message-ID if not provided by client (format: `<uuid@smtp.cakemail.com>`)
3. Add Received header to track gateway transit
4. Transform headers into Cakemail API format (map SMTP headers to API fields)
5. Preserve custom X-* headers if supported by Cakemail API
6. Unit tests for header parsing and transformation
7. Integration test: Verify all headers present in delivered email

### Story 3.5: Advanced MIME Parsing Edge Cases

As a **developer**,
I want robust MIME parsing that handles edge cases,
so that the gateway works with all email clients and libraries.

**Acceptance Criteria:**

1. Handle nested multipart messages (multipart/mixed containing multipart/alternative)
2. Parse inline images (multipart/related with Content-ID references)
3. Handle non-UTF-8 character encodings (ISO-8859-1, Windows-1252, etc.) with proper decoding
4. Parse quoted-printable and base64 content transfer encodings
5. Handle malformed MIME boundaries gracefully (log warning, attempt best-effort parsing)
6. Limit MIME nesting depth (max 10 levels) to prevent DoS attacks
7. Unit tests for edge cases (nested MIME, inline images, various encodings, malformed messages)
8. Integration test: Send complex email from Nodemailer (Node.js) and PHPMailer (PHP) → verify delivery

### Story 3.6: Client Compatibility Testing

As a **product manager**,
I want the gateway tested with popular SMTP libraries,
so that we ensure drop-in compatibility with SendGrid/Mailgun.

**Acceptance Criteria:**

1. Integration tests using Nodemailer (Node.js) - send transactional and marketing emails
2. Integration tests using smtplib (Python) - send with attachments and HTML
3. Integration tests using PHPMailer (PHP) - send complex MIME messages
4. Integration tests using ActionMailer (Ruby on Rails) - send application emails
5. Integration tests using System.Net.Mail (.NET) - send from enterprise applications
6. Document any known limitations or library-specific quirks in README
7. All tests pass with 100% email delivery success rate
8. Performance test: Send 1000 emails via each library → measure throughput and error rate

## Epic 4: Production Readiness & Observability

**Epic Goal:** Implement comprehensive observability (Prometheus metrics, structured logging), error handling, connection throttling, and performance optimization to achieve production SLA targets: 99.99% uptime, 1M+ emails/hour throughput, and <2s p99 processing delay. This epic transforms the gateway from functional to production-ready.

### Story 4.1: Structured Logging Implementation

As a **DevOps engineer**,
I want structured JSON logs for all gateway operations,
so that I can debug issues and analyze system behavior in production.

**Acceptance Criteria:**

1. Replace basic logging with structured JSON logging (using Python structlog library)
2. Log all SMTP events: connection, auth (success/failure), email received, API submission, errors
3. Include correlation ID (unique per SMTP session) in all log entries for tracing
4. Log levels configured via environment variable (DEBUG, INFO, WARNING, ERROR)
5. Sensitive data (passwords, API keys, email content) excluded from logs or redacted
6. Performance: logging overhead <5ms p99 per log entry
7. Integration test: Process email → verify complete session trace in logs with correlation ID

### Story 4.2: Comprehensive Prometheus Metrics

As a **DevOps engineer**,
I want detailed Prometheus metrics exposed,
so that I can monitor gateway health and performance.

**Acceptance Criteria:**

1. Counter metrics: `smtp_connections_total`, `smtp_emails_received_total`, `smtp_emails_forwarded_total`, `smtp_auth_failures_total`, `smtp_api_errors_total`
2. Histogram metrics: `smtp_processing_duration_seconds`, `smtp_api_latency_seconds`, `smtp_connection_duration_seconds`
3. Gauge metrics: `smtp_active_connections`, `smtp_api_key_cache_size`
4. Metrics labeled by: result (success/failure), error_type, smtp_command
5. /metrics endpoint returns Prometheus format with all metrics
6. Performance: metrics collection overhead <1ms per operation
7. Unit tests verify metrics increment correctly for all code paths

### Story 4.3: Connection Throttling and Rate Limiting

As a **security engineer**,
I want connection throttling and rate limiting,
so that the gateway is protected from abuse and DoS attacks.

**Acceptance Criteria:**

1. Per-IP connection limit: Max 10 concurrent connections per IP address
2. Per-IP rate limit: Max 100 emails per minute per IP address
3. Global connection limit: Max 1000 concurrent connections per pod
4. Return 421 "Too many connections" when limits exceeded
5. Failed auth attempts tracked: After 5 failures from same IP in 5 minutes, block IP for 1 hour
6. Whitelist support via ConfigMap for trusted IPs (bypass rate limits)
7. Unit tests for throttling logic, integration test: exceed limits → verify 421 error

### Story 4.4: Performance Optimization and Load Testing

As a **performance engineer**,
I want the gateway optimized for 1M+ emails/hour,
so that we meet SLA targets under production load.

**Acceptance Criteria:**

1. Connection pool for Cakemail API (max 100 concurrent connections per pod)
2. Async I/O optimizations: batch API calls where possible, use httpx connection pooling
3. Memory profiling: ensure no memory leaks under sustained load, <1GB memory per pod
4. Load test with k6 or Locust: 1M emails/hour distributed across 10 pods
5. Verify <2s p99 processing delay under load
6. Verify <100ms p95 API latency under load
7. CPU utilization <70% per pod at target load (headroom for spikes)
8. Document tuning parameters: HPA settings, resource limits, connection pool sizes

### Story 4.5: Error Handling and Retry Logic

As a **developer**,
I want comprehensive error handling with appropriate retry behavior,
so that transient failures don't impact email delivery.

**Acceptance Criteria:**

1. Classify errors: retriable (network timeout, 5xx API errors) vs non-retriable (4xx validation errors, auth failure)
2. Retry retriable errors: 2 retries with exponential backoff (1s, 2s delays)
3. Return correct SMTP codes: 451 for retriable errors, 550 for non-retriable errors
4. Circuit breaker pattern: If Cakemail API fails >50% for 1 minute, return 451 immediately (no retries) for 5 minutes
5. Dead letter queue (DLQ) logging: Log failed emails with full details for manual investigation
6. Graceful degradation: If metrics/logging fails, continue processing emails (don't fail)
7. Unit tests for all error scenarios and retry logic

### Story 4.6: Horizontal Scaling Validation

As a **DevOps engineer**,
I want to validate that the gateway scales horizontally,
so that we can handle traffic spikes and achieve 99.99% uptime.

**Acceptance Criteria:**

1. Deploy 2 pods minimum via HPA (high availability)
2. HPA scales based on CPU (target 70%) and custom metric (emails_per_second > 100)
3. Load balancer distributes connections evenly across pods (validate with connection metrics)
4. Rolling updates: Deploy new version with zero downtime (test with continuous load)
5. Pod failure handling: Kill pod during load test → verify no email loss, traffic routes to healthy pods
6. Multi-zone deployment (if supported by OVH): Pods distributed across availability zones
7. Load test: Scale from 2 → 10 pods under load → verify performance remains stable

### Story 4.7: Security Audit and Hardening

As a **security engineer**,
I want the gateway to pass security audit,
so that we can deploy to production with confidence.

**Acceptance Criteria:**

1. TLS configuration audit: Verify TLS 1.2+ only, strong cipher suites, no vulnerabilities
2. Secrets management audit: No secrets in code/logs, Kubernetes Secrets used properly
3. Input validation: All SMTP commands and email headers validated, malformed input rejected
4. Resource limits: Connection limits, message size limits, MIME nesting limits enforced
5. Network policies: Kubernetes NetworkPolicies restrict pod-to-pod communication
6. Container security: Non-root user, minimal image, no shell access, read-only filesystem where possible
7. Dependency audit: Run `pip audit` to check for vulnerable dependencies, update as needed
8. Security documentation: Document threat model, security controls, and incident response procedures

## Next Steps

### Architect Prompt

Please review this PRD and create a comprehensive technical architecture document for the Cakemail SMTP Gateway. Focus on:

1. **System Architecture**: Detail the stateless Python async architecture, component interactions (SMTP server, HTTP client, health endpoints), and data flow from SMTP → Gateway → Cakemail API
2. **Technology Stack**: Specify Python 3.11+, aiosmtpd, httpx, FastAPI, pytest, and explain why each was chosen for this use case
3. **Deployment Architecture**: Design Kubernetes deployment on OVH Private Cloud including pod topology, HPA configuration, service mesh considerations, and multi-zone redundancy for 99.99% uptime
4. **Performance Design**: Architecture decisions to achieve 1M+ emails/hour throughput and <2s p99 latency including connection pooling, async I/O patterns, and resource allocation
5. **Security Architecture**: TLS/certificate management, authentication flow (SMTP → Cakemail API validation), credential caching strategy, and network security controls
6. **Observability Design**: Logging strategy (structlog), metrics architecture (Prometheus), and distributed tracing approach
7. **API Integration**: Detailed design for Cakemail Email API integration including request/response formats, error handling, and retry strategies
8. **Scalability & Reliability**: Horizontal scaling strategy, failure modes and mitigation, circuit breaker pattern, and stateless design principles

Key constraints: OVH Private Cloud Kubernetes, Python 3.11+, stateless design, 1-3 developer team maintainability, 3-6 month timeline.

Please provide a detailed architecture document that the development team can use to implement this PRD.
