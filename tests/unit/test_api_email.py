"""Unit tests for Cakemail Email API client."""

import pytest
import respx
from httpx import Response

from smtp_gateway.api.email import submit_email
from smtp_gateway.api.errors import (
    NetworkError,
    RateLimitError,
    ServerError,
    ValidationError,
)


@pytest.mark.unit
class TestSubmitEmail:
    """Tests for submit_email function (Story 2.5)."""

    @respx.mock
    async def test_submit_email_success(self):
        """Test successful email submission."""
        respx.post("https://api.cakemail.com/v1/email").mock(
            return_value=Response(
                200,
                json={"message_id": "msg-12345", "status": "queued"},
            )
        )

        email_data = {
            "from": "sender@example.com",
            "to": ["recipient@example.com"],  # Story 3.1: now a list
            "cc": [],
            "bcc": [],
            "subject": "Test Email",
            "body_text": "Email body content.",
        }

        result = await submit_email("test-api-key", email_data)

        assert result["message_id"] == "msg-12345"
        assert result["status"] == "accepted"
        assert result["recipients"]["succeeded"] == ["recipient@example.com"]
        assert result["recipients"]["failed"] == []

    @respx.mock
    async def test_submit_email_accepted_202(self):
        """Test email submission with 202 Accepted response."""
        respx.post("https://api.cakemail.com/v1/email").mock(
            return_value=Response(
                202,
                json={"id": "msg-67890"},  # Some APIs use 'id' instead of 'message_id'
            )
        )

        email_data = {
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "cc": [],
            "bcc": [],
            "subject": "Test",
            "body_text": "Content",
        }

        result = await submit_email("test-api-key", email_data)

        assert result["message_id"] == "msg-67890"

    @respx.mock
    async def test_submit_email_validation_error(self):
        """Test email validation error (400) - Story 3.1: all recipients fail."""
        respx.post("https://api.cakemail.com/v1/email").mock(
            return_value=Response(
                400,
                json={"error": "Invalid email address format"},
            )
        )

        email_data = {
            "from": "invalid-email",
            "to": ["recipient@example.com"],
            "cc": [],
            "bcc": [],
            "subject": "Test",
            "body_text": "Content",
        }

        with pytest.raises(ValidationError, match="All recipients failed"):
            await submit_email("test-api-key", email_data)

    @respx.mock
    async def test_submit_email_rate_limit(self):
        """Test rate limit error (429)."""
        respx.post("https://api.cakemail.com/v1/email").mock(
            return_value=Response(
                429,
                json={"error": "Rate limit exceeded"},
            )
        )

        email_data = {
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "cc": [],
            "bcc": [],
            "subject": "Test",
            "body_text": "Content",
        }

        with pytest.raises(RateLimitError, match="Rate limit exceeded"):
            await submit_email("test-api-key", email_data)

    @respx.mock
    async def test_submit_email_server_error(self):
        """Test server error (500) - Story 3.1: single recipient fails."""
        respx.post("https://api.cakemail.com/v1/email").mock(
            return_value=Response(
                500,
                json={"error": "Internal server error"},
            )
        )

        email_data = {
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "cc": [],
            "bcc": [],
            "subject": "Test",
            "body_text": "Content",
        }

        # Story 3.1: All recipients failed, raises ValidationError
        with pytest.raises(ValidationError, match="All recipients failed"):
            await submit_email("test-api-key", email_data)

    @respx.mock
    async def test_submit_email_network_error_retries(self):
        """Test network error triggers retry - Story 3.1: all recipients fail."""
        import httpx

        # Mock network error on both attempts
        respx.post("https://api.cakemail.com/v1/email").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        email_data = {
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "cc": [],
            "bcc": [],
            "subject": "Test",
            "body_text": "Content",
        }

        # Story 3.1: Network error after retry results in all recipients failed
        with pytest.raises(ValidationError, match="All recipients failed"):
            await submit_email("test-api-key", email_data)

        # Verify we made 2 attempts per recipient (initial + 1 retry)
        assert len(respx.calls) == 2

    @respx.mock
    async def test_submit_email_network_recovers_on_retry(self):
        """Test network error recovers on retry."""
        import httpx

        # First attempt fails, second succeeds
        route = respx.post("https://api.cakemail.com/v1/email")
        route.side_effect = [
            httpx.TimeoutException("Timeout"),
            Response(200, json={"message_id": "msg-retry-success"}),
        ]

        email_data = {
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "cc": [],
            "bcc": [],
            "subject": "Test",
            "body_text": "Content",
        }

        result = await submit_email("test-api-key", email_data)

        assert result["message_id"] == "msg-retry-success"
        assert result["recipients"]["succeeded"] == ["recipient@example.com"]
        assert len(respx.calls) == 2

    @respx.mock
    async def test_submit_email_missing_message_id(self):
        """Test response with 200 but missing message_id - Story 3.1: all fail."""
        respx.post("https://api.cakemail.com/v1/email").mock(
            return_value=Response(200, json={"status": "ok"})  # Missing message_id
        )

        email_data = {
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "cc": [],
            "bcc": [],
            "subject": "Test",
            "body_text": "Content",
        }

        # Story 3.1: Missing message_id causes recipient to fail
        with pytest.raises(ValidationError, match="All recipients failed"):
            await submit_email("test-api-key", email_data)

    @respx.mock
    async def test_submit_email_sends_correct_payload(self):
        """Test that correct payload is sent to API."""
        route = respx.post("https://api.cakemail.com/v1/email").mock(
            return_value=Response(200, json={"message_id": "msg-123"})
        )

        email_data = {
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "cc": [],
            "bcc": [],
            "subject": "Test Subject",
            "body_text": "Email body content",
        }

        await submit_email("test-api-key-123", email_data)

        # Verify request payload
        request = respx.calls.last.request
        assert request.method == "POST"
        assert request.headers["Authorization"] == "Bearer test-api-key-123"
        assert request.headers["Content-Type"] == "application/json"

        import json

        payload = json.loads(request.content)
        assert payload["from"]["email"] == "sender@example.com"
        assert payload["to"] == [{"email": "recipient@example.com"}]
        assert payload["subject"] == "Test Subject"
        assert payload["text"] == "Email body content"

    @respx.mock
    async def test_submit_email_unexpected_status_code(self):
        """Test unexpected status code (e.g., 404, 403) - Story 3.1: all fail."""
        respx.post("https://api.cakemail.com/v1/email").mock(
            return_value=Response(403, json={"error": "Forbidden"})
        )

        email_data = {
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "cc": [],
            "bcc": [],
            "subject": "Test",
            "body_text": "Content",
        }

        # Story 3.1: Unexpected error causes all recipients to fail
        with pytest.raises(ValidationError, match="All recipients failed"):
            await submit_email("test-api-key", email_data)

    @respx.mock
    async def test_submit_email_uses_configured_url(self, monkeypatch):
        """Test that configured API URL is used."""
        # Set custom API URL
        monkeypatch.setenv("CAKEMAIL_API_URL", "https://custom-api.example.com/v2")

        # Clear settings cache
        from smtp_gateway.config import get_settings

        get_settings.cache_clear()

        # Mock the custom URL
        respx.post("https://custom-api.example.com/v2/email").mock(
            return_value=Response(200, json={"message_id": "custom-msg"})
        )

        email_data = {
            "from": "sender@example.com",
            "to": ["recipient@example.com"],
            "cc": [],
            "bcc": [],
            "subject": "Test",
            "body_text": "Content",
        }

        result = await submit_email("test-api-key", email_data)

        assert result["message_id"] == "custom-msg"

        # Clean up
        get_settings.cache_clear()

    # Story 3.1: Multi-Recipient Tests

    @respx.mock
    async def test_submit_email_multiple_recipients_all_succeed(self):
        """Test submitting to multiple recipients with all successful (Story 3.1)."""
        # Mock all 3 API calls to succeed
        respx.post("https://api.cakemail.com/v1/email").mock(
            side_effect=[
                Response(200, json={"message_id": "msg-1"}),
                Response(200, json={"message_id": "msg-2"}),
                Response(200, json={"message_id": "msg-3"}),
            ]
        )

        email_data = {
            "from": "sender@example.com",
            "to": ["recipient1@example.com", "recipient2@example.com"],
            "cc": ["recipient3@example.com"],
            "bcc": [],
            "subject": "Multi-Recipient Test",
            "body_text": "Test body",
        }

        result = await submit_email("test-api-key", email_data)

        # Should have 3 message IDs (one per recipient)
        assert result["message_id"] == ["msg-1", "msg-2", "msg-3"]
        assert result["status"] == "accepted"
        assert result["recipients"]["succeeded"] == [
            "recipient1@example.com",
            "recipient2@example.com",
            "recipient3@example.com",
        ]
        assert result["recipients"]["failed"] == []

        # Verify 3 API calls were made
        assert len(respx.calls) == 3

    @respx.mock
    async def test_submit_email_multiple_recipients_partial_success(self):
        """Test multi-recipient with partial success (Story 3.1)."""
        # First succeeds, second fails validation, third succeeds
        respx.post("https://api.cakemail.com/v1/email").mock(
            side_effect=[
                Response(200, json={"message_id": "msg-1"}),
                Response(400, json={"error": "Invalid recipient"}),
                Response(200, json={"message_id": "msg-3"}),
            ]
        )

        email_data = {
            "from": "sender@example.com",
            "to": ["recipient1@example.com", "invalid@example.com", "recipient3@example.com"],
            "cc": [],
            "bcc": [],
            "subject": "Partial Success Test",
            "body_text": "Test body",
        }

        result = await submit_email("test-api-key", email_data)

        # Should succeed with 2/3 recipients
        assert result["message_id"] == ["msg-1", "msg-3"]
        assert result["status"] == "accepted"
        assert result["recipients"]["succeeded"] == ["recipient1@example.com", "recipient3@example.com"]
        assert len(result["recipients"]["failed"]) == 1
        assert result["recipients"]["failed"][0]["email"] == "invalid@example.com"
        assert "Invalid recipient" in result["recipients"]["failed"][0]["error"]

    @respx.mock
    async def test_submit_email_no_recipients(self):
        """Test submitting with no recipients raises error (Story 3.1)."""
        email_data = {
            "from": "sender@example.com",
            "to": [],
            "cc": [],
            "bcc": [],
            "subject": "No Recipients",
            "body_text": "Test body",
        }

        with pytest.raises(ValidationError, match="No recipients specified"):
            await submit_email("test-api-key", email_data)
