"""SMTP server implementation."""

from pathlib import Path
from typing import Any

import structlog
from aiosmtpd.controller import Controller

from smtp_gateway.config import get_settings
from smtp_gateway.smtp.handler import SMTPHandler
from smtp_gateway.utils.tls import create_tls_context, generate_self_signed_cert


logger = structlog.get_logger()


def _ensure_tls_certificates(settings) -> tuple[Path, Path]:
    """Ensure TLS certificates exist, generating self-signed if needed.

    Args:
        settings: Application settings

    Returns:
        Tuple of (cert_path, key_path)
    """
    cert_path = settings.tls_cert_path
    key_path = settings.tls_key_path

    # Check if certificates already exist
    if cert_path.exists() and key_path.exists():
        logger.info(
            "Using existing TLS certificates",
            cert_path=str(cert_path),
            key_path=str(key_path),
        )
        return cert_path, key_path

    # Generate self-signed certificates for local development
    logger.info(
        "TLS certificates not found, generating self-signed certificates",
        cert_path=str(cert_path),
        key_path=str(key_path),
    )

    return generate_self_signed_cert(
        hostname=settings.smtp_hostname,
        cert_path=cert_path,
        key_path=key_path,
    )


async def create_smtp_server() -> Any:
    """Create and start the SMTP server.

    This creates an aiosmtpd Controller that runs the SMTP server
    on the configured host and port with STARTTLS support.

    For Story 1.3, TLS support is added with:
    - STARTTLS command for upgrading connections to TLS
    - Self-signed certificate generation for local development
    - Secure TLS context (TLS 1.2+, strong ciphers)

    Returns:
        SMTP server controller instance
    """
    settings = get_settings()

    logger.info(
        "Creating SMTP server",
        host=settings.smtp_host,
        port=settings.smtp_port,
        hostname=settings.smtp_hostname,
    )

    # Ensure TLS certificates exist
    cert_path, key_path = _ensure_tls_certificates(settings)

    # Create TLS context
    tls_context = create_tls_context(
        cert_path=cert_path,
        key_path=key_path,
        require_cert=False,  # Don't require client certificates
    )

    # Create the SMTP handler
    handler = SMTPHandler()

    # Create the SMTP controller with STARTTLS support
    controller = Controller(
        handler,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        # Use the handler's hostname
        server_hostname=settings.smtp_hostname,
        # Enable STARTTLS with our TLS context
        require_starttls=False,  # Optional STARTTLS (client can choose)
        tls_context=tls_context,
        # Enable AUTH mechanisms (Story 2.1)
        # Auth will only be advertised after STARTTLS
        auth_require_tls=True,  # Require TLS before AUTH
        auth_callback=None,  # We handle auth in handle_AUTH method
        # Enable for debugging during development
        decode_data=False,  # We'll handle decoding ourselves
        enable_SMTPUTF8=True,  # Support UTF-8 email addresses
    )

    # Start the controller (this starts the SMTP server)
    controller.start()

    logger.info(
        "SMTP server started with STARTTLS support",
        host=settings.smtp_host,
        port=settings.smtp_port,
        tls_enabled=True,
    )

    return controller
