"""Integration tests for SMTP authentication flow (Story 2.3)."""

import asyncio
import base64
import os
import smtplib
import ssl

import pytest
import respx
from httpx import Response

from smtp_gateway.smtp.server import create_smtp_server


@pytest.fixture
async def smtp_server_with_tls(tmp_path):
    """Create SMTP server with TLS for testing."""
    # Set environment variables for TLS certificates
    os.environ["TLS_CERT_PATH"] = str(tmp_path / "tls.crt")
    os.environ["TLS_KEY_PATH"] = str(tmp_path / "tls.key")
    os.environ["SMTP_PORT"] = "5870"  # Use different port for parallel tests

    # Clear settings cache to pick up new env vars
    from smtp_gateway.config import get_settings

    get_settings.cache_clear()

    # Create server
    server = await create_smtp_server()

    yield server

    # Cleanup
    server.stop()
    await asyncio.sleep(0.1)  # Allow cleanup
    get_settings.cache_clear()


@pytest.mark.integration
class TestSMTPAuthenticationFlow:
    """Integration tests for complete SMTP authentication flow."""

    @respx.mock
    async def test_full_auth_flow_success(self, smtp_server_with_tls):
        """Test complete flow: connection -> STARTTLS -> AUTH -> MAIL FROM."""
        # Mock successful authentication API response
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(200, json={"api_key": "test-api-key-12345"})
        )

        # Create SSL context that doesn't verify certificates (for self-signed cert)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Connect to SMTP server
        with smtplib.SMTP("localhost", 5870, timeout=5) as client:
            # Send EHLO
            code, msg = client.ehlo()
            assert code == 250

            # Start TLS
            client.starttls(context=context)

            # Send EHLO again after TLS
            code, msg = client.ehlo()
            assert code == 250

            # Authenticate with AUTH PLAIN
            username = "user@example.com"
            password = "password123"
            auth_string = f"\x00{username}\x00{password}"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()

            code, msg = client.docmd("AUTH", f"PLAIN {auth_b64}")
            assert code == 235
            assert b"Authentication successful" in msg

            # Send MAIL FROM (should succeed after auth)
            code, msg = client.mail("sender@example.com")
            assert code == 250

    @respx.mock
    async def test_auth_failure_invalid_credentials(self, smtp_server_with_tls):
        """Test authentication failure with invalid credentials."""
        # Mock authentication failure (401)
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(401, json={"error": "Invalid credentials"})
        )

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP("localhost", 5870, timeout=5) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()

            # Authenticate with wrong credentials
            auth_string = "\x00wronguser@example.com\x00wrongpass"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()

            code, msg = client.docmd("AUTH", f"PLAIN {auth_b64}")
            assert code == 535
            assert b"Authentication failed" in msg

    @respx.mock
    async def test_auth_temporary_failure_server_error(self, smtp_server_with_tls):
        """Test temporary authentication failure due to API server error."""
        # Mock server error (500)
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(500, json={"error": "Internal server error"})
        )

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP("localhost", 5870, timeout=10) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()

            # Authenticate - should get temporary failure
            auth_string = "\x00user@example.com\x00password123"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()

            code, msg = client.docmd("AUTH", f"PLAIN {auth_b64}")
            assert code == 451
            assert b"Temporary authentication failure" in msg

    @respx.mock
    async def test_mail_from_requires_authentication(self, smtp_server_with_tls):
        """Test that MAIL FROM is rejected without authentication (Story 2.3)."""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP("localhost", 5870, timeout=5) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()

            # MAIL FROM should be rejected without authentication
            # smtplib.mail() returns (code, msg), doesn't raise on non-2xx
            code, msg = client.mail("sender@example.com")
            assert code == 530
            assert b"Authentication required" in msg

    @respx.mock
    async def test_auth_caches_api_key_in_session(self, smtp_server_with_tls):
        """Test that API key is cached in session after successful auth."""
        # Mock successful authentication
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(200, json={"api_key": "cached-key-123"})
        )

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP("localhost", 5870, timeout=5) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()

            # Authenticate
            auth_string = "\x00user@example.com\x00password123"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()

            code, msg = client.docmd("AUTH", f"PLAIN {auth_b64}")
            assert code == 235

            # Verify API was called once
            assert len(respx.calls) == 1

            # MAIL FROM should work without additional API calls
            code, msg = client.mail("sender@example.com")
            assert code == 250

            # Verify no additional API calls were made
            assert len(respx.calls) == 1  # Still only 1 call

    @respx.mock
    async def test_auth_before_starttls_rejected(self, smtp_server_with_tls):
        """Test that AUTH is rejected before STARTTLS."""
        with smtplib.SMTP("localhost", 5870, timeout=5) as client:
            client.ehlo()

            # Try to authenticate before STARTTLS
            auth_string = "\x00user@example.com\x00password123"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()

            code, msg = client.docmd("AUTH", f"PLAIN {auth_b64}")
            # aiosmtpd returns 538 (encryption required for auth) which is acceptable
            # Our handler returns 530, but aiosmtpd may intercept first
            assert code in (530, 538)
            assert b"STARTTLS" in msg or b"encryption" in msg.lower()

    @respx.mock
    async def test_multiple_auth_attempts(self, smtp_server_with_tls):
        """Test multiple authentication attempts in same session."""
        # First attempt fails, second succeeds
        route = respx.post("https://api.cakemail.com/v1/auth/validate")
        route.side_effect = [
            Response(401, json={"error": "Invalid credentials"}),
            Response(200, json={"api_key": "retry-success-key"}),
        ]

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP("localhost", 5870, timeout=5) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()

            # First auth attempt (fails)
            auth_string = "\x00wrong@example.com\x00wrongpass"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()
            code, msg = client.docmd("AUTH", f"PLAIN {auth_b64}")
            assert code == 535

            # Second auth attempt (succeeds)
            auth_string2 = "\x00correct@example.com\x00correctpass"
            auth_b64_2 = base64.b64encode(auth_string2.encode()).decode()
            code, msg = client.docmd("AUTH", f"PLAIN {auth_b64_2}")
            assert code == 235

            # MAIL FROM should work after successful auth
            code, msg = client.mail("sender@example.com")
            assert code == 250
