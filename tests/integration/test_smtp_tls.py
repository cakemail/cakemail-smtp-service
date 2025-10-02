"""Integration tests for SMTP TLS/STARTTLS functionality."""

import asyncio
import os
import smtplib
import ssl
from pathlib import Path

import pytest

from smtp_gateway.smtp.server import create_smtp_server


class TestSMTPTLS:
    """Integration tests for SMTP STARTTLS functionality."""

    @pytest.fixture
    async def smtp_server(self, tmp_path):
        """Create and start an SMTP server for testing."""
        # Set environment variables for TLS cert paths to use tmp_path
        cert_path = tmp_path / "tls.crt"
        key_path = tmp_path / "tls.key"

        os.environ["TLS_CERT_PATH"] = str(cert_path)
        os.environ["TLS_KEY_PATH"] = str(key_path)

        controller = await create_smtp_server()
        # Give the server a moment to fully start
        await asyncio.sleep(0.1)
        yield controller
        controller.stop()

        # Cleanup environment variables
        os.environ.pop("TLS_CERT_PATH", None)
        os.environ.pop("TLS_KEY_PATH", None)

    @pytest.mark.asyncio
    async def test_starttls_connection(self, smtp_server):
        """Test successful STARTTLS upgrade."""
        # Arrange
        smtp_host = "localhost"
        smtp_port = 587

        # Act & Assert
        with smtplib.SMTP(smtp_host, smtp_port) as client:
            # Connection successful
            code, msg = client.ehlo("test.example.com")
            assert code == 250

            # STARTTLS should be advertised
            assert client.has_extn("STARTTLS")

            # Upgrade to TLS
            code, msg = client.starttls()
            assert code == 220

            # After STARTTLS, need to send EHLO again
            code, msg = client.ehlo("test.example.com")
            assert code == 250

    @pytest.mark.asyncio
    async def test_starttls_with_context(self, smtp_server):
        """Test STARTTLS with custom SSL context."""
        # Arrange
        smtp_host = "localhost"
        smtp_port = 587

        # Create SSL context that doesn't verify certificates
        # (needed for self-signed certs in testing)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Act & Assert
        with smtplib.SMTP(smtp_host, smtp_port) as client:
            code, msg = client.ehlo("test.example.com")
            assert code == 250

            # Upgrade to TLS with custom context
            code, msg = client.starttls(context=context)
            assert code == 220

            # Verify connection is encrypted
            # After STARTTLS, the socket should be wrapped in SSL
            assert isinstance(client.sock, ssl.SSLSocket)

    @pytest.mark.asyncio
    async def test_auth_rejected_before_starttls(self, smtp_server):
        """Test that AUTH is rejected before STARTTLS.

        Note: For Story 1.3, AUTH isn't advertised until we implement
        it in Story 2.1. This test verifies the rejection logic would work
        if AUTH were attempted.
        """
        # For now, skip this test since AUTH isn't fully implemented
        # The handle_AUTH method exists and will reject before STARTTLS
        # but the AUTH extension isn't advertised by aiosmtpd yet
        pytest.skip("AUTH not fully implemented until Story 2.1")

    @pytest.mark.asyncio
    async def test_auth_allowed_after_starttls(self, smtp_server):
        """Test that AUTH is allowed after STARTTLS (even if not implemented)."""
        # Skip for now - will be tested in Story 2.1 when AUTH is fully implemented
        pytest.skip("AUTH not fully implemented until Story 2.1")

    @pytest.mark.asyncio
    async def test_tls_version(self, smtp_server):
        """Test that TLS 1.2 or higher is used."""
        # Arrange
        smtp_host = "localhost"
        smtp_port = 587
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Act
        with smtplib.SMTP(smtp_host, smtp_port) as client:
            client.ehlo("test.example.com")
            client.starttls(context=context)

            # Assert - Check TLS version
            # Should be TLS 1.2 or TLS 1.3
            cipher = client.sock.cipher()
            assert cipher is not None, "No cipher info available"

            # Get TLS version
            tls_version = client.sock.version()
            assert tls_version in ["TLSv1.2", "TLSv1.3"], (
                f"Expected TLS 1.2 or 1.3, got {tls_version}"
            )

    @pytest.mark.asyncio
    async def test_multiple_starttls_connections(self, smtp_server):
        """Test that server handles multiple STARTTLS connections."""
        # Arrange
        smtp_host = "localhost"
        smtp_port = 587
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Act & Assert - Connect multiple times with STARTTLS
        for i in range(3):
            with smtplib.SMTP(smtp_host, smtp_port) as client:
                client.ehlo(f"client{i}.example.com")
                code, msg = client.starttls(context=context)
                assert code == 220

                # Verify TLS is active
                assert isinstance(client.sock, ssl.SSLSocket)
