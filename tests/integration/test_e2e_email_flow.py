"""End-to-end integration tests for email forwarding (Story 2.6 & 3.1)."""

import asyncio
import base64
import os
import smtplib
import ssl
from email.mime.text import MIMEText

import pytest
import respx
from httpx import Response

from smtp_gateway.smtp.server import create_smtp_server


@pytest.fixture
async def smtp_server_e2e(tmp_path):
    """Create SMTP server for end-to-end testing."""
    os.environ["TLS_CERT_PATH"] = str(tmp_path / "tls.crt")
    os.environ["TLS_KEY_PATH"] = str(tmp_path / "tls.key")
    os.environ["SMTP_PORT"] = "5871"  # Use different port

    from smtp_gateway.config import get_settings

    get_settings.cache_clear()

    server = await create_smtp_server()
    yield server

    server.stop()
    await asyncio.sleep(0.1)
    get_settings.cache_clear()


@pytest.mark.integration
class TestEndToEndEmailFlow:
    """End-to-end tests for complete email forwarding flow (Story 2.6)."""

    @respx.mock
    async def test_complete_email_flow_success(self, smtp_server_e2e):
        """Test complete SMTP session with successful API submission."""
        # Mock auth API
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(200, json={"api_key": "test-api-key-e2e"})
        )

        # Mock email API
        respx.post("https://api.cakemail.com/v1/email").mock(
            return_value=Response(200, json={"message_id": "msg-e2e-12345"})
        )

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        # Send complete email via SMTP
        with smtplib.SMTP("localhost", 5871, timeout=10) as client:
            client.set_debuglevel(0)

            # EHLO
            code, msg = client.ehlo()
            assert code == 250

            # STARTTLS
            client.starttls(context=context)

            # EHLO after TLS
            code, msg = client.ehlo()
            assert code == 250

            # Authenticate
            username = "user@example.com"
            password = "password123"
            auth_string = f"\x00{username}\x00{password}"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()

            code, msg = client.docmd("AUTH", f"PLAIN {auth_b64}")
            assert code == 235

            # MAIL FROM
            code, msg = client.mail("sender@example.com")
            assert code == 250

            # RCPT TO
            code, msg = client.rcpt("recipient@example.com")
            assert code == 250

            # DATA - send email
            msg = MIMEText("This is a test email body.")
            msg["From"] = "sender@example.com"
            msg["To"] = "recipient@example.com"
            msg["Subject"] = "Test Email"

            code, response = client.data(msg.as_bytes())
            assert code == 250
            assert b"msg-e2e-12345" in response  # Message ID in response

            # QUIT
            code, msg = client.quit()
            assert code == 221

        # Verify API calls were made
        assert len(respx.calls) == 2  # Auth + Email submission

    @respx.mock
    async def test_email_flow_validation_error(self, smtp_server_e2e):
        """Test email rejected with 550 on API validation error."""
        # Mock auth API
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(200, json={"api_key": "test-api-key"})
        )

        # Mock email API validation error
        respx.post("https://api.cakemail.com/v1/email").mock(
            return_value=Response(400, json={"error": "Invalid recipient email"})
        )

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP("localhost", 5871, timeout=10) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()

            # Authenticate
            auth_string = "\x00user@example.com\x00password"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()
            client.docmd("AUTH", f"PLAIN {auth_b64}")

            client.mail("sender@example.com")
            client.rcpt("invalid@example.com")

            # DATA - should fail with 550
            msg = MIMEText("Test body")
            msg["From"] = "sender@example.com"
            msg["To"] = "invalid@example.com"
            msg["Subject"] = "Test"

            code, response = client.data(msg.as_bytes())
            assert code == 550
            assert b"Message rejected" in response

    @respx.mock
    async def test_email_flow_rate_limit(self, smtp_server_e2e):
        """Test email rejected with 451 on rate limit."""
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(200, json={"api_key": "test-api-key"})
        )

        # Mock rate limit
        respx.post("https://api.cakemail.com/v1/email").mock(
            return_value=Response(429, json={"error": "Rate limit exceeded"})
        )

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP("localhost", 5871, timeout=10) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()

            auth_string = "\x00user@example.com\x00password"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()
            client.docmd("AUTH", f"PLAIN {auth_b64}")

            client.mail("sender@example.com")
            client.rcpt("recipient@example.com")

            msg = MIMEText("Test body")
            msg["From"] = "sender@example.com"
            msg["To"] = "recipient@example.com"
            msg["Subject"] = "Test"

            code, response = client.data(msg.as_bytes())
            assert code == 451
            assert b"Rate limit" in response

    @respx.mock
    async def test_email_flow_api_server_error(self, smtp_server_e2e):
        """Test email rejected with 550 when all recipients fail due to server error (Story 3.1)."""
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(200, json={"api_key": "test-api-key"})
        )

        # Mock server error
        respx.post("https://api.cakemail.com/v1/email").mock(
            return_value=Response(500, json={"error": "Internal server error"})
        )

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP("localhost", 5871, timeout=10) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()

            auth_string = "\x00user@example.com\x00password"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()
            client.docmd("AUTH", f"PLAIN {auth_b64}")

            client.mail("sender@example.com")
            client.rcpt("recipient@example.com")

            msg = MIMEText("Test body")
            msg["From"] = "sender@example.com"
            msg["To"] = "recipient@example.com"
            msg["Subject"] = "Test"

            code, response = client.data(msg.as_bytes())
            # Story 3.1: All recipients failed due to server error -> 550
            assert code == 550
            assert b"Message rejected" in response

    @respx.mock
    async def test_email_flow_network_error(self, smtp_server_e2e):
        """Test email rejected with 550 when all recipients fail due to network error (Story 3.1)."""
        import httpx

        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(200, json={"api_key": "test-api-key"})
        )

        # Mock network error
        respx.post("https://api.cakemail.com/v1/email").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP("localhost", 5871, timeout=15) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()

            auth_string = "\x00user@example.com\x00password"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()
            client.docmd("AUTH", f"PLAIN {auth_b64}")

            client.mail("sender@example.com")
            client.rcpt("recipient@example.com")

            msg = MIMEText("Test body")
            msg["From"] = "sender@example.com"
            msg["To"] = "recipient@example.com"
            msg["Subject"] = "Test"

            code, response = client.data(msg.as_bytes())
            # Story 3.1: All recipients failed due to network error -> 550
            assert code == 550
            assert b"Message rejected" in response

    @respx.mock
    async def test_email_with_utf8_content(self, smtp_server_e2e):
        """Test sending email with UTF-8 content."""
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(200, json={"api_key": "test-api-key"})
        )

        respx.post("https://api.cakemail.com/v1/email").mock(
            return_value=Response(200, json={"message_id": "msg-utf8"})
        )

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP("localhost", 5871, timeout=10) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()

            auth_string = "\x00user@example.com\x00password"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()
            client.docmd("AUTH", f"PLAIN {auth_b64}")

            client.mail("sender@example.com")
            client.rcpt("recipient@example.com")

            # Create email with UTF-8 content
            msg = MIMEText("Hello 世界! 🌍", _charset="utf-8")
            msg["From"] = "sender@example.com"
            msg["To"] = "recipient@example.com"
            msg["Subject"] = "UTF-8 Test"

            code, response = client.data(msg.as_bytes())
            assert code == 250
            assert b"msg-utf8" in response

    @respx.mock
    async def test_email_with_multiple_recipients(self, smtp_server_e2e):
        """Test sending email to 3 recipients (Story 3.1)."""
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(200, json={"api_key": "test-api-key"})
        )

        # Mock 3 successful API submissions (one per recipient)
        respx.post("https://api.cakemail.com/v1/email").mock(
            side_effect=[
                Response(200, json={"message_id": "msg-1"}),
                Response(200, json={"message_id": "msg-2"}),
                Response(200, json={"message_id": "msg-3"}),
            ]
        )

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP("localhost", 5871, timeout=10) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()

            # Authenticate
            auth_string = "\x00user@example.com\x00password"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()
            client.docmd("AUTH", f"PLAIN {auth_b64}")

            client.mail("sender@example.com")

            # Story 3.1: Add 3 recipients
            client.rcpt("recipient1@example.com")
            client.rcpt("recipient2@example.com")
            client.rcpt("recipient3@example.com")

            # Create email with 3 recipients
            msg = MIMEText("Test email to multiple recipients")
            msg["From"] = "sender@example.com"
            msg["To"] = "recipient1@example.com, recipient2@example.com"
            msg["Cc"] = "recipient3@example.com"
            msg["Subject"] = "Multi-Recipient Test"

            code, response = client.data(msg.as_bytes())
            assert code == 250
            # Response should contain message IDs (Story 3.1 returns list)
            assert b"Message accepted" in response

        # Verify 3 API calls were made (one per recipient)
        # First call is auth, next 3 are email submissions
        assert len(respx.calls) == 4

    @respx.mock
    async def test_email_with_html_content(self, smtp_server_e2e):
        """Test sending HTML email (Story 3.2)."""
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText as MIMETextPart

        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(200, json={"api_key": "test-api-key"})
        )

        # Mock API submission
        respx.post("https://api.cakemail.com/v1/email").mock(
            return_value=Response(200, json={"message_id": "msg-html"})
        )

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP("localhost", 5871, timeout=10) as client:
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()

            # Authenticate
            auth_string = "\x00user@example.com\x00password"
            auth_b64 = base64.b64encode(auth_string.encode()).decode()
            client.docmd("AUTH", f"PLAIN {auth_b64}")

            client.mail("sender@example.com")
            client.rcpt("recipient@example.com")

            # Create multipart/alternative email with both text and HTML
            msg = MIMEMultipart("alternative")
            msg["From"] = "sender@example.com"
            msg["To"] = "recipient@example.com"
            msg["Subject"] = "HTML Email Test"

            # Add plain text part
            text_part = MIMETextPart("This is the plain text version.", "plain")
            msg.attach(text_part)

            # Add HTML part
            html_part = MIMETextPart(
                "<html><body><h1>Hello</h1><p>This is <b>HTML</b> content.</p></body></html>",
                "html",
            )
            msg.attach(html_part)

            code, response = client.data(msg.as_bytes())
            assert code == 250
            assert b"msg-html" in response

        # Verify API was called with HTML content
        assert len(respx.calls) == 2  # Auth + email
        email_request = respx.calls[1].request
        import json

        payload = json.loads(email_request.content)
        # Story 3.2: Should include both text and html fields
        assert "text" in payload
        assert "html" in payload
        assert "plain text version" in payload["text"]
        assert "<b>HTML</b>" in payload["html"]
