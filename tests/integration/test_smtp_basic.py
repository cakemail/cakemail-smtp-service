"""Integration tests for basic SMTP functionality."""

import asyncio
import os
import smtplib

import pytest

from smtp_gateway.smtp.server import create_smtp_server


class TestBasicSMTP:
    """Integration tests for basic SMTP server functionality."""

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
    async def test_smtp_connection_and_quit(self, smtp_server):
        """Test basic SMTP connection and QUIT command."""
        # Arrange
        smtp_host = "localhost"
        smtp_port = 587

        # Act & Assert
        with smtplib.SMTP(smtp_host, smtp_port) as client:
            # Connection successful
            code, msg = client.ehlo("test.example.com")
            assert code == 250
            assert b"smtp.cakemail.com" in msg

            # QUIT should succeed
            code, msg = client.quit()
            assert code == 221
            assert b"Bye" in msg

    @pytest.mark.asyncio
    async def test_smtp_ehlo_command(self, smtp_server):
        """Test EHLO command response."""
        # Arrange
        smtp_host = "localhost"
        smtp_port = 587

        # Act
        with smtplib.SMTP(smtp_host, smtp_port) as client:
            code, msg = client.ehlo("client.example.com")

            # Assert
            assert code == 250
            assert b"smtp.cakemail.com" in msg

    @pytest.mark.asyncio
    async def test_smtp_multiple_connections(self, smtp_server):
        """Test that server can handle multiple sequential connections."""
        # Arrange
        smtp_host = "localhost"
        smtp_port = 587

        # Act & Assert - Connect multiple times
        for i in range(3):
            with smtplib.SMTP(smtp_host, smtp_port) as client:
                code, msg = client.ehlo(f"client{i}.example.com")
                assert code == 250

    @pytest.mark.asyncio
    async def test_smtp_helo_command(self, smtp_server):
        """Test HELO command (older SMTP version) also works."""
        # Arrange
        smtp_host = "localhost"
        smtp_port = 587

        # Act
        with smtplib.SMTP(smtp_host, smtp_port) as client:
            code, msg = client.helo("client.example.com")

            # Assert
            assert code == 250
            # HELO response is simpler than EHLO
            assert b"smtp.cakemail.com" in msg
