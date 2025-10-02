"""Prometheus metrics definitions for SMTP Gateway."""

from prometheus_client import Counter, Gauge, Histogram

# Counter metrics
smtp_connections_total = Counter(
    "smtp_connections_total",
    "Total number of SMTP connections",
    ["status"],  # success, failed
)

smtp_emails_received_total = Counter(
    "smtp_emails_received_total",
    "Total number of emails received",
    ["status"],  # accepted, rejected
)

smtp_emails_forwarded_total = Counter(
    "smtp_emails_forwarded_total",
    "Total number of emails forwarded to Cakemail API",
    ["status"],  # success, failed
)

smtp_auth_failures_total = Counter(
    "smtp_auth_failures_total",
    "Total number of authentication failures",
    ["reason"],  # invalid_credentials, timeout, api_error
)

smtp_api_errors_total = Counter(
    "smtp_api_errors_total",
    "Total number of Cakemail API errors",
    ["error_type"],  # validation, rate_limit, server_error, network_error
)

smtp_commands_total = Counter(
    "smtp_commands_total",
    "Total number of SMTP commands processed",
    ["command", "status"],  # command: EHLO, AUTH, MAIL, RCPT, DATA, etc.
)

# Histogram metrics
smtp_processing_duration_seconds = Histogram(
    "smtp_processing_duration_seconds",
    "Email processing duration in seconds",
    ["stage"],  # auth, parse, transform, submit
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

smtp_api_latency_seconds = Histogram(
    "smtp_api_latency_seconds",
    "Cakemail API request latency in seconds",
    ["endpoint", "status"],  # endpoint: auth, email; status: success, error
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1.0, 2.0),
)

smtp_connection_duration_seconds = Histogram(
    "smtp_connection_duration_seconds",
    "SMTP connection duration in seconds",
    buckets=(1, 5, 10, 30, 60, 120, 300, 600),
)

smtp_message_size_bytes = Histogram(
    "smtp_message_size_bytes",
    "Email message size in bytes",
    buckets=(1024, 10240, 102400, 1048576, 10485760, 26214400),  # 1KB to 25MB
)

# Gauge metrics
smtp_active_connections = Gauge(
    "smtp_active_connections",
    "Current number of active SMTP connections",
)

smtp_api_key_cache_size = Gauge(
    "smtp_api_key_cache_size",
    "Current size of API key cache",
)

smtp_circuit_breaker_state = Gauge(
    "smtp_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["service"],  # cakemail_api
)
