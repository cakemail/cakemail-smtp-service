# Project Brief: Cakemail SMTP Gateway

## Executive Summary

**Cakemail SMTP Gateway** is a high-performance SMTP server that bridges the SMTP protocol to the Cakemail Email API, enabling developers to send emails through Cakemail's infrastructure using standard SMTP libraries and legacy applications. The gateway addresses the critical need for seamless migration from traditional SMTP-based email services (SendGrid, Mandrill, Mailgun, AWS SES) to Cakemail's modern API platform without requiring application code changes. Target users include developers with existing SMTP integrations and organizations operating legacy systems that cannot easily adopt REST APIs. The gateway delivers enterprise-grade throughput (1M+ emails/hour) while maintaining drop-in compatibility with existing SMTP workflows, significantly reducing migration friction and accelerating Cakemail adoption.

## Problem Statement

Many developers and organizations rely on SMTP-based email delivery services like SendGrid, Mandrill, Mailgun, and AWS SES. When considering migration to Cakemail's Email API, they face significant technical barriers:

**Current State & Pain Points:**
- Existing applications are built around SMTP protocol integration using standard libraries
- Legacy systems cannot easily be refactored to adopt REST API calls
- Migration requires substantial code changes, testing, and deployment across multiple services
- Development teams face opportunity cost: migration work delays feature development
- Risk of introducing bugs during email infrastructure replacement

**Impact:**
- **Migration friction** creates a significant barrier to Cakemail adoption, even when the Email API offers superior features or pricing
- **Lost revenue opportunities** as potential customers choose to stay with incumbent providers due to switching costs
- **Competitive disadvantage** against providers offering SMTP compatibility alongside modern APIs
- **Developer time waste**: Teams estimate weeks or months of effort for what should be a configuration change

**Why Existing Solutions Fall Short:**
- Cakemail's Email API requires REST integration, which is not backward-compatible with SMTP
- Manual SMTP-to-API rewrite forces customers to modify and retest application code
- No "drop-in replacement" option exists for customers wanting zero-downtime migration

**Urgency:**
- Email infrastructure is mission-critical; customers are reluctant to risk disruption
- Competitors offering SMTP compatibility have a clear adoption advantage
- Market window exists to capture migrating customers from other SMTP providers

## Proposed Solution

The **Cakemail SMTP Gateway** is a standalone SMTP server that acts as a protocol translation layer between SMTP clients and the Cakemail Email API.

**Core Concept:**
- Accept standard SMTP connections (port 587/TLS) from any SMTP-compatible client
- Authenticate users via username/password credentials that map to Cakemail account credentials
- Parse incoming SMTP email messages (headers, body, attachments)
- Transform SMTP data into Cakemail Email API requests
- Forward emails to Cakemail's infrastructure via HTTPS API calls
- Return SMTP success/error responses to the client

**Key Differentiators:**
- **Zero code changes required**: Drop-in replacement for SendGrid/Mandrill/Mailgun SMTP endpoints - simply update the SMTP hostname and credentials
- **Enterprise-grade performance**: Designed to handle 1M+ emails per hour through async processing, connection pooling, and horizontal scaling
- **Full SMTP compliance**: Supports standard SMTP features (TLS, AUTH, MIME, attachments) ensuring compatibility with all major libraries and clients
- **Kubernetes-native**: Designed for cloud deployment with auto-scaling, health checks, and observability

**Why This Succeeds:**
- **Eliminates migration friction**: What previously required weeks of development becomes a 5-minute configuration change
- **Preserves developer workflows**: Teams continue using familiar SMTP libraries and patterns
- **Enables gradual transition**: Customers can migrate to SMTP first, then optionally adopt the REST API later for advanced features
- **Competitive parity**: Matches capabilities of competitors while leveraging Cakemail's superior email infrastructure

**High-Level Vision:**
A production-ready, enterprise-grade SMTP gateway that becomes the standard migration path for customers moving to Cakemail from legacy SMTP providers, accelerating platform adoption and reducing customer acquisition friction. As a **Canadian-owned solution**, the gateway provides a competitive alternative to US-based SMTP providers, enabling both transactional and high-volume marketing email delivery at enterprise scale.

## Target Users

### Primary User Segment: Developers Migrating from SMTP Providers

**Demographic/Firmographic Profile:**
- Software engineers and DevOps teams at SaaS companies, e-commerce platforms, and web applications
- Organizations currently using SendGrid, Mandrill, Mailgun, AWS SES, or similar SMTP-based email services
- Team sizes ranging from solo developers to enterprise engineering teams
- Companies with 10K-100M+ monthly email volume (both transactional and marketing campaigns)
- **Canadian companies** seeking Canadian-owned email infrastructure for data sovereignty, compliance, and regional preferences

**Current Behaviors and Workflows:**
- Send **transactional emails** (password resets, order confirmations, notifications) and **marketing campaigns** (newsletters, promotional emails, drip campaigns) via SMTP libraries
- Use language-specific SMTP clients (Nodemailer for Node.js, SMTP lib for Python, PHPMailer, etc.)
- Deploy high-volume SMTP relay for bulk marketing email sends
- Configure SMTP credentials in environment variables or configuration files
- Monitor email delivery through provider dashboards
- Minimal custom integration code—rely on standard SMTP protocol

**Specific Needs and Pain Points:**
- Need to migrate email infrastructure without disrupting production systems
- Cannot justify weeks of development time for email provider migration
- Require confidence that migration won't introduce bugs or delivery failures
- Want to test new provider in staging/canary environments before full rollout
- Need performance guarantees to handle peak email volumes (1M+ emails/hour for marketing campaigns)
- **Canadian companies**: Prefer Canadian-owned providers for data residency, avoiding US-based services due to privacy regulations (PIPEDA) or corporate policy

**Goals They're Trying to Achieve:**
- Seamlessly switch email providers with minimal risk and development effort
- Maintain existing application code and deployment processes
- Reduce email infrastructure costs or improve deliverability by moving to Cakemail
- Achieve zero-downtime migration with gradual rollout capability
- **Canadian advantage**: Support Canadian businesses by using Canadian infrastructure, ensuring data stays within national borders

### Secondary User Segment: Legacy System Operators

**Demographic/Firmographic Profile:**
- IT administrators and maintenance teams supporting legacy enterprise applications
- Organizations with monolithic applications built 5-15+ years ago
- Industries with long software lifecycles (finance, healthcare, government, education)
- Companies with limited budget or approval for major application refactoring

**Current Behaviors and Workflows:**
- Operate applications where codebase changes require extensive approval and testing
- Use SMTP as the only supported email integration method in legacy software
- Rely on IT operations to manage email infrastructure, not development teams
- Prioritize stability and uptime over new features

**Specific Needs and Pain Points:**
- Cannot modify application source code due to technical debt or lack of original developers
- Need to migrate from deprecated/expensive SMTP providers without touching application layer
- Require drop-in replacement with identical SMTP interface
- Must maintain compliance and audit trails during infrastructure changes

**Goals They're Trying to Achieve:**
- Replace aging email infrastructure without application code changes
- Meet compliance requirements or service-level agreements during provider migration
- Reduce operational costs by switching email providers
- Future-proof email delivery without refactoring legacy applications

## Goals & Success Metrics

### Business Objectives

- **Reduce customer acquisition friction**: Decrease time-to-first-email for new Cakemail customers from weeks (API migration) to minutes (SMTP configuration change), targeting 80% reduction in onboarding time
- **Capture market share from competitors**: Win 15-20% of migrating customers from SendGrid, Mandrill, Mailgun, and AWS SES within first 12 months of launch
- **Increase Canadian market penetration**: Position Cakemail as the preferred Canadian-owned alternative to US-based SMTP providers, targeting 30% of Canadian SMB email market
- **Enable enterprise-grade revenue**: Support customers sending 1M+ emails/hour, unlocking high-volume contracts and expanding upmarket customer segment
- **Accelerate platform adoption**: Convert 40% of SMTP Gateway users to adopt Cakemail's REST API within 18 months for advanced features

### User Success Metrics

- **Migration completion time**: Users complete SMTP provider migration in <30 minutes (configuration + testing)
- **Zero-downtime migration**: 95%+ of users successfully migrate without production email delivery failures
- **Performance satisfaction**: Gateway sustains 1M+ emails/hour throughput with <100ms p95 latency for API forwarding
- **Developer experience**: 90%+ of users report SMTP Gateway "works exactly like SendGrid/Mailgun" (drop-in compatibility)
- **Retention**: 85%+ of SMTP Gateway users remain active after 6 months (vs. churn due to migration complexity)

### Key Performance Indicators (KPIs)

- **Adoption Rate**: Number of active SMTP Gateway users (target: 500 users in first 6 months, 2000 in first year)
- **Email Volume**: Total emails processed through gateway (target: 100M emails/month within 6 months)
- **Migration Conversion**: % of leads citing "easy SMTP migration" as primary reason for choosing Cakemail (target: 60%+)
- **Performance SLA**: 99.99% uptime for SMTP Gateway service with <2s p99 SMTP response time (total processing delay)
- **Canadian Market Share**: % of new Canadian customers choosing SMTP Gateway as entry point (target: 50%+)
- **Revenue Impact**: MRR from SMTP Gateway users (target: $50K MRR within 12 months)

## MVP Scope

### Core Features (Must Have)

- **SMTP Server (Port 587/TLS)**: Full-featured SMTP server accepting connections on standard submission port (587) with mandatory TLS encryption
- **Authentication via Cakemail Credentials**: Username/password authentication where credentials map to Cakemail account API keys for secure, account-based access
- **MIME Message Parsing**: Parse standard SMTP email format including headers (From, To, CC, BCC, Subject), body (plain text and HTML), and MIME attachments
- **Cakemail Email API Integration**: Transform parsed SMTP data into Cakemail Email API requests and forward via HTTPS to https://docs.cakemail.com/en/api/email-api#submit-an-email
- **SMTP Response Handling**: Return standard SMTP success (250 OK) and error codes (authentication failures, API errors, rate limits) to client
- **High-Performance Async Processing**: Support 1M+ emails/hour through async request handling, connection pooling, and non-blocking I/O
- **Kubernetes Deployment**: Containerized service with Kubernetes manifests, health checks (liveness/readiness probes), and horizontal pod autoscaling
- **Basic Observability**: Structured logging (request tracing, errors, performance metrics) and Prometheus metrics endpoint for monitoring

### Out of Scope for MVP

- Advanced SMTP features (DKIM signing, SPF validation, custom bounce handling)
- Web-based admin dashboard or UI
- Multi-region deployment or geographic routing
- Webhook callbacks for delivery status
- Email queuing with retry logic (rely on Cakemail API's delivery guarantees)
- Support for legacy SMTP ports (25, 465) - MVP focuses on modern port 587/TLS only
- Custom domain routing or white-label SMTP hostnames
- Rate limiting per customer (rely on Cakemail API's rate limits)
- Message content validation or spam filtering (Cakemail API handles this)

### MVP Success Criteria

The MVP is successful when:
- A developer can replace their SendGrid SMTP configuration (hostname + credentials) with Cakemail SMTP Gateway and send emails without code changes
- Gateway sustains 1M emails/hour in load testing with <2s p99 processing delay
- Gateway achieves 99.99% uptime over 30-day period in production
- 10+ pilot customers successfully migrate from competitor SMTP providers with zero production issues
- Gateway passes security audit for credential handling and TLS implementation

## Post-MVP Vision

### Phase 2 Features

Once the MVP proves market fit and achieves stable production operation, the following enhancements become priorities:

- **Multi-Region Deployment**: Deploy gateway instances in Canadian and US data centers with geographic routing for reduced latency and data residency compliance
- **Webhook Support**: Real-time delivery status callbacks (delivered, bounced, opened, clicked) to customer endpoints for event-driven workflows
- **Enhanced Observability**: Distributed tracing (OpenTelemetry), advanced metrics dashboards (Grafana), alerting (PagerDuty integration)
- **Rate Limiting & Quotas**: Per-customer rate limits and daily quotas with configurable policies
- **Legacy Port Support**: Optional support for ports 25 and 465 for customers with legacy infrastructure requirements

### Long-term Vision

**Within 1-2 years**, the Cakemail SMTP Gateway evolves into a comprehensive email delivery platform:

- **API Parity**: Feature parity between SMTP Gateway and Cakemail REST API, allowing customers to mix protocols seamlessly
- **Global Edge Network**: Multi-region deployment across North America, Europe, and Asia-Pacific with intelligent geographic routing

### Expansion Opportunities

- **SMTP Receiving Gateway**: Inbound email processing (receive emails via SMTP, forward to webhooks or storage)
- **Email Testing & Sandbox**: Developer-focused SMTP endpoint for testing email integrations without sending real emails
- **Migration Toolkit**: Automated tools and services to migrate customers from competitor SMTP providers (config converters, bulk migration support)
- **Compliance & Archiving**: Built-in email archiving for regulatory compliance (HIPAA, SOC2, GDPR)

## Technical Considerations

### Platform Requirements

- **Target Platforms**: Backend service deployed on OVH Private Cloud Kubernetes
- **Regional Requirements**: Canadian data center deployment for data sovereignty and PIPEDA compliance
- **Performance Requirements**:
  - 1M+ emails/hour throughput
  - 99.99% uptime SLA
  - <2s p99 processing delay
  - <100ms p95 API forwarding latency

### Technology Preferences

- **Frontend**: N/A (backend service only)
- **Backend**:
  - **Language**: Python 3.11+
  - **SMTP Server**: aiosmtpd (async SMTP server library)
  - **HTTP Client**: httpx (async HTTP client for Cakemail API calls)
  - **Framework**: FastAPI for health check/metrics endpoints
- **Database**: Stateless architecture - no persistent storage required (rely on Cakemail API for all state)
- **Hosting/Infrastructure**:
  - OVH Private Cloud Kubernetes
  - Container Registry: OVH Harbor or Docker Hub
  - CI/CD: GitHub Actions
  - IaC: Helm charts for Kubernetes deployment

### Architecture Considerations

- **Repository Structure**: Single repository (monorepo not needed for single service)
- **Service Architecture**: Stateless monolith with horizontal scaling via Kubernetes HPA (Horizontal Pod Autoscaler)
  - Multiple gateway pods behind Kubernetes Service (load balancer)
  - Auto-scaling based on CPU/memory and custom metrics (emails/second)
  - Async processing model: Each pod handles thousands of concurrent SMTP connections
- **Integration Requirements**:
  - **Authentication**: SMTP username/password validated against Cakemail API (credential lookup via API call on first connection, cached in-memory per pod)
  - **API Integration**: Direct HTTPS calls to Cakemail Email API using customer credentials
  - **Observability**: Prometheus metrics endpoint + structured JSON logging to stdout (collected by Kubernetes logging stack)
- **Security/Compliance**:
  - **TLS**: cert-manager with Let's Encrypt for automated certificate management
  - **Secrets**: Kubernetes Secrets for sensitive config (Cakemail API endpoints, internal auth tokens)
  - **Compliance**: PIPEDA compliance via Canadian data center deployment; all email data transient (no storage)
  - **Network Security**: Kubernetes NetworkPolicies for pod-to-pod communication restrictions

## Constraints & Assumptions

### Constraints

- **Budget**: Bootstrapped development - leverage open-source tools and OVH infrastructure to minimize costs
- **Timeline**: Target MVP launch within 3-6 months to capture migration opportunities from competitors
- **Resources**: Small engineering team (1-3 developers) - architecture must be simple and maintainable
- **Technical**:
  - Must integrate with existing Cakemail Email API (no modifications to API allowed)
  - OVH Private Cloud Kubernetes infrastructure (no AWS/GCP/Azure services)
  - Python-based implementation (team expertise constraint)
  - Stateless design required for horizontal scaling

### Key Assumptions

- **Cakemail Email API stability**: Assumes Cakemail Email API can handle 1M+ emails/hour and has sufficient capacity for gateway traffic
- **Authentication mechanism**: Assumes Cakemail API provides endpoint to validate SMTP credentials and retrieve API keys
- **Canadian market demand**: Assumes significant demand exists for Canadian-owned SMTP alternative (validation needed)
- **SMTP protocol coverage**: Assumes port 587/TLS with basic SMTP features is sufficient for 80%+ of migration use cases
- **Competitor migration**: Assumes customers currently using SendGrid/Mandrill/Mailgun are actively seeking alternatives
- **Performance achievable**: Assumes Python async architecture can achieve 99.99% uptime and <2s p99 latency targets
- **No email storage**: Assumes transient email processing (no persistence) meets customer needs and compliance requirements
- **OVH reliability**: Assumes OVH Private Cloud provides sufficient reliability for 99.99% uptime SLA
- **Team capability**: Assumes team has or can acquire expertise in Python async, SMTP protocol, and Kubernetes operations

## Risks & Open Questions

### Key Risks

- **Cakemail API capacity**: If Cakemail Email API cannot handle 1M+ emails/hour or becomes a bottleneck, gateway performance degrades. *Mitigation: Load test API early, work with API team on capacity planning*
- **Authentication endpoint dependency**: If no Cakemail API endpoint exists to validate SMTP credentials, requires API changes before gateway can launch. *Mitigation: Validate authentication mechanism feasibility in discovery phase*
- **Python performance ceiling**: Python async may struggle to achieve 99.99% uptime under high load or memory pressure. *Mitigation: Conduct performance benchmarking early, consider fallback to Go if targets unachievable*
- **OVH infrastructure reliability**: OVH Private Cloud may not provide 99.99% uptime guarantees. *Mitigation: Review OVH SLA, architect for multi-zone redundancy, prepare failover plans*
- **Market validation failure**: Canadian market demand for SMTP gateway may be overestimated. *Mitigation: Pre-launch survey with existing customers, beta program with 10+ pilot users*
- **Feature gap vs competitors**: Basic SMTP implementation may lack features customers expect (DKIM, webhooks, dashboard). *Mitigation: Conduct competitor feature analysis, prioritize most-requested features for Phase 2*
- **Security vulnerabilities**: SMTP protocol and credential handling introduce attack surface (spam relay, credential theft). *Mitigation: Security audit before launch, rate limiting, connection throttling*

### Open Questions

- Does Cakemail Email API have an authentication endpoint to validate SMTP credentials and retrieve API keys?
- What is the current capacity limit of the Cakemail Email API (requests/second, emails/hour)?
- Are there existing Cakemail customers requesting SMTP support? If so, what are their primary use cases?
- What SMTP features beyond basic email sending are must-haves vs nice-to-haves? (DKIM, webhooks, custom headers?)
- Does OVH Private Cloud provide multi-zone deployment options for high availability?
- What is the team's current expertise level with Python async, SMTP protocol, and Kubernetes?
- Are there regulatory requirements beyond PIPEDA that affect Canadian email infrastructure?
- What is the pricing model for SMTP Gateway usage? (Same as API, separate pricing tier, free during beta?)

### Areas Needing Further Research

- **SMTP protocol compliance**: Deep dive into RFC 5321 (SMTP), RFC 5322 (Email format), RFC 3207 (STARTTLS) to ensure full compatibility
- **Competitor analysis**: Detailed feature comparison of SendGrid, Mandrill, Mailgun, AWS SES SMTP offerings
- **Python SMTP libraries**: Evaluate aiosmtpd alternatives (smtplib, Twisted) for performance and feature completeness
- **Load testing strategy**: Design load tests to validate 1M+ emails/hour with realistic traffic patterns
- **Canadian data sovereignty**: Research PIPEDA requirements and whether additional certifications (SOC2, ISO 27001) are needed
- **Migration patterns**: Document common SMTP configuration patterns from competitors to inform documentation and tooling

## Next Steps

### Immediate Actions

1. Validate Cakemail Email API authentication mechanism and capacity with API team
2. Conduct market validation survey with existing customers regarding SMTP migration needs
3. Review OVH Private Cloud SLA and multi-zone deployment capabilities
4. Perform competitor feature analysis (SendGrid, Mandrill, Mailgun, AWS SES)
5. Create detailed technical architecture document using this Project Brief as input

### PM Handoff

This Project Brief provides the full context for **Cakemail SMTP Gateway**. Please start in 'PRD Generation Mode', review the brief thoroughly to work with the user to create the PRD section by section as the template indicates, asking for any necessary clarification or suggesting improvements.
