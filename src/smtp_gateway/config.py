"""Configuration management for SMTP Gateway."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Cakemail API Configuration
    cakemail_api_url: str = Field(
        default="https://api.cakemail.com/v1",
        description="Cakemail Email API base URL",
    )
    cakemail_auth_url: str = Field(
        default="https://api.cakemail.com/v1/auth",
        description="Cakemail Authentication API URL",
    )

    # SMTP Server Configuration
    smtp_host: str = Field(default="0.0.0.0", description="SMTP server bind address")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_hostname: str = Field(default="smtp.cakemail.com", description="SMTP server hostname")

    # TLS Configuration
    tls_cert_path: Path = Field(
        default=Path("/etc/smtp-gateway/tls/tls.crt"),
        description="Path to TLS certificate",
    )
    tls_key_path: Path = Field(
        default=Path("/etc/smtp-gateway/tls/tls.key"),
        description="Path to TLS private key",
    )

    # HTTP Server Configuration
    http_host: str = Field(default="0.0.0.0", description="HTTP server bind address")
    http_port: int = Field(default=8080, description="HTTP server port")

    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or console)")

    # Rate Limiting Configuration
    rate_limit_per_ip: int = Field(
        default=100,
        description="Maximum emails per minute per IP address",
    )
    max_connections_per_pod: int = Field(
        default=1000,
        description="Maximum concurrent connections per pod",
    )
    max_connections_per_ip: int = Field(
        default=10,
        description="Maximum concurrent connections per IP address",
    )

    # Connection Configuration
    connection_timeout: int = Field(
        default=300,
        description="Connection idle timeout in seconds",
    )
    message_size_limit: int = Field(
        default=26214400,  # 25MB
        description="Maximum message size in bytes",
    )
    max_recipients: int = Field(
        default=100,
        description="Maximum recipients per email",
    )

    # API Client Configuration
    api_timeout: float = Field(
        default=10.0,
        description="API request timeout in seconds",
    )
    api_connection_pool_size: int = Field(
        default=100,
        description="API connection pool size",
    )
    api_max_retries: int = Field(
        default=2,
        description="Maximum API retry attempts",
    )

    # Caching Configuration
    auth_cache_ttl: int = Field(
        default=900,  # 15 minutes
        description="Authentication cache TTL in seconds",
    )

    # Circuit Breaker Configuration
    circuit_breaker_threshold: int = Field(
        default=5,
        description="Circuit breaker failure threshold",
    )
    circuit_breaker_timeout: int = Field(
        default=60,
        description="Circuit breaker timeout in seconds",
    )

    def validate_tls_paths(self) -> None:
        """Validate TLS certificate paths exist."""
        if not self.tls_cert_path.exists():
            raise ValueError(f"TLS certificate not found: {self.tls_cert_path}")
        if not self.tls_key_path.exists():
            raise ValueError(f"TLS key not found: {self.tls_key_path}")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
