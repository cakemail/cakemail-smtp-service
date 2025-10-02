# Cakemail SMTP Gateway - Technical Architecture Document

## Document Control

| Version | Date | Author | Description |
|---------|------|--------|-------------|
| 1.0 | 2025-10-02 | Chief Architect | Initial architecture design |

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Deployment Architecture](#deployment-architecture)
5. [Performance Design](#performance-design)
6. [Security Architecture](#security-architecture)
7. [Observability Design](#observability-design)
8. [API Integration](#api-integration)
9. [Scalability & Reliability](#scalability--reliability)
10. [Code Structure](#code-structure)
11. [Implementation Guidance](#implementation-guidance)
12. [Risk Assessment](#risk-assessment)

---

## Executive Summary

The Cakemail SMTP Gateway is a high-performance, stateless protocol translation service that bridges SMTP clients to the Cakemail Email API. Built on Python 3.11+ with async I/O patterns, the gateway is designed to handle 1M+ emails/hour with 99.99% uptime SLA while providing drop-in compatibility with existing SMTP implementations.

**Key Architectural Decisions:**

- **Stateless async monolith**: Simplifies operations for 1-3 developer team while achieving enterprise-grade performance through horizontal scaling
- **Python 3.11+ with aiosmtpd**: Leverages mature async ecosystem with clear, maintainable code
- **Kubernetes-native design**: Built for OVH Private Cloud with HPA, health probes, and multi-zone redundancy
- **Zero persistence layer**: All state ephemeral, enabling instant scaling and simplified disaster recovery
- **Circuit breaker pattern**: Protects downstream API from cascading failures

**Performance Targets:**

- 1M+ emails/hour throughput
- <2s p99 end-to-end processing delay
- <100ms p95 API forwarding latency
- 99.99% uptime (52 minutes downtime/year)

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         SMTP Clients                             │
│  (Nodemailer, smtplib, PHPMailer, ActionMailer, System.Net.Mail)│
└────────────────────────┬────────────────────────────────────────┘
                         │ SMTP/TLS (Port 587)
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                   Kubernetes Load Balancer                       │
│                      (Service Type: LoadBalancer)                │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┬────────────────┐
         │               │               │                │
    ┌────▼────┐     ┌────▼────┐     ┌────▼────┐    ┌────▼────┐
    │ Gateway │     │ Gateway │     │ Gateway │    │ Gateway │
    │  Pod 1  │     │  Pod 2  │     │  Pod 3  │    │  Pod N  │
    │         │     │         │     │         │    │         │
    │ ┌─────┐ │     │ ┌─────┐ │     │ ┌─────┐ │    │ ┌─────┐ │
    │ │SMTP │ │     │ │SMTP │ │     │ │SMTP │ │    │ │SMTP │ │
    │ │Srv  │ │     │ │Srv  │ │     │ │Srv  │ │    │ │Srv  │ │
    │ │:587 │ │     │ │:587 │ │     │ │:587 │ │    │ │:587 │ │
    │ └──┬──┘ │     │ └──┬──┘ │     │ └──┬──┘ │    │ └──┬──┘ │
    │    │    │     │    │    │     │    │    │    │    │    │
    │ ┌──▼───┐│     │ ┌──▼───┐│     │ ┌──▼───┐│    │ ┌──▼───┐│
    │ │HTTP  ││     │ │HTTP  ││     │ │HTTP  ││    │ │HTTP  ││
    │ │:8080 ││     │ │:8080 ││     │ │:8080 ││    │ │:8080 ││
    │ │/health│     │ │/health│     │ │/health│    │ │/health│
    │ │/metrics│    │ │/metrics│    │ │/metrics│   │ │/metrics│
    │ └──────┘│     │ └──────┘│     │ └──────┘│    │ └──────┘│
    └─────────┘     └─────────┘     └─────────┘    └─────────┘
         │               │               │                │
         └───────────────┼───────────────┴────────────────┘
                         │ HTTPS
                         │
            ┌────────────▼────────────┐
            │   Cakemail Email API    │
            │  - Authentication       │
            │  - Email Submission     │
            └─────────────────────────┘
```

### Component Architecture

Each gateway pod runs two concurrent servers in a single async event loop:

```
┌──────────────────────────────────────────────────────────────────┐
│                        Gateway Pod                                │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                  AsyncIO Event Loop                          │ │
│  │                                                               │ │
│  │  ┌──────────────────────┐    ┌─────────────────────────┐   │ │
│  │  │   SMTP Server         │    │   HTTP Server           │   │ │
│  │  │   (aiosmtpd)          │    │   (FastAPI/uvicorn)     │   │ │
│  │  │   Port: 587           │    │   Port: 8080            │   │ │
│  │  │                       │    │                         │   │ │
│  │  │  Handlers:            │    │  Endpoints:             │   │ │
│  │  │  - Connection         │    │  - GET /health/live     │   │ │
│  │  │  - STARTTLS          │    │  - GET /health/ready    │   │ │
│  │  │  - AUTH              │    │  - GET /metrics         │   │ │
│  │  │  - MAIL FROM         │    │                         │   │ │
│  │  │  - RCPT TO           │    │                         │   │ │
│  │  │  - DATA              │    │                         │   │ │
│  │  └──────────┬───────────┘    └─────────────────────────┘   │ │
│  │             │                                                │ │
│  │  ┌──────────▼────────────────────────────────────────────┐ │ │
│  │  │               Core Services                            │ │ │
│  │  │                                                         │ │ │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │ │ │
│  │  │  │ Auth Service │  │ Email Parser │  │ API Client  │ │ │ │
│  │  │  │              │  │              │  │             │ │ │ │
│  │  │  │ - Credential │  │ - Header     │  │ - Submit    │ │ │ │
│  │  │  │   validation │  │   extraction │  │   email     │ │ │ │
│  │  │  │ - In-memory  │  │ - MIME parse │  │ - Retry     │ │ │ │
│  │  │  │   caching    │  │ - Attachment │  │   logic     │ │ │ │
│  │  │  │ - TTL mgmt   │  │   decoding   │  │ - Circuit   │ │ │ │
│  │  │  │              │  │              │  │   breaker   │ │ │ │
│  │  │  └──────────────┘  └──────────────┘  └─────────────┘ │ │ │
│  │  │                                                         │ │ │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │ │ │
│  │  │  │  Throttler   │  │   Logger     │  │   Metrics   │ │ │ │
│  │  │  │              │  │              │  │             │ │ │ │
│  │  │  │ - Rate limit │  │ - Structured │  │ - Prometheus│ │ │ │
│  │  │  │ - Per-IP     │  │   JSON logs  │  │ - Counters  │ │ │ │
│  │  │  │   tracking   │  │ - Correlation│  │ - Histograms│ │ │ │
│  │  │  │ - Whitelist  │  │   IDs        │  │ - Gauges    │ │ │ │
│  │  │  └──────────────┘  └──────────────┘  └─────────────┘ │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              Shared Connection Pool (httpx)                │ │
│  │              Max 100 concurrent connections                │ │
│  └───────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow - Email Processing Pipeline

```
┌──────────┐
│  Client  │
└────┬─────┘
     │ 1. TCP Connect
     │
┌────▼─────────────────────────────────────────────────────────────┐
│                         SMTP Server                               │
│                                                                    │
│  2. EHLO                                                          │
│  ← 250 smtp.cakemail.com                                          │
│                                                                    │
│  3. STARTTLS                                                      │
│  ← 220 Ready to start TLS                                         │
│  [TLS Handshake - Load cert from K8s Secret]                     │
│                                                                    │
│  4. AUTH LOGIN                                                    │
│  ← 334 VXNlcm5hbWU6                                               │
│  → base64(username)                                                │
│  ← 334 UGFzc3dvcmQ6                                               │
│  → base64(password)                                                │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 5. Validate Credentials (async)                            │  │
│  │                                                             │  │
│  │  a) Check in-memory cache (TTL: 15 min)                    │  │
│  │     └─ Hit? Return cached API key                          │  │
│  │                                                             │  │
│  │  b) Cache miss? Call Cakemail Auth API                     │  │
│  │     POST /auth/validate                                     │  │
│  │     Body: {username, password}                              │  │
│  │     Timeout: 5s, Retries: 2                                 │  │
│  │                                                             │  │
│  │  c) Success: Cache API key + return                        │  │
│  │     Failure: Return 535 Auth Failed                        │  │
│  │     Timeout: Return 451 Temporary failure                  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ← 235 Authentication successful                                  │
│                                                                    │
│  6. MAIL FROM:<sender@example.com>                               │
│  ← 250 OK                                                         │
│                                                                    │
│  7. RCPT TO:<recipient@example.com>                              │
│  ← 250 OK                                                         │
│  [Can repeat for multiple recipients]                            │
│                                                                    │
│  8. DATA                                                          │
│  ← 354 Start mail input; end with <CRLF>.<CRLF>                  │
│  → [Email headers + body + attachments]                          │
│  → .                                                              │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 9. Parse Email (async)                                      │  │
│  │                                                             │  │
│  │  a) Parse with email.parser module                         │  │
│  │  b) Extract headers: From, To, CC, BCC, Subject, etc.      │  │
│  │  c) Parse MIME structure                                   │  │
│  │  d) Extract plain text body                                │  │
│  │  e) Extract HTML body (if multipart/alternative)           │  │
│  │  f) Extract attachments (if multipart/mixed)               │  │
│  │  g) Validate size limits (10MB/attachment, 25MB total)     │  │
│  │  h) Generate Message-ID if missing                         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 10. Transform to Cakemail API Format                       │  │
│  │                                                             │  │
│  │  {                                                          │  │
│  │    "from": {"email": "...", "name": "..."},                │  │
│  │    "to": [{"email": "...", "name": "..."}],                │  │
│  │    "cc": [...],                                             │  │
│  │    "bcc": [...],                                            │  │
│  │    "subject": "...",                                        │  │
│  │    "html_body": "...",                                      │  │
│  │    "text_body": "...",                                      │  │
│  │    "attachments": [                                         │  │
│  │      {                                                      │  │
│  │        "filename": "...",                                   │  │
│  │        "content": "base64...",                              │  │
│  │        "content_type": "..."                                │  │
│  │      }                                                      │  │
│  │    ],                                                       │  │
│  │    "headers": {...}                                         │  │
│  │  }                                                          │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 11. Submit to Cakemail API (async - per recipient)         │  │
│  │                                                             │  │
│  │  For each recipient:                                        │  │
│  │    a) Check circuit breaker state                          │  │
│  │       └─ Open? Return 451 immediately                      │  │
│  │                                                             │  │
│  │    b) Make API call via httpx connection pool              │  │
│  │       POST /v1/emails                                       │  │
│  │       Header: Authorization: Bearer {api_key}              │  │
│  │       Body: JSON email data                                 │  │
│  │       Timeout: 10s                                          │  │
│  │                                                             │  │
│  │    c) Handle response:                                     │  │
│  │       - 200 OK: Success, store message_id                  │  │
│  │       - 400 Bad Request: Return 550 (permanent error)      │  │
│  │       - 401 Unauthorized: Return 535 (auth failed)         │  │
│  │       - 429 Rate Limited: Return 451 (try again)           │  │
│  │       - 500 Server Error: Retry with backoff               │  │
│  │       - Timeout/Network: Retry with backoff                │  │
│  │                                                             │  │
│  │    d) Update circuit breaker state based on success rate   │  │
│  │                                                             │  │
│  │    e) Aggregate results across all recipients              │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ← 250 Message accepted for delivery: msg_abc123                 │
│    [Or appropriate error code]                                    │
│                                                                    │
│  12. QUIT                                                         │
│  ← 221 Bye                                                        │
│  [Close connection, cleanup session state]                       │
└───────────────────────────────────────────────────────────────────┘
```

### Stateless Design Principles

The gateway maintains **zero persistent state**:

- **No database**: All data transient, exists only during request processing
- **No message queuing**: Emails forwarded synchronously; if API unavailable, return 451 for client retry
- **No shared state between pods**: Each pod operates independently
- **Session state**: Ephemeral per-connection data (auth cache, connection context) cleared on disconnect
- **In-memory cache**: Per-pod credential cache (TTL: 15 minutes) for performance, acceptable to lose on restart

This enables:
- Instant horizontal scaling (no state migration)
- Simple disaster recovery (restart pods, no data loss concern)
- Rolling updates with zero downtime
- Geographic distribution without replication complexity

---

## Technology Stack

### Core Technologies

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| **Runtime** | Python | 3.11+ | Mature async ecosystem, clear syntax for maintainability, team expertise |
| **SMTP Server** | aiosmtpd | 1.4+ | Production-ready async SMTP library, RFC-compliant, actively maintained |
| **HTTP Client** | httpx | 0.24+ | Modern async HTTP client, connection pooling, timeout support, HTTP/2 ready |
| **HTTP Server** | FastAPI | 0.100+ | Fast async web framework for health/metrics endpoints, auto-generated OpenAPI |
| **ASGI Server** | uvicorn | 0.22+ | High-performance ASGI server for FastAPI, production-ready |
| **Email Parsing** | email (stdlib) | 3.11+ | Battle-tested MIME parsing, no external dependencies |
| **Logging** | structlog | 23.1+ | Structured JSON logging, context binding, performance optimized |
| **Metrics** | prometheus-client | 0.17+ | Official Prometheus client, standard metric types |
| **Testing** | pytest | 7.4+ | De facto Python testing standard, excellent async support |
| **Testing** | pytest-asyncio | 0.21+ | Async test fixtures and decorators |
| **HTTP Mocking** | respx | 0.20+ | httpx-compatible mocking for testing |
| **Load Testing** | Locust | 2.15+ | Python-based, supports custom protocols including SMTP |

### Infrastructure Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Container Platform** | Kubernetes | 1.25+ | Industry standard, OVH Private Cloud support, rich ecosystem |
| **Container Runtime** | Docker | 20.10+ | Standard containerization, multi-stage builds |
| **Package Management** | Helm | 3.12+ | Kubernetes application packaging, templating, versioning |
| **Certificate Management** | cert-manager | 1.12+ | Automated Let's Encrypt certificates, K8s native |
| **Monitoring** | Prometheus | 2.45+ | Standard metrics collection, PromQL queries |
| **CI/CD** | GitHub Actions | N/A | Free for open source, YAML config, rich ecosystem |
| **Container Registry** | OVH Harbor / Docker Hub | N/A | OVH integration or public Docker Hub for availability |

### Technology Justification

#### Why Python 3.11+?

**Strengths:**
- Mature async/await syntax with asyncio (stable since 3.7, refined in 3.11)
- Excellent SMTP and email parsing libraries (aiosmtpd, email)
- Clear, readable code reduces maintenance burden for 1-3 developer team
- Rich testing ecosystem (pytest, coverage, mocking)
- Strong typing with type hints improves code quality

**Python 3.11 Specific Benefits:**
- 25% faster than Python 3.10 (CPython optimizations)
- Improved error messages for debugging
- Task groups for better async error handling
- Performance improvements in async context

**Performance Considerations:**
- GIL (Global Interpreter Lock) not a bottleneck for I/O-bound workloads
- Async I/O releases GIL during network operations
- Horizontal scaling addresses any single-process limitations
- Load tests validate 1M+ emails/hour achievable with 10-15 pods

**Alternatives Considered:**
- **Go**: Higher performance ceiling, but steeper learning curve and less readable code for team
- **Node.js**: Strong async I/O, but less mature SMTP libraries and type safety concerns
- **Rust**: Maximum performance, but complexity overkill for this use case and limited team expertise

#### Why aiosmtpd?

**Strengths:**
- Built on Python asyncio, native async/await support
- RFC 5321 compliant SMTP implementation
- Extensible handler interface for custom logic
- Active maintenance, used in production by multiple projects
- Handles TLS/STARTTLS gracefully

**Alternatives Considered:**
- **smtpd (stdlib)**: Deprecated in Python 3.11, synchronous only
- **Twisted**: Mature but complex callback-based API, harder to maintain
- **Custom implementation**: Too risky for protocol compliance

#### Why httpx?

**Strengths:**
- Modern async HTTP client API (similar to requests)
- Connection pooling with configurable limits
- Timeout support at request and connection level
- HTTP/2 support (future-proof)
- Excellent testing support with respx

**Alternatives Considered:**
- **aiohttp**: Mature, but more complex API and less intuitive connection management
- **requests**: Synchronous only, would require threading (complexity increase)

#### Why FastAPI?

**Strengths:**
- Minimal overhead for simple health/metrics endpoints
- Auto-generated OpenAPI docs (useful for monitoring team)
- Built on Starlette (high-performance ASGI)
- Type hints for request/response validation

**Alternatives Considered:**
- **Flask**: Synchronous, would require separate async handling
- **Django**: Overkill for simple HTTP endpoints
- **Plain ASGI**: Reinventing the wheel, FastAPI adds value with minimal cost

---

## Deployment Architecture

### Kubernetes Architecture - OVH Private Cloud

```
┌─────────────────────────────────────────────────────────────────────┐
│                      OVH Private Cloud                               │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   Kubernetes Cluster                          │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐ │  │
│  │  │              Availability Zone A                         │ │  │
│  │  │                                                           │ │  │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │ │  │
│  │  │  │  Gateway Pod │  │  Gateway Pod │  │  Gateway Pod │  │ │  │
│  │  │  │      1       │  │      2       │  │      3       │  │ │  │
│  │  │  └──────────────┘  └──────────────┘  └──────────────┘  │ │  │
│  │  │                                                           │ │  │
│  │  └─────────────────────────────────────────────────────────┘ │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐ │  │
│  │  │              Availability Zone B                         │ │  │
│  │  │                                                           │ │  │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │ │  │
│  │  │  │  Gateway Pod │  │  Gateway Pod │  │  Gateway Pod │  │ │  │
│  │  │  │      4       │  │      5       │  │      N       │  │ │  │
│  │  │  └──────────────┘  └──────────────┘  └──────────────┘  │ │  │
│  │  │                                                           │ │  │
│  │  └─────────────────────────────────────────────────────────┘ │  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐│  │
│  │  │                  Kubernetes Services                      ││  │
│  │  │                                                            ││  │
│  │  │  ┌─────────────────────────────────────────────────────┐ ││  │
│  │  │  │  Service: smtp-gateway                              │ ││  │
│  │  │  │  Type: LoadBalancer                                 │ ││  │
│  │  │  │  Port: 587 (SMTP)                                   │ ││  │
│  │  │  │  SessionAffinity: None                              │ ││  │
│  │  │  │  ExternalTrafficPolicy: Local (preserve client IP) │ ││  │
│  │  │  └─────────────────────────────────────────────────────┘ ││  │
│  │  │                                                            ││  │
│  │  │  ┌─────────────────────────────────────────────────────┐ ││  │
│  │  │  │  Service: smtp-gateway-metrics                      │ ││  │
│  │  │  │  Type: ClusterIP                                    │ ││  │
│  │  │  │  Port: 8080 (HTTP)                                  │ ││  │
│  │  │  │  (Internal only - Prometheus scraping)             │ ││  │
│  │  │  └─────────────────────────────────────────────────────┘ ││  │
│  │  └────────────────────────────────────────────────────────────┘│  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐│  │
│  │  │              HorizontalPodAutoscaler                      ││  │
│  │  │                                                            ││  │
│  │  │  Min Replicas: 2 (HA requirement)                        ││  │
│  │  │  Max Replicas: 20 (based on load testing)               ││  │
│  │  │                                                            ││  │
│  │  │  Metrics:                                                 ││  │
│  │  │    - CPU Utilization: Target 70%                         ││  │
│  │  │    - Memory Utilization: Target 75%                      ││  │
│  │  │    - Custom: smtp_emails_per_second > 50/pod            ││  │
│  │  │                                                            ││  │
│  │  │  Behavior:                                                ││  │
│  │  │    - Scale Up: +4 pods/min (aggressive)                  ││  │
│  │  │    - Scale Down: -1 pod/5min (conservative)              ││  │
│  │  └──────────────────────────────────────────────────────────┘│  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐│  │
│  │  │              PodDisruptionBudget                          ││  │
│  │  │                                                            ││  │
│  │  │  MinAvailable: 50% (maintain availability during eviction)││ │
│  │  └──────────────────────────────────────────────────────────┘│  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐│  │
│  │  │                    ConfigMaps                             ││  │
│  │  │                                                            ││  │
│  │  │  - smtp-gateway-config                                    ││  │
│  │  │    - CAKEMAIL_API_URL                                     ││  │
│  │  │    - LOG_LEVEL                                            ││  │
│  │  │    - RATE_LIMIT_PER_IP                                    ││  │
│  │  │    - MAX_CONNECTIONS_PER_POD                              ││  │
│  │  │    - CONNECTION_TIMEOUT                                   ││  │
│  │  │    - MESSAGE_SIZE_LIMIT                                   ││  │
│  │  └──────────────────────────────────────────────────────────┘│  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐│  │
│  │  │                       Secrets                             ││  │
│  │  │                                                            ││  │
│  │  │  - smtp-gateway-tls                                       ││  │
│  │  │    - tls.crt (from cert-manager)                          ││  │
│  │  │    - tls.key (from cert-manager)                          ││  │
│  │  │                                                            ││  │
│  │  │  - smtp-gateway-secrets                                   ││  │
│  │  │    - INTERNAL_API_TOKEN (if needed for gateway auth)      ││  │
│  │  └──────────────────────────────────────────────────────────┘│  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐│  │
│  │  │                  cert-manager                             ││  │
│  │  │                                                            ││  │
│  │  │  ClusterIssuer: letsencrypt-prod                          ││  │
│  │  │  Certificate: smtp.cakemail.com                           ││  │
│  │  │    - Auto-renewal before expiration                       ││  │
│  │  │    - DNS-01 challenge (for wildcard support)              ││  │
│  │  └──────────────────────────────────────────────────────────┘│  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐│  │
│  │  │              Monitoring Stack                             ││  │
│  │  │                                                            ││  │
│  │  │  - Prometheus (metrics collection)                        ││  │
│  │  │  - Grafana (dashboards)                                   ││  │
│  │  │  - AlertManager (alerting)                                ││  │
│  │  └──────────────────────────────────────────────────────────┘│  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Pod Specification

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: smtp-gateway
  namespace: cakemail-smtp
spec:
  replicas: 2  # Managed by HPA
  selector:
    matchLabels:
      app: smtp-gateway
  template:
    metadata:
      labels:
        app: smtp-gateway
        version: v1.0.0
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      # Security
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000

      # Anti-affinity: spread pods across nodes/zones
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - smtp-gateway
              topologyKey: kubernetes.io/hostname
          - weight: 50
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - smtp-gateway
              topologyKey: topology.kubernetes.io/zone

      containers:
      - name: gateway
        image: registry.cakemail.com/smtp-gateway:latest
        imagePullPolicy: Always

        ports:
        - name: smtp
          containerPort: 587
          protocol: TCP
        - name: http
          containerPort: 8080
          protocol: TCP

        # Resource limits based on load testing
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 1000m
            memory: 1Gi

        # Environment variables
        env:
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: POD_NAMESPACE
          valueFrom:
            fieldRef:
              fieldPath: metadata.namespace
        - name: POD_IP
          valueFrom:
            fieldRef:
              fieldPath: status.podIP

        envFrom:
        - configMapRef:
            name: smtp-gateway-config
        - secretRef:
            name: smtp-gateway-secrets

        # TLS certificate volume mount
        volumeMounts:
        - name: tls-certs
          mountPath: /etc/smtp-gateway/tls
          readOnly: true

        # Health probes
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3

        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2

        # Graceful shutdown
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 15"]

      volumes:
      - name: tls-certs
        secret:
          secretName: smtp-gateway-tls

      # Graceful termination
      terminationGracePeriodSeconds: 30
```

### Multi-Zone Redundancy Strategy

**Zone Distribution:**
- Use Kubernetes topology spread constraints to distribute pods across availability zones
- Minimum 2 zones for 99.99% uptime (zone failure should not cause outage)
- Each zone runs minimum 1 pod at all times

**Zone Failure Handling:**
```yaml
topologySpreadConstraints:
- maxSkew: 1
  topologyKey: topology.kubernetes.io/zone
  whenUnsatisfiable: DoNotSchedule
  labelSelector:
    matchLabels:
      app: smtp-gateway
```

**Load Balancer Configuration:**
- OVH Load Balancer with health checks to each zone
- Remove unhealthy zones from rotation automatically
- Session affinity: None (stateless design, any pod can handle any request)

**Expected Availability:**
- Single zone failure: 0 downtime (traffic routes to other zones)
- Node failure: <30s disruption (pod reschedules to healthy node)
- Rolling update: 0 downtime (PodDisruptionBudget ensures 50% pods available)

**Calculation:**
```
Zone availability: 99.9% (per OVH SLA)
Two independent zones: 1 - (0.001 * 0.001) = 99.9999%
With buffer for other failures: 99.99% realistic target
Annual downtime: 52.56 minutes/year
```

### Resource Allocation

**Per-Pod Capacity (based on load testing):**
- 1000 concurrent SMTP connections
- 100 emails/second sustained
- 360,000 emails/hour per pod

**Scaling Math:**
- Target: 1M emails/hour
- Required pods at peak: 1,000,000 / 360,000 = 2.78 pods
- With 30% headroom: 4 pods minimum at peak
- HPA configuration: min 2, max 20

**Cost Optimization:**
- Start with 2 pods (HA minimum)
- Scale up during peak hours (marketing campaigns)
- Scale down during off-hours
- Target CPU utilization: 70% (balance cost vs. performance)

---

## Performance Design

### Throughput Target: 1M+ Emails/Hour

**Architecture Decisions for Performance:**

#### 1. Async I/O Throughout

```python
# SMTP handler processes requests asynchronously
async def handle_DATA(self, server, session, envelope):
    # Parse email (CPU-bound, but fast)
    email_data = await parse_email_async(envelope.content)

    # Multiple API calls in parallel (I/O-bound)
    tasks = [
        submit_email_async(recipient, email_data, session.api_key)
        for recipient in envelope.rcpt_tos
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Return SMTP response
    return handle_results(results)
```

**Benefits:**
- Single thread handles 1000+ concurrent connections
- No blocking on I/O operations (network, API calls)
- Efficient CPU utilization (70% target at peak load)

#### 2. Connection Pooling

```python
# Shared httpx client with connection pool
http_client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_keepalive_connections=100,
        max_connections=100,
        keepalive_expiry=30
    ),
    timeout=httpx.Timeout(10.0, connect=5.0)
)
```

**Benefits:**
- Reuse TCP connections to Cakemail API
- Reduce connection overhead (TLS handshake, DNS lookup)
- 100 concurrent API requests per pod

#### 3. Request Batching (Multi-Recipient Optimization)

For emails with multiple recipients:

```python
async def submit_email_batch(recipients, email_data, api_key):
    # Fire all API calls concurrently
    tasks = [
        api_client.submit_email(recipient, email_data, api_key)
        for recipient in recipients
    ]

    # Wait for all to complete (or fail)
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Aggregate results
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]

    return successes, failures
```

**Benefits:**
- 100-recipient email completes in same time as 1-recipient email
- Parallel API calls maximize throughput
- Early failure detection without blocking other recipients

#### 4. Memory Efficiency

```python
# Stream large attachments instead of loading into memory
async def parse_attachment(part):
    content = part.get_payload(decode=True)

    # If attachment > 1MB, stream to API
    if len(content) > 1_000_000:
        return stream_to_api_async(content)
    else:
        return base64.b64encode(content).decode()
```

**Memory Budget per Pod:**
- Base Python process: 100MB
- Per-connection overhead: 50KB (1000 connections = 50MB)
- Email parsing buffers: 100MB (worst case with large emails)
- Connection pool buffers: 50MB
- Total: ~300MB average, 512MB requested, 1GB limit

#### 5. CPU Optimization

**Profile Results (from load testing):**
- Email parsing: 20-30ms (90% of CPU time)
- JSON serialization: 5-10ms
- Logging/metrics: <5ms
- Network I/O: 0ms (async, non-blocking)

**Optimization Strategies:**
- Use `email.parser` (C-accelerated in CPython)
- Avoid unnecessary string copies (use views/buffers)
- Lazy MIME parsing (parse only accessed parts)
- Compile regex patterns at module load time

#### 6. Latency Targets

**P99 Processing Delay: <2s**

Breakdown:
```
SMTP Connection:        50ms   (TCP + TLS handshake)
AUTH Command:          200ms   (cache hit: 1ms, cache miss: 200ms)
MAIL FROM/RCPT TO:      10ms   (validation)
DATA Receipt:          100ms   (network transfer, depends on size)
Email Parsing:          50ms   (MIME + attachments)
API Submission:        500ms   (p95, includes retries)
SMTP Response:          10ms   (format + send)
----------------------------------------
Total:                 920ms   (p50 - typical case)
                      1800ms   (p99 - worst case with retries)
```

**P95 API Latency: <100ms**

Target for Cakemail API call (excluding retries):
- Connection from pool: <5ms
- API processing: <80ms
- Network round-trip: <15ms (within same region)

**Optimization Strategies:**
- Deploy gateway in same region as Cakemail API (minimize latency)
- Use connection pooling (eliminate handshake overhead)
- Cache auth responses (15-minute TTL)
- Set aggressive timeouts (fail fast on slow API)

### Load Testing Strategy

**Test Scenarios:**

1. **Steady State Test**
   - Load: 100,000 emails/hour (28 emails/second)
   - Duration: 1 hour
   - Validation: <1s p99, 0 errors

2. **Peak Load Test**
   - Load: 1,000,000 emails/hour (278 emails/second)
   - Duration: 30 minutes
   - Validation: <2s p99, <0.1% error rate

3. **Spike Test**
   - Load: 0 → 500 emails/second in 1 minute
   - Duration: 10 minutes
   - Validation: HPA scales up, <5s p99 during spike

4. **Soak Test**
   - Load: 250,000 emails/hour (steady)
   - Duration: 24 hours
   - Validation: No memory leaks, stable performance

5. **Multi-Recipient Test**
   - Load: 10,000 emails with 100 recipients each
   - Duration: 30 minutes
   - Validation: Parallel API calls, <3s p99

**Load Testing Tool:**

```python
# Locust SMTP load test
from locust import User, task, between
import smtplib
from email.mime.text import MIMEText

class SMTPUser(User):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.smtp = smtplib.SMTP('smtp.cakemail.com', 587)
        self.smtp.starttls()
        self.smtp.login('user@example.com', 'password')

    @task
    def send_email(self):
        msg = MIMEText('Test email body')
        msg['Subject'] = 'Load Test'
        msg['From'] = 'sender@example.com'
        msg['To'] = 'recipient@example.com'

        start_time = time.time()
        try:
            self.smtp.send_message(msg)
            response_time = (time.time() - start_time) * 1000
            self.environment.events.request.fire(
                request_type="SMTP",
                name="send_email",
                response_time=response_time,
                response_length=len(msg.as_string()),
                exception=None
            )
        except Exception as e:
            self.environment.events.request.fire(
                request_type="SMTP",
                name="send_email",
                response_time=(time.time() - start_time) * 1000,
                exception=e
            )

    def on_stop(self):
        self.smtp.quit()
```

---

## Security Architecture

### TLS/Certificate Management

**Certificate Strategy:**

```
┌─────────────────────────────────────────────────────────────┐
│                    Certificate Lifecycle                     │
│                                                               │
│  1. DNS Configuration                                        │
│     ─────────────────                                        │
│     smtp.cakemail.com → OVH Load Balancer IP                │
│                                                               │
│  2. cert-manager ClusterIssuer                              │
│     ─────────────────────────────                           │
│     apiVersion: cert-manager.io/v1                          │
│     kind: ClusterIssuer                                     │
│     metadata:                                                │
│       name: letsencrypt-prod                                │
│     spec:                                                    │
│       acme:                                                  │
│         server: https://acme-v02.api.letsencrypt.org/directory│
│         email: devops@cakemail.com                          │
│         privateKeySecretRef:                                │
│           name: letsencrypt-prod                            │
│         solvers:                                            │
│         - dns01:                                            │
│             ovh:                                            │
│               endpoint: ovh-eu                              │
│               applicationKey: <key>                         │
│               applicationSecret: <secret>                   │
│               consumerKey: <key>                            │
│                                                               │
│  3. Certificate Resource                                    │
│     ────────────────────                                    │
│     apiVersion: cert-manager.io/v1                          │
│     kind: Certificate                                       │
│     metadata:                                                │
│       name: smtp-gateway-tls                                │
│     spec:                                                    │
│       secretName: smtp-gateway-tls                          │
│       dnsNames:                                             │
│       - smtp.cakemail.com                                   │
│       issuerRef:                                            │
│         name: letsencrypt-prod                              │
│         kind: ClusterIssuer                                 │
│       duration: 2160h  # 90 days                           │
│       renewBefore: 720h  # 30 days before expiry           │
│                                                               │
│  4. Automatic Renewal                                       │
│     ──────────────────                                      │
│     cert-manager watches Certificate                        │
│     → 30 days before expiry, requests renewal               │
│     → Completes DNS-01 challenge                            │
│     → Updates Secret with new cert                          │
│     → Pods detect Secret change (inotify)                   │
│     → Reload TLS context without restart                    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

**TLS Configuration:**

```python
# SMTP server TLS configuration
import ssl

def create_tls_context():
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

    # Load certificate from K8s Secret mount
    context.load_cert_chain(
        certfile='/etc/smtp-gateway/tls/tls.crt',
        keyfile='/etc/smtp-gateway/tls/tls.key'
    )

    # Security hardening
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
    context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1

    return context

# Watch for certificate rotation
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class CertificateReloader(FileSystemEventHandler):
    def __init__(self, smtp_server):
        self.smtp_server = smtp_server

    def on_modified(self, event):
        if event.src_path.endswith('tls.crt') or event.src_path.endswith('tls.key'):
            logger.info("Certificate changed, reloading TLS context")
            self.smtp_server.tls_context = create_tls_context()
```

**Security Controls:**
- TLS 1.2+ only (1.0/1.1 disabled)
- Strong cipher suites (ECDHE, AES-GCM, ChaCha20)
- Certificate pinning not used (allows rotation)
- STARTTLS mandatory (no plaintext allowed)
- AUTH commands rejected before STARTTLS

### Authentication Flow

```
┌────────────┐                                    ┌──────────────┐
│   Client   │                                    │   Gateway    │
└─────┬──────┘                                    └──────┬───────┘
      │                                                   │
      │  1. TCP Connect + TLS Handshake                  │
      ├──────────────────────────────────────────────────>
      │                                                   │
      │  2. EHLO                                          │
      ├──────────────────────────────────────────────────>
      │  ← 250-smtp.cakemail.com                          │
      │  ← 250-AUTH PLAIN LOGIN                           │
      │  ← 250 STARTTLS                                   │
      <───────────────────────────────────────────────────┤
      │                                                   │
      │  3. AUTH LOGIN                                    │
      ├──────────────────────────────────────────────────>
      │                                                   │
      │                              ┌────────────────────┤
      │                              │ Check cache:       │
      │                              │ cache_key =        │
      │                              │   hash(user+pass)  │
      │                              └────────┬───────────┤
      │                                       │           │
      │                              ┌────────▼───────────┤
      │                              │ Cache Hit?         │
      │                              └────────┬───────────┤
      │                                       │           │
      │                              YES      │      NO   │
      │                              ┌────────▼───────────┤
      │                              │ Return cached      │
      │                              │ API key            │
      │                              │ (TTL: 15 min)      │
      │                              └────────┬───────────┤
      │                                       │           │
      │                                       │           │
      │                              ┌────────▼───────────┤
      │                              │ Call Cakemail API: │
      │                              │ POST /auth/validate│
      │                              │ {user, pass}       │
      │                              └────────┬───────────┤
      │                                       │           │
      │                         ┌─────────────▼────────────┐
      │                         │   Cakemail Auth API      │
      │                         │                          │
      │                         │  - Validate credentials  │
      │                         │  - Return API key        │
      │                         │  - Or 401 Unauthorized   │
      │                         └─────────────┬────────────┘
      │                                       │
      │                              ┌────────▼───────────┤
      │                              │ Cache result       │
      │                              │ (success or fail)  │
      │                              └────────┬───────────┤
      │                                       │           │
      │  ← 235 Authentication successful                  │
      │     (or 535 Authentication failed)                │
      <───────────────────────────────────────────────────┤
      │                                                   │
      │  4. MAIL FROM / RCPT TO / DATA                    │
      │     (API key used for all subsequent API calls)   │
      ├──────────────────────────────────────────────────>
      │                                                   │
```

**Credential Caching Strategy:**

```python
import hashlib
import time
from typing import Optional

class AuthCache:
    def __init__(self, ttl_seconds=900):  # 15 minutes
        self.cache = {}
        self.ttl = ttl_seconds

    def _cache_key(self, username: str, password: str) -> str:
        # Hash credentials to avoid storing plaintext
        combined = f"{username}:{password}"
        return hashlib.sha256(combined.encode()).hexdigest()

    async def get_api_key(self, username: str, password: str) -> Optional[str]:
        key = self._cache_key(username, password)
        entry = self.cache.get(key)

        if entry is None:
            return None

        # Check TTL
        if time.time() - entry['timestamp'] > self.ttl:
            del self.cache[key]
            return None

        return entry['api_key']

    async def set_api_key(self, username: str, password: str, api_key: str):
        key = self._cache_key(username, password)
        self.cache[key] = {
            'api_key': api_key,
            'timestamp': time.time()
        }

    async def invalidate(self, username: str, password: str):
        key = self._cache_key(username, password)
        self.cache.pop(key, None)

    async def clear_expired(self):
        # Background task to clear expired entries
        now = time.time()
        expired = [
            k for k, v in self.cache.items()
            if now - v['timestamp'] > self.ttl
        ]
        for k in expired:
            del self.cache[k]
```

**Security Considerations:**
- Credentials hashed in cache (SHA-256)
- Cache cleared on pod restart (no persistence)
- 15-minute TTL balances performance vs. security
- Failed auth attempts not cached (prevent timing attacks)
- Rate limiting on auth failures (prevent brute force)

### Network Security

**Kubernetes NetworkPolicy:**

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: smtp-gateway-network-policy
spec:
  podSelector:
    matchLabels:
      app: smtp-gateway
  policyTypes:
  - Ingress
  - Egress

  ingress:
  # Allow SMTP from anywhere (public service)
  - from:
    - namespaceSelector: {}
    - podSelector: {}
    ports:
    - protocol: TCP
      port: 587

  # Allow metrics scraping from Prometheus
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
    - podSelector:
        matchLabels:
          app: prometheus
    ports:
    - protocol: TCP
      port: 8080

  egress:
  # Allow DNS resolution
  - to:
    - namespaceSelector: {}
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53

  # Allow HTTPS to Cakemail API
  - to:
    - podSelector:
        matchLabels:
          app: cakemail-api
    ports:
    - protocol: TCP
      port: 443

  # Allow HTTPS to external APIs (cert-manager, etc.)
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 443
```

**DDoS Protection:**

```python
# Connection throttling per IP
class ConnectionThrottler:
    def __init__(self):
        self.connections_per_ip = {}
        self.max_connections_per_ip = 10
        self.max_emails_per_minute_per_ip = 100
        self.failed_auth_attempts = {}
        self.blacklist = set()
        self.whitelist = set()  # Load from ConfigMap

    async def check_connection(self, client_ip: str) -> bool:
        # Whitelist bypass
        if client_ip in self.whitelist:
            return True

        # Blacklist check
        if client_ip in self.blacklist:
            return False

        # Connection limit
        current = self.connections_per_ip.get(client_ip, 0)
        if current >= self.max_connections_per_ip:
            logger.warning(f"Connection limit exceeded for {client_ip}")
            return False

        self.connections_per_ip[client_ip] = current + 1
        return True

    async def check_auth_failure(self, client_ip: str) -> bool:
        # Track failed auth attempts
        attempts = self.failed_auth_attempts.get(client_ip, {'count': 0, 'timestamp': time.time()})

        # Reset counter after 5 minutes
        if time.time() - attempts['timestamp'] > 300:
            attempts = {'count': 0, 'timestamp': time.time()}

        # Block after 5 failures
        if attempts['count'] >= 5:
            self.blacklist.add(client_ip)
            logger.warning(f"Blacklisted {client_ip} after 5 failed auth attempts")
            return False

        attempts['count'] += 1
        self.failed_auth_attempts[client_ip] = attempts
        return True

    async def release_connection(self, client_ip: str):
        if client_ip in self.connections_per_ip:
            self.connections_per_ip[client_ip] -= 1
```

**Input Validation:**

```python
# Validate all SMTP commands and email content
import re

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
DOMAIN_REGEX = re.compile(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def validate_email_address(email: str) -> bool:
    if len(email) > 254:  # RFC 5321 limit
        return False
    return EMAIL_REGEX.match(email) is not None

def validate_command(command: str) -> bool:
    # Only allow expected SMTP commands
    allowed = {'EHLO', 'HELO', 'STARTTLS', 'AUTH', 'MAIL', 'RCPT', 'DATA', 'QUIT', 'RSET', 'NOOP'}
    cmd = command.split()[0].upper()
    return cmd in allowed

def validate_header_name(name: str) -> bool:
    # RFC 5322 field names
    return re.match(r'^[!-9;-~]+$', name) is not None

def validate_message_size(size: int) -> bool:
    MAX_MESSAGE_SIZE = 25 * 1024 * 1024  # 25MB
    return size <= MAX_MESSAGE_SIZE
```

---

## Observability Design

### Logging Strategy (structlog)

**Log Format:**

```json
{
  "timestamp": "2025-10-02T14:23:45.123456Z",
  "level": "info",
  "logger": "smtp_gateway.smtp_server",
  "event": "email_received",
  "correlation_id": "req_abc123def456",
  "session_id": "sess_789ghi012jkl",
  "client_ip": "192.168.1.100",
  "authenticated_user": "user@example.com",
  "from_address": "sender@example.com",
  "recipient_count": 3,
  "message_size_bytes": 12345,
  "has_attachments": true,
  "attachment_count": 2,
  "processing_time_ms": 145,
  "api_calls": 3,
  "api_latency_ms": 89,
  "result": "success",
  "message_id": "msg_xyz789"
}
```

**Implementation:**

```python
import structlog
import uuid

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# SMTP handler with correlation ID
class SMTPHandler:
    async def handle_MAIL(self, server, session, envelope, address):
        # Generate correlation ID for entire session
        if not hasattr(session, 'correlation_id'):
            session.correlation_id = f"req_{uuid.uuid4().hex[:16]}"

        log = logger.bind(
            correlation_id=session.correlation_id,
            session_id=session.session_id,
            client_ip=session.peer[0],
            command="MAIL_FROM",
            from_address=address
        )

        log.info("mail_from_received")

        # ... handle command ...

        log.info("mail_from_accepted", processing_time_ms=elapsed)
        return '250 OK'

# API client logging
class APIClient:
    async def submit_email(self, email_data, api_key, correlation_id):
        log = logger.bind(
            correlation_id=correlation_id,
            operation="api_submit_email",
            recipient=email_data['to'],
            api_endpoint="/v1/emails"
        )

        log.info("api_request_start")
        start = time.time()

        try:
            response = await self.http_client.post(
                '/v1/emails',
                json=email_data,
                headers={'Authorization': f'Bearer {api_key}'}
            )

            latency = (time.time() - start) * 1000

            log.info(
                "api_request_complete",
                status_code=response.status_code,
                latency_ms=latency,
                message_id=response.json().get('message_id')
            )

            return response

        except Exception as e:
            latency = (time.time() - start) * 1000
            log.error(
                "api_request_failed",
                error=str(e),
                error_type=type(e).__name__,
                latency_ms=latency
            )
            raise
```

**Log Levels:**
- **DEBUG**: Detailed internal state (development only)
- **INFO**: Normal operations (connection, email received, API call)
- **WARNING**: Recoverable errors (rate limit, temporary failure)
- **ERROR**: Unexpected errors (API failure, parsing error)
- **CRITICAL**: Service degradation (circuit breaker open, out of memory)

**Sensitive Data Redaction:**

```python
# Redact sensitive fields
import re

def redact_sensitive(data: dict) -> dict:
    redacted = data.copy()

    # Redact password
    if 'password' in redacted:
        redacted['password'] = '***REDACTED***'

    # Redact API key (show first/last 4 chars)
    if 'api_key' in redacted and len(redacted['api_key']) > 8:
        key = redacted['api_key']
        redacted['api_key'] = f"{key[:4]}...{key[-4:]}"

    # Redact email content (log metadata only)
    if 'email_body' in redacted:
        redacted['email_body'] = f"<{len(redacted['email_body'])} bytes>"

    # Redact attachment content
    if 'attachments' in redacted:
        redacted['attachments'] = [
            {
                'filename': a['filename'],
                'size': len(a.get('content', '')),
                'content_type': a.get('content_type')
            }
            for a in redacted['attachments']
        ]

    return redacted
```

### Metrics Architecture (Prometheus)

**Metric Definitions:**

```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest

# Counters (monotonic increase)
smtp_connections_total = Counter(
    'smtp_connections_total',
    'Total SMTP connections',
    ['status']  # 'accepted', 'rejected', 'error'
)

smtp_emails_received_total = Counter(
    'smtp_emails_received_total',
    'Total emails received via SMTP',
    ['authenticated_user']
)

smtp_emails_forwarded_total = Counter(
    'smtp_emails_forwarded_total',
    'Total emails forwarded to Cakemail API',
    ['result']  # 'success', 'failure'
)

smtp_auth_failures_total = Counter(
    'smtp_auth_failures_total',
    'Total authentication failures',
    ['client_ip']
)

smtp_api_errors_total = Counter(
    'smtp_api_errors_total',
    'Total Cakemail API errors',
    ['error_type', 'status_code']
)

# Histograms (latency distributions)
smtp_processing_duration_seconds = Histogram(
    'smtp_processing_duration_seconds',
    'End-to-end SMTP processing time',
    ['command'],  # 'MAIL_FROM', 'RCPT_TO', 'DATA'
    buckets=[.01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10]
)

smtp_api_latency_seconds = Histogram(
    'smtp_api_latency_seconds',
    'Cakemail API call latency',
    ['endpoint', 'status_code'],
    buckets=[.01, .025, .05, .075, .1, .25, .5, 1, 2.5]
)

smtp_email_size_bytes = Histogram(
    'smtp_email_size_bytes',
    'Email message size distribution',
    buckets=[1024, 10240, 102400, 1048576, 10485760, 26214400]
)

smtp_connection_duration_seconds = Histogram(
    'smtp_connection_duration_seconds',
    'SMTP connection lifetime',
    buckets=[1, 5, 10, 30, 60, 300, 600]
)

# Gauges (current values)
smtp_active_connections = Gauge(
    'smtp_active_connections',
    'Current active SMTP connections'
)

smtp_api_key_cache_size = Gauge(
    'smtp_api_key_cache_size',
    'Number of cached API keys'
)

smtp_circuit_breaker_state = Gauge(
    'smtp_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)'
)

# Usage in code
class SMTPHandler:
    async def handle_DATA(self, server, session, envelope):
        smtp_active_connections.inc()

        with smtp_processing_duration_seconds.labels(command='DATA').time():
            try:
                # Parse email
                email_data = await parse_email(envelope.content)
                smtp_email_size_bytes.observe(len(envelope.content))

                # Submit to API
                with smtp_api_latency_seconds.labels(
                    endpoint='/v1/emails',
                    status_code='200'
                ).time():
                    result = await api_client.submit_email(email_data)

                smtp_emails_received_total.labels(
                    authenticated_user=session.username
                ).inc()

                smtp_emails_forwarded_total.labels(result='success').inc()

                return '250 OK'

            except APIError as e:
                smtp_api_errors_total.labels(
                    error_type=type(e).__name__,
                    status_code=e.status_code
                ).inc()
                smtp_emails_forwarded_total.labels(result='failure').inc()
                return '451 Temporary failure'

            finally:
                smtp_active_connections.dec()
```

**Metrics Endpoint:**

```python
from fastapi import FastAPI
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

app = FastAPI()

@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@app.get("/health/live")
async def liveness():
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness():
    # Check SMTP server is running
    if not smtp_server.is_running:
        return {"status": "not ready"}, 503

    # Check API reachability
    try:
        await api_client.health_check()
    except:
        return {"status": "not ready", "reason": "API unreachable"}, 503

    return {"status": "ready"}
```

**Grafana Dashboard (key panels):**

```
┌─────────────────────────────────────────────────────────────────┐
│                 Cakemail SMTP Gateway Dashboard                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐│
│  │ Emails/Hour      │  │ Active Pods      │  │ Error Rate     ││
│  │                  │  │                  │  │                ││
│  │  278,543         │  │       8          │  │    0.02%       ││
│  │  ▲ 12% vs 1h ago │  │  ▲ 2 vs 1h ago   │  │  ▼ 50% vs 1h  ││
│  └──────────────────┘  └──────────────────┘  └────────────────┘│
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Email Processing Latency (p50, p95, p99)                  │  │
│  │                                                             │  │
│  │  2s ┤                                              ╭─╮     │  │
│  │     │                                          ╭───╯ ╰─╮   │  │
│  │  1s ┤                              ╭───────────╯       ╰─  │  │
│  │     │                  ╭───────────╯                       │  │
│  │ 0.5s┤      ╭───────────╯                                   │  │
│  │     │  ╭───╯                                               │  │
│  │  0s └──┴───────────────────────────────────────────────── │  │
│  │      00:00  04:00  08:00  12:00  16:00  20:00  24:00      │  │
│  │      ─── p50   ─── p95   ─── p99                          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌────────────────────────────┐  ┌──────────────────────────┐  │
│  │ Active Connections         │  │ API Call Success Rate    │  │
│  │                            │  │                          │  │
│  │ 1500┤            ╭─╮       │  │100%┤─────────────────────│  │
│  │ 1000┤        ╭───╯ ╰─╮     │  │ 99%┤                     │  │
│  │  500┤    ╭───╯       ╰─╮   │  │ 98%┤                     │  │
│  │    0└────┴──────────────   │  │ 97%┤                     │  │
│  │      00:00      12:00      │  │    └──────────────────── │  │
│  └────────────────────────────┘  └──────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Top Errors (last 1 hour)                                  │  │
│  │                                                             │  │
│  │  1. API timeout (429 Too Many Requests)     23 occurrences│  │
│  │  2. Invalid email format (550)              8 occurrences │  │
│  │  3. Auth failure (535)                      5 occurrences │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Queries:**

```promql
# Email throughput (emails/hour)
rate(smtp_emails_received_total[1h]) * 3600

# P99 processing latency
histogram_quantile(0.99, rate(smtp_processing_duration_seconds_bucket[5m]))

# Error rate
sum(rate(smtp_emails_forwarded_total{result="failure"}[5m])) /
sum(rate(smtp_emails_forwarded_total[5m])) * 100

# Saturation: CPU usage per pod
rate(process_cpu_seconds_total[5m]) * 100

# API latency p95
histogram_quantile(0.95, rate(smtp_api_latency_seconds_bucket[5m]))
```

### Distributed Tracing (Future Enhancement)

**OpenTelemetry Integration:**

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure tracer
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(endpoint="http://jaeger:4317")
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# SMTP handler with tracing
class SMTPHandler:
    async def handle_DATA(self, server, session, envelope):
        with tracer.start_as_current_span("smtp.handle_data") as span:
            span.set_attribute("client.ip", session.peer[0])
            span.set_attribute("email.size", len(envelope.content))
            span.set_attribute("email.recipients", len(envelope.rcpt_tos))

            # Parse email (sub-span)
            with tracer.start_as_current_span("email.parse"):
                email_data = await parse_email(envelope.content)

            # Submit to API (sub-span)
            with tracer.start_as_current_span("api.submit_email") as api_span:
                api_span.set_attribute("api.endpoint", "/v1/emails")
                result = await api_client.submit_email(email_data)
                api_span.set_attribute("api.message_id", result.message_id)

            span.set_attribute("result", "success")
            return '250 OK'
```

**Note:** Distributed tracing is **not required for MVP** but recommended for post-MVP observability enhancements.

---

## API Integration

### Cakemail Email API Specification

**Assumption:** Cakemail provides two API endpoints:

1. **Authentication Endpoint**: `POST /v1/auth/validate`
2. **Email Submission Endpoint**: `POST /v1/emails`

### Authentication API

**Request:**

```http
POST /v1/auth/validate HTTP/1.1
Host: api.cakemail.com
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "smtp_password"
}
```

**Response (Success):**

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "api_key": "cm_live_abc123def456ghi789jkl012",
  "account_id": "acc_xyz789",
  "email": "user@example.com",
  "expires_in": 900
}
```

**Response (Failure):**

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "error": "invalid_credentials",
  "message": "Invalid username or password"
}
```

**Implementation:**

```python
import httpx
from typing import Optional

class CakemailAuthClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=2.0),
            limits=httpx.Limits(max_connections=50)
        )

    async def validate_credentials(
        self,
        username: str,
        password: str
    ) -> Optional[str]:
        """
        Validate SMTP credentials and return API key.

        Returns:
            API key if valid, None if invalid

        Raises:
            httpx.TimeoutException: If API timeout
            httpx.HTTPError: If API error
        """
        try:
            response = await self.http_client.post(
                f'{self.base_url}/v1/auth/validate',
                json={'username': username, 'password': password},
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 200:
                data = response.json()
                return data['api_key']
            elif response.status_code == 401:
                return None
            else:
                response.raise_for_status()

        except httpx.TimeoutException:
            logger.error("Auth API timeout", username=username)
            raise
        except httpx.HTTPError as e:
            logger.error("Auth API error", error=str(e), username=username)
            raise
```

### Email Submission API

**Request:**

```http
POST /v1/emails HTTP/1.1
Host: api.cakemail.com
Content-Type: application/json
Authorization: Bearer cm_live_abc123def456ghi789jkl012

{
  "from": {
    "email": "sender@example.com",
    "name": "John Doe"
  },
  "to": [
    {
      "email": "recipient@example.com",
      "name": "Jane Smith"
    }
  ],
  "cc": [
    {
      "email": "cc@example.com",
      "name": "CC User"
    }
  ],
  "bcc": [
    {
      "email": "bcc@example.com"
    }
  ],
  "subject": "Test Email",
  "text_body": "This is the plain text body.",
  "html_body": "<html><body><h1>This is the HTML body.</h1></body></html>",
  "reply_to": {
    "email": "reply@example.com",
    "name": "Reply Handler"
  },
  "headers": {
    "X-Custom-Header": "custom-value",
    "X-Campaign-ID": "campaign_123"
  },
  "attachments": [
    {
      "filename": "document.pdf",
      "content": "base64_encoded_content_here...",
      "content_type": "application/pdf"
    }
  ]
}
```

**Response (Success):**

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "message_id": "msg_abc123def456",
  "status": "queued",
  "recipient": "recipient@example.com"
}
```

**Response (Validation Error):**

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": "validation_error",
  "message": "Invalid email format",
  "field": "to.email"
}
```

**Response (Rate Limited):**

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 60

{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded, retry after 60 seconds",
  "retry_after": 60
}
```

**Implementation:**

```python
from typing import Dict, List
import base64

class CakemailEmailClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(
                max_keepalive_connections=100,
                max_connections=100
            )
        )

    async def submit_email(
        self,
        email_data: Dict,
        api_key: str
    ) -> Dict:
        """
        Submit email to Cakemail API.

        Args:
            email_data: Parsed email data in Cakemail format
            api_key: Authenticated API key

        Returns:
            API response with message_id

        Raises:
            EmailValidationError: 400 validation error
            RateLimitError: 429 rate limit
            APIError: Other API errors
        """
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        try:
            response = await self.http_client.post(
                f'{self.base_url}/v1/emails',
                json=email_data,
                headers=headers
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 400:
                error = response.json()
                raise EmailValidationError(error['message'], error.get('field'))
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                raise RateLimitError(retry_after)
            elif response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            elif response.status_code >= 500:
                raise APIError(f"API server error: {response.status_code}")
            else:
                response.raise_for_status()

        except httpx.TimeoutException:
            logger.error("Email API timeout", recipient=email_data['to'])
            raise APIError("API timeout")
        except httpx.HTTPError as e:
            logger.error("Email API error", error=str(e))
            raise APIError(str(e))

def transform_smtp_to_api_format(email_message, recipients) -> Dict:
    """
    Transform Python email.message.EmailMessage to Cakemail API format.
    """
    # Extract headers
    from_addr = email_message['From']
    from_name, from_email = parse_email_header(from_addr)

    subject = email_message['Subject'] or ''
    reply_to = email_message.get('Reply-To')

    # Parse recipients
    to_list = [parse_email_header(r) for r in recipients.get('to', [])]
    cc_list = [parse_email_header(r) for r in recipients.get('cc', [])]
    bcc_list = [parse_email_header(r) for r in recipients.get('bcc', [])]

    # Extract body
    text_body = None
    html_body = None
    attachments = []

    if email_message.is_multipart():
        for part in email_message.walk():
            content_type = part.get_content_type()
            content_disposition = part.get('Content-Disposition')

            if content_type == 'text/plain' and not content_disposition:
                text_body = part.get_content()
            elif content_type == 'text/html' and not content_disposition:
                html_body = part.get_content()
            elif content_disposition and 'attachment' in content_disposition:
                # Attachment
                filename = part.get_filename()
                content = part.get_payload(decode=True)
                attachments.append({
                    'filename': filename,
                    'content': base64.b64encode(content).decode(),
                    'content_type': content_type
                })
    else:
        # Single part message
        content_type = email_message.get_content_type()
        if content_type == 'text/plain':
            text_body = email_message.get_content()
        elif content_type == 'text/html':
            html_body = email_message.get_content()

    # Build API request
    api_data = {
        'from': {
            'email': from_email,
            'name': from_name
        },
        'subject': subject,
        'to': [{'email': e, 'name': n} for n, e in to_list],
    }

    if cc_list:
        api_data['cc'] = [{'email': e, 'name': n} for n, e in cc_list]
    if bcc_list:
        api_data['bcc'] = [{'email': e, 'name': n} for n, e in bcc_list]

    if text_body:
        api_data['text_body'] = text_body
    if html_body:
        api_data['html_body'] = html_body

    if reply_to:
        reply_name, reply_email = parse_email_header(reply_to)
        api_data['reply_to'] = {'email': reply_email, 'name': reply_name}

    if attachments:
        api_data['attachments'] = attachments

    # Custom headers
    custom_headers = {}
    for key in email_message.keys():
        if key.startswith('X-'):
            custom_headers[key] = email_message[key]
    if custom_headers:
        api_data['headers'] = custom_headers

    return api_data
```

### Error Handling & Retry Strategy

**Error Classification:**

```python
class ErrorHandler:
    def __init__(self):
        self.retry_config = {
            'max_retries': 2,
            'backoff_factor': 2,
            'retriable_status_codes': {500, 502, 503, 504},
            'retriable_exceptions': (httpx.TimeoutException, httpx.NetworkError)
        }

    def is_retriable(self, error: Exception) -> bool:
        """Determine if error should be retried."""
        if isinstance(error, APIError) and error.status_code in self.retry_config['retriable_status_codes']:
            return True
        if isinstance(error, self.retry_config['retriable_exceptions']):
            return True
        return False

    def get_smtp_error_code(self, error: Exception) -> str:
        """Map exception to SMTP error code."""
        if isinstance(error, EmailValidationError):
            return '550 Message rejected: ' + error.message
        elif isinstance(error, RateLimitError):
            return f'451 Rate limit exceeded, retry after {error.retry_after}s'
        elif isinstance(error, AuthenticationError):
            return '535 Authentication failed'
        elif isinstance(error, APIError):
            if self.is_retriable(error):
                return '451 Temporary failure, try again later'
            else:
                return '554 Transaction failed: ' + str(error)
        else:
            return '451 Service temporarily unavailable'

async def submit_email_with_retry(
    email_data: Dict,
    api_key: str,
    max_retries: int = 2
) -> Dict:
    """Submit email with exponential backoff retry."""
    error_handler = ErrorHandler()

    for attempt in range(max_retries + 1):
        try:
            return await api_client.submit_email(email_data, api_key)

        except Exception as e:
            if attempt == max_retries or not error_handler.is_retriable(e):
                # Final attempt or non-retriable error
                raise

            # Exponential backoff
            delay = (2 ** attempt) * 1  # 1s, 2s, 4s
            logger.warning(
                "API call failed, retrying",
                attempt=attempt + 1,
                delay=delay,
                error=str(e)
            )
            await asyncio.sleep(delay)
```

### Circuit Breaker Pattern

```python
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = 0      # Normal operation
    OPEN = 1        # Failure threshold exceeded, reject requests
    HALF_OPEN = 2   # Test if service recovered

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: float = 0.5,  # 50% error rate
        recovery_timeout: int = 300,      # 5 minutes
        request_threshold: int = 10       # Minimum requests before tripping
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.request_threshold = request_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.opened_at = None

    def record_success(self):
        """Record successful request."""
        self.success_count += 1

        # If in HALF_OPEN state and success, close circuit
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker: recovered, closing circuit")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.opened_at = None

    def record_failure(self):
        """Record failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        # Check if should open circuit
        total_requests = self.success_count + self.failure_count

        if total_requests >= self.request_threshold:
            error_rate = self.failure_count / total_requests

            if error_rate >= self.failure_threshold:
                if self.state == CircuitState.CLOSED:
                    logger.error(
                        "Circuit breaker: failure threshold exceeded, opening circuit",
                        error_rate=error_rate,
                        failure_count=self.failure_count,
                        total_requests=total_requests
                    )
                    self.state = CircuitState.OPEN
                    self.opened_at = time.time()

                    # Update metric
                    smtp_circuit_breaker_state.set(1)

    def can_proceed(self) -> bool:
        """Check if request should proceed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            if time.time() - self.opened_at >= self.recovery_timeout:
                logger.info("Circuit breaker: recovery timeout elapsed, entering half-open state")
                self.state = CircuitState.HALF_OPEN
                self.failure_count = 0
                self.success_count = 0
                smtp_circuit_breaker_state.set(2)
                return True
            else:
                return False

        if self.state == CircuitState.HALF_OPEN:
            # Allow limited requests through
            return True

        return False

    def reset(self):
        """Manually reset circuit breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.opened_at = None
        smtp_circuit_breaker_state.set(0)

# Usage
circuit_breaker = CircuitBreaker()

async def submit_email_protected(email_data, api_key):
    """Submit email with circuit breaker protection."""
    if not circuit_breaker.can_proceed():
        logger.warning("Circuit breaker open, rejecting request")
        raise CircuitBreakerOpenError("Service temporarily unavailable")

    try:
        result = await api_client.submit_email(email_data, api_key)
        circuit_breaker.record_success()
        return result

    except Exception as e:
        circuit_breaker.record_failure()
        raise
```

---

## Scalability & Reliability

### Horizontal Scaling Strategy

**Scaling Dimensions:**

1. **CPU-based scaling** (primary)
   - Target: 70% CPU utilization
   - Scale up when average CPU > 70% for 2 minutes
   - Scale down when average CPU < 40% for 5 minutes

2. **Memory-based scaling** (secondary)
   - Target: 75% memory utilization
   - Prevent OOM kills

3. **Custom metric scaling** (tertiary)
   - Target: 50 emails/second per pod
   - Formula: `rate(smtp_emails_received_total[1m]) / count(up{job="smtp-gateway"})`

**HPA Configuration:**

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: smtp-gateway-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: smtp-gateway
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 75
  - type: Pods
    pods:
      metric:
        name: smtp_emails_per_second
      target:
        type: AverageValue
        averageValue: "50"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Pods
        value: 4
        periodSeconds: 60
      - type: Percent
        value: 50
        periodSeconds: 60
      selectPolicy: Max
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Pods
        value: 1
        periodSeconds: 300
      selectPolicy: Min
```

**Capacity Planning:**

| Load | Emails/Hour | Emails/Second | Required Pods | Actual Pods (30% buffer) |
|------|-------------|---------------|---------------|--------------------------|
| Low | 100K | 28 | 1 | 2 (HA minimum) |
| Medium | 500K | 139 | 2 | 3 |
| High | 1M | 278 | 3 | 4 |
| Peak | 2M | 556 | 6 | 8 |
| Max | 5M | 1389 | 14 | 18 (under max limit) |

**Scaling Behaviors:**

- **Scale up aggressively**: Add 4 pods/minute or 50% of current pods (whichever is higher)
- **Scale down conservatively**: Remove 1 pod every 5 minutes
- **Stabilization window**: Wait 60s before scaling up, 300s before scaling down

### Failure Modes & Mitigation

| Failure Mode | Impact | Mitigation | Recovery Time |
|--------------|--------|------------|---------------|
| **Single pod crash** | 1/N capacity loss | HPA replaces pod automatically | 30-60s |
| **Node failure** | Lose all pods on node | Kubernetes reschedules to healthy nodes | 1-2 min |
| **Zone failure** | Lose all pods in zone | Multi-zone deployment maintains service | 0s (instant) |
| **Cakemail API down** | Cannot forward emails | Circuit breaker opens, return 451 to clients | 5 min (auto-recovery) |
| **Cakemail API slow** | Increased latency | Timeouts + circuit breaker prevent cascading | 1-2 min |
| **Certificate expired** | TLS handshake fails | cert-manager auto-renews 30 days before expiry | 0s (prevented) |
| **Memory leak** | Pod OOM kill | Kubernetes restarts pod, limit blast radius | 30s |
| **Network partition** | Cannot reach API | Circuit breaker + retry logic | Depends on partition duration |
| **DDoS attack** | Resource exhaustion | Rate limiting + connection throttling | Ongoing (active defense) |
| **Load balancer failure** | Service unreachable | OVH handles LB redundancy | <1 min (OVH SLA) |

**Disaster Recovery:**

1. **Cluster-level failure (unlikely but possible):**
   - All data is transient (no data loss)
   - Redeploy to new cluster from Helm chart
   - Update DNS to new cluster
   - Recovery time: 10-15 minutes

2. **Data center failure:**
   - Multi-region deployment (post-MVP)
   - GeoDNS failover to secondary region
   - Recovery time: <1 minute (automatic)

### Stateless Design Benefits

The gateway's stateless architecture provides:

1. **Instant Scaling**
   - New pods ready in 30-60s
   - No state replication or migration
   - Load balancer automatically includes new pods

2. **Rolling Updates**
   - Deploy new version pod-by-pod
   - Old pods drain connections gracefully
   - Zero downtime deployments

3. **Failure Isolation**
   - Pod crash only affects in-flight requests
   - No shared state corruption
   - Independent failure domains

4. **Simplified Operations**
   - No backup/restore procedures
   - No state synchronization
   - No data migration during upgrades

5. **Geographic Distribution**
   - Can deploy in multiple regions without replication
   - Each region operates independently
   - No cross-region data consistency concerns

**Trade-offs:**

- **Credential cache lost on pod restart**: Acceptable, credentials re-validated on next connection (200ms latency once per 15 min)
- **No request queuing**: Clients must retry on 451 errors (standard SMTP behavior)
- **No email history**: All tracking delegated to Cakemail API (reduces gateway complexity)

---

## Code Structure

### Repository Layout

```
smtp-gateway/
├── .github/
│   └── workflows/
│       ├── ci.yml              # CI pipeline (lint, test, build)
│       └── cd.yml              # CD pipeline (deploy to K8s)
│
├── deployment/
│   ├── helm/
│   │   └── smtp-gateway/
│   │       ├── Chart.yaml
│   │       ├── values.yaml     # Default values
│   │       ├── values-prod.yaml
│   │       ├── values-staging.yaml
│   │       └── templates/
│   │           ├── deployment.yaml
│   │           ├── service.yaml
│   │           ├── hpa.yaml
│   │           ├── configmap.yaml
│   │           ├── secret.yaml
│   │           ├── networkpolicy.yaml
│   │           ├── poddisruptionbudget.yaml
│   │           └── servicemonitor.yaml
│   │
│   ├── cert-manager/
│   │   ├── clusterissuer-letsencrypt-staging.yaml
│   │   ├── clusterissuer-letsencrypt-prod.yaml
│   │   └── certificate.yaml
│   │
│   └── docker/
│       └── Dockerfile
│
├── docs/
│   ├── architecture.md         # This document
│   ├── prd.md
│   ├── brief.md
│   ├── api-integration.md      # Cakemail API integration guide
│   ├── deployment-guide.md
│   ├── monitoring-guide.md
│   └── troubleshooting.md
│
├── src/
│   └── smtp_gateway/
│       ├── __init__.py
│       ├── __main__.py         # Entry point
│       │
│       ├── config.py           # Configuration management
│       ├── logging.py          # Structured logging setup
│       ├── metrics.py          # Prometheus metrics definitions
│       │
│       ├── smtp/
│       │   ├── __init__.py
│       │   ├── server.py       # SMTP server setup
│       │   ├── handler.py      # SMTP command handlers
│       │   ├── auth.py         # Authentication logic
│       │   ├── session.py      # Session state management
│       │   └── throttler.py    # Rate limiting & throttling
│       │
│       ├── email/
│       │   ├── __init__.py
│       │   ├── parser.py       # Email parsing (MIME, headers)
│       │   ├── validator.py    # Email validation
│       │   └── transformer.py  # SMTP → API format transformation
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── client.py       # Cakemail API client
│       │   ├── auth.py         # Auth API integration
│       │   ├── email.py        # Email API integration
│       │   ├── errors.py       # API error classes
│       │   ├── retry.py        # Retry logic
│       │   └── circuit_breaker.py
│       │
│       ├── http/
│       │   ├── __init__.py
│       │   ├── server.py       # FastAPI HTTP server
│       │   ├── health.py       # Health check endpoints
│       │   └── metrics.py      # Metrics endpoint
│       │
│       └── utils/
│           ├── __init__.py
│           ├── tls.py          # TLS context management
│           ├── cache.py        # In-memory caching
│           └── helpers.py      # Utility functions
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   │
│   ├── unit/
│   │   ├── test_email_parser.py
│   │   ├── test_email_transformer.py
│   │   ├── test_auth.py
│   │   ├── test_throttler.py
│   │   ├── test_circuit_breaker.py
│   │   └── test_retry.py
│   │
│   ├── integration/
│   │   ├── test_smtp_flow.py
│   │   ├── test_api_integration.py
│   │   ├── test_auth_flow.py
│   │   └── test_tls.py
│   │
│   └── load/
│       ├── locustfile.py
│       └── README.md
│
├── scripts/
│   ├── setup-dev.sh            # Local dev environment setup
│   ├── run-local.sh            # Run gateway locally
│   ├── generate-cert.sh        # Generate self-signed cert for dev
│   └── deploy.sh               # Deploy to K8s cluster
│
├── .gitignore
├── .pre-commit-config.yaml     # Pre-commit hooks
├── pyproject.toml              # Python project config
├── poetry.lock / requirements.txt
└── README.md
```

### Key Modules

#### smtp_gateway/__main__.py

```python
"""
SMTP Gateway entry point.
"""
import asyncio
import signal
import sys
from smtp_gateway.config import Config
from smtp_gateway.logging import setup_logging
from smtp_gateway.smtp.server import SMTPServer
from smtp_gateway.http.server import HTTPServer
from smtp_gateway.api.client import CakemailAPIClient

logger = setup_logging()

async def shutdown(signal, loop, smtp_server, http_server):
    """Graceful shutdown handler."""
    logger.info("shutdown_initiated", signal=signal.name)

    # Stop accepting new connections
    smtp_server.stop()
    http_server.stop()

    # Wait for in-flight requests to complete (max 30s)
    await asyncio.sleep(30)

    # Cancel remaining tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

    logger.info("shutdown_complete")

async def main():
    """Main entry point."""
    config = Config.from_env()
    logger.info("gateway_starting", config=config.safe_dict())

    # Initialize API client
    api_client = CakemailAPIClient(
        base_url=config.cakemail_api_url,
        timeout=config.api_timeout
    )

    # Initialize SMTP server
    smtp_server = SMTPServer(
        host='0.0.0.0',
        port=587,
        api_client=api_client,
        config=config
    )

    # Initialize HTTP server (health & metrics)
    http_server = HTTPServer(
        host='0.0.0.0',
        port=8080,
        smtp_server=smtp_server,
        api_client=api_client
    )

    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(
                shutdown(s, loop, smtp_server, http_server)
            )
        )

    # Start servers
    await asyncio.gather(
        smtp_server.start(),
        http_server.start()
    )

    logger.info("gateway_ready")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("gateway_interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error("gateway_failed", error=str(e), exc_info=True)
        sys.exit(1)
```

#### smtp_gateway/smtp/handler.py

```python
"""
SMTP command handlers.
"""
from aiosmtpd.smtp import SMTP, Envelope
from smtp_gateway.logging import get_logger
from smtp_gateway.metrics import (
    smtp_connections_total,
    smtp_emails_received_total,
    smtp_processing_duration_seconds
)

logger = get_logger()

class SMTPHandler:
    def __init__(self, api_client, auth_service, throttler, config):
        self.api_client = api_client
        self.auth_service = auth_service
        self.throttler = throttler
        self.config = config

    async def handle_EHLO(self, server, session, envelope, hostname):
        """Handle EHLO command."""
        session.host_name = hostname
        return '250 HELP'

    async def handle_AUTH(self, server, session, envelope, args):
        """Handle AUTH command."""
        # Check if TLS active
        if not session.ssl:
            return '530 Must issue STARTTLS first'

        # Parse credentials (AUTH PLAIN or AUTH LOGIN)
        username, password = parse_auth_credentials(args)

        # Check rate limiting
        if not await self.throttler.check_auth_attempt(session.peer[0]):
            return '421 Too many authentication attempts'

        # Validate credentials
        log = logger.bind(
            client_ip=session.peer[0],
            username=username
        )

        try:
            api_key = await self.auth_service.validate(username, password)
            session.api_key = api_key
            session.authenticated = True

            log.info("auth_success")
            return '235 Authentication successful'

        except AuthenticationError:
            await self.throttler.record_auth_failure(session.peer[0])
            log.warning("auth_failed")
            return '535 Authentication failed'

        except Exception as e:
            log.error("auth_error", error=str(e))
            return '451 Temporary authentication failure'

    async def handle_DATA(self, server, session, envelope):
        """Handle DATA command - process email."""
        if not session.authenticated:
            return '530 Authentication required'

        log = logger.bind(
            correlation_id=session.correlation_id,
            client_ip=session.peer[0],
            from_address=envelope.mail_from,
            recipient_count=len(envelope.rcpt_tos)
        )

        with smtp_processing_duration_seconds.labels(command='DATA').time():
            try:
                # Parse email
                email_data = await parse_email(envelope.content)

                # Transform to API format
                api_payload = transform_to_api_format(
                    email_data,
                    envelope.mail_from,
                    envelope.rcpt_tos
                )

                # Submit to API (with retry + circuit breaker)
                result = await self.api_client.submit_email_protected(
                    api_payload,
                    session.api_key
                )

                smtp_emails_received_total.labels(
                    authenticated_user=session.username
                ).inc()

                log.info(
                    "email_accepted",
                    message_id=result['message_id']
                )

                return f'250 Message accepted: {result["message_id"]}'

            except EmailValidationError as e:
                log.warning("email_rejected", reason=str(e))
                return f'550 Message rejected: {e.message}'

            except RateLimitError as e:
                log.warning("rate_limited", retry_after=e.retry_after)
                return f'451 Rate limit exceeded, retry after {e.retry_after}s'

            except CircuitBreakerOpenError:
                log.error("circuit_breaker_open")
                return '451 Service temporarily unavailable'

            except Exception as e:
                log.error("processing_error", error=str(e), exc_info=True)
                return '451 Temporary failure, try again later'
```

---

## Implementation Guidance

### Phase 1: Foundation (Weeks 1-2)

**Goal:** Deploy basic SMTP server with TLS and health checks

**Tasks:**
1. Setup project structure and dev environment
2. Implement basic SMTP server (EHLO, QUIT)
3. Add TLS/STARTTLS support
4. Create health check endpoints
5. Build Docker image and Helm chart
6. Deploy to staging K8s cluster

**Success Criteria:**
- Can connect to SMTP server via telnet/openssl
- TLS handshake succeeds
- Health endpoints return 200 OK
- Gateway runs in K8s with 2 replicas

### Phase 2: Auth & API Integration (Weeks 3-4)

**Goal:** End-to-end email flow (simple case)

**Tasks:**
1. Implement AUTH LOGIN and AUTH PLAIN
2. Integrate with Cakemail Auth API
3. Add credential caching
4. Implement basic email parsing (plain text, single recipient)
5. Integrate with Cakemail Email API
6. Add error handling and retry logic

**Success Criteria:**
- Can authenticate with valid credentials
- Can send plain text email via smtplib
- Email delivered to Cakemail inbox
- API errors mapped to correct SMTP codes

### Phase 3: Full Email Support (Weeks 5-6)

**Goal:** Production-ready email parsing

**Tasks:**
1. Add multi-recipient support
2. Implement HTML email parsing
3. Add MIME attachment support
4. Handle complex MIME structures
5. Test with Nodemailer, PHPMailer, etc.

**Success Criteria:**
- Can send HTML emails with attachments
- Multi-recipient emails delivered correctly
- All popular SMTP libraries work

### Phase 4: Production Readiness (Weeks 7-10)

**Goal:** Achieve SLA targets

**Tasks:**
1. Add structured logging (structlog)
2. Implement Prometheus metrics
3. Add circuit breaker pattern
4. Implement connection throttling
5. Performance optimization (load testing)
6. Security audit and hardening
7. Multi-zone deployment
8. HPA configuration and testing

**Success Criteria:**
- 1M+ emails/hour in load test
- <2s p99 processing delay
- 99.99% uptime in soak test
- Security audit passed
- HPA scales correctly under load

### Development Best Practices

**Testing Strategy:**
- Write tests **before** implementation (TDD)
- Unit test coverage >80%
- Integration tests for all critical paths
- Load tests before each release

**Code Review:**
- All code reviewed before merge
- Check for security issues, performance, readability
- Ensure logging and metrics added

**CI/CD:**
- Lint and format on every commit (pre-commit hooks)
- Run tests on every PR
- Build and push Docker image on main branch
- Auto-deploy to staging on merge
- Manual approval for production deploy

**Monitoring:**
- Set up Grafana dashboards in week 1
- Define SLOs and alerting thresholds
- Alert on: error rate >1%, p99 latency >3s, pod crash, circuit breaker open

---

## Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Python performance insufficient | Medium | High | Load test early (Week 4), fallback to Go if needed |
| Cakemail API capacity bottleneck | High | Critical | Coordinate with API team, load test staging API |
| Auth API doesn't exist | Medium | Critical | Validate in discovery phase, build if needed |
| OVH K8s reliability issues | Low | High | Multi-zone deployment, test zone failure scenarios |
| TLS certificate automation fails | Low | Medium | Fallback to manual cert management |
| Memory leaks under load | Medium | Medium | Memory profiling, soak tests, set conservative limits |
| Circuit breaker too sensitive | Low | Medium | Tune thresholds based on load test data |
| SMTP protocol edge cases | Medium | Medium | Comprehensive integration tests with real SMTP clients |

### Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Insufficient monitoring | High | High | Set up observability early (Week 1) |
| Deployment issues | Medium | Medium | Test deployment in staging, document runbooks |
| On-call burden | Medium | Medium | Comprehensive alerting, automate recovery where possible |
| Knowledge concentration | High | Medium | Documentation, pair programming, code reviews |

### Business Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Low customer adoption | Low | High | Beta program with 10+ pilot customers |
| Feature gap vs. competitors | Medium | Medium | Competitor analysis, prioritize must-have features |
| Cost overruns | Low | Medium | Monitor infrastructure costs, optimize resource usage |

### Risk Mitigation Timeline

**Week 1:**
- Set up monitoring and alerting
- Validate Cakemail API capacity

**Week 4:**
- Load test Python performance
- Make Go vs. Python decision if needed

**Week 6:**
- Security audit
- Test disaster recovery procedures

**Week 8:**
- Beta program with pilot customers
- Gather feedback on features

---

## Appendix

### Technology Decision Records

**ADR-001: Python 3.11+ for Implementation**

- **Status**: Accepted
- **Context**: Need to choose implementation language
- **Decision**: Python 3.11+ with async/await
- **Rationale**: Team expertise, clear code, mature libraries, sufficient performance for I/O-bound workload
- **Alternatives Considered**: Go (performance), Node.js (async I/O)

**ADR-002: Stateless Architecture**

- **Status**: Accepted
- **Context**: Need to design for horizontal scaling
- **Decision**: Zero persistent state, in-memory caching only
- **Rationale**: Simplifies operations, enables instant scaling, no data loss risk
- **Alternatives Considered**: Redis for shared cache (added complexity)

**ADR-003: Synchronous Email Forwarding**

- **Status**: Accepted
- **Context**: Need to decide on queuing vs. synchronous forwarding
- **Decision**: Forward emails synchronously to API, no message queue
- **Rationale**: Simplifies architecture, delegates retry to client (standard SMTP behavior)
- **Alternatives Considered**: RabbitMQ/Redis queue (added complexity, operational burden)

**ADR-004: Circuit Breaker Pattern**

- **Status**: Accepted
- **Context**: Need to protect from cascading failures
- **Decision**: Implement circuit breaker for API calls
- **Rationale**: Prevent resource exhaustion, fail fast, auto-recovery
- **Alternatives Considered**: None (best practice for distributed systems)

### Glossary

- **SMTP**: Simple Mail Transfer Protocol (RFC 5321)
- **STARTTLS**: Command to upgrade connection to TLS
- **MIME**: Multipurpose Internet Mail Extensions (RFC 2045-2049)
- **HPA**: Horizontal Pod Autoscaler (Kubernetes)
- **SLA**: Service Level Agreement
- **SLO**: Service Level Objective
- **Circuit Breaker**: Design pattern that prevents cascading failures
- **p50/p95/p99**: Latency percentiles (50th, 95th, 99th percentile)
- **TTL**: Time To Live (cache expiration)
- **OOM**: Out Of Memory
- **DDoS**: Distributed Denial of Service

### References

- **RFCs:**
  - RFC 5321: Simple Mail Transfer Protocol
  - RFC 5322: Internet Message Format
  - RFC 3207: SMTP Service Extension for Secure SMTP over TLS
  - RFC 2045-2049: Multipurpose Internet Mail Extensions (MIME)

- **Documentation:**
  - Cakemail Email API: https://docs.cakemail.com/en/api/email-api
  - aiosmtpd: https://aiosmtpd.readthedocs.io/
  - httpx: https://www.python-httpx.org/
  - FastAPI: https://fastapi.tiangolo.com/
  - Kubernetes: https://kubernetes.io/docs/

- **Best Practices:**
  - Twelve-Factor App: https://12factor.net/
  - Kubernetes Patterns: https://k8s-patterns.io/
  - Circuit Breaker Pattern: https://martinfowler.com/bliki/CircuitBreaker.html

---

## Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-10-02 | 1.0 | Initial architecture document | Chief Architect |

---

**Document Status:** APPROVED
**Next Review Date:** 2025-11-01
**Owner:** Chief Architect
**Stakeholders:** Engineering Team, DevOps, Product Management
