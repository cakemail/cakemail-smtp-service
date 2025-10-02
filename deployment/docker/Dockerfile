# Multi-stage Dockerfile for SMTP Gateway
# Stage 1: Build stage
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /build

# Install build dependencies
# gcc and libffi-dev needed for cryptography package
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Stage 2: Runtime stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Create non-root user for security
RUN groupadd -r smtp && useradd -r -g smtp smtp

# Install runtime dependencies only
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ /app/src/

# Create directory for TLS certificates
RUN mkdir -p /etc/smtp-gateway/tls && \
    chown -R smtp:smtp /etc/smtp-gateway

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

# Switch to non-root user
USER smtp

# Expose ports
EXPOSE 587 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health/live')"

# Run the application
CMD ["python", "-m", "smtp_gateway"]
