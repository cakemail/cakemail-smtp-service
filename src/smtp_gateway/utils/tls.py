"""TLS utilities for SMTP Gateway."""

import ssl
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import structlog
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


logger = structlog.get_logger()


def generate_self_signed_cert(
    hostname: str,
    cert_path: Path,
    key_path: Path,
    days_valid: int = 365,
) -> tuple[Path, Path]:
    """Generate a self-signed certificate for local development.

    Args:
        hostname: Hostname for the certificate (e.g., "smtp.cakemail.com")
        cert_path: Path to save the certificate file
        key_path: Path to save the private key file
        days_valid: Number of days the certificate is valid (default: 365)

    Returns:
        Tuple of (cert_path, key_path)

    Raises:
        OSError: If unable to write certificate or key files
    """
    logger.info(
        "Generating self-signed certificate",
        hostname=hostname,
        cert_path=str(cert_path),
        key_path=str(key_path),
        days_valid=days_valid,
    )

    # Generate RSA private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Build certificate subject and issuer (same for self-signed)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "CA"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Quebec"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Montreal"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Cakemail SMTP Gateway"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])

    # Build certificate
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=days_valid))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(hostname),
                x509.DNSName(f"*.{hostname}"),  # Wildcard for subdomains
                x509.DNSName("localhost"),  # Allow localhost for testing
            ]),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Ensure parent directories exist
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    # Write certificate to file
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    # Write private key to file
    with open(key_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Set restrictive permissions on private key (owner read-only)
    key_path.chmod(0o600)

    logger.info(
        "Self-signed certificate generated successfully",
        cert_path=str(cert_path),
        key_path=str(key_path),
    )

    return cert_path, key_path


def create_tls_context(
    cert_path: Optional[Path] = None,
    key_path: Optional[Path] = None,
    require_cert: bool = False,
) -> ssl.SSLContext:
    """Create a secure TLS context for SMTP server.

    Configures TLS with secure defaults:
    - TLS 1.2+ only (no SSLv2, SSLv3, TLS 1.0, TLS 1.1)
    - Strong cipher suites
    - Server-side certificate verification

    Args:
        cert_path: Path to TLS certificate file (PEM format)
        key_path: Path to TLS private key file (PEM format)
        require_cert: Whether to require client certificates (default: False)

    Returns:
        Configured SSL context

    Raises:
        FileNotFoundError: If certificate or key file not found
        ssl.SSLError: If unable to load certificate or key
    """
    logger.info(
        "Creating TLS context",
        cert_path=str(cert_path) if cert_path else None,
        key_path=str(key_path) if key_path else None,
        require_cert=require_cert,
    )

    # Create SSL context with secure defaults
    # PROTOCOL_TLS_SERVER automatically selects the highest protocol version
    # that both client and server support
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # Disable insecure protocols (SSLv2, SSLv3, TLS 1.0, TLS 1.1)
    # Only allow TLS 1.2 and TLS 1.3
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_3

    # Set secure cipher suites (Mozilla Modern compatibility)
    # Prioritize forward secrecy (ECDHE) and AEAD ciphers (GCM, ChaCha20)
    context.set_ciphers(
        "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
    )

    # Enable certificate verification if required
    if require_cert:
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
    else:
        context.verify_mode = ssl.CERT_NONE

    # Load server certificate and private key if provided
    if cert_path and key_path:
        if not cert_path.exists():
            raise FileNotFoundError(f"Certificate file not found: {cert_path}")
        if not key_path.exists():
            raise FileNotFoundError(f"Private key file not found: {key_path}")

        context.load_cert_chain(
            certfile=str(cert_path),
            keyfile=str(key_path),
        )

        logger.info(
            "TLS context created with certificate",
            cert_path=str(cert_path),
        )
    else:
        logger.warning(
            "TLS context created without certificate - "
            "STARTTLS will fail until certificate is loaded"
        )

    return context
