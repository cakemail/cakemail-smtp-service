"""Unit tests for Cakemail Authentication API client."""

import pytest
import respx
from httpx import Response

from smtp_gateway.api.auth import validate_credentials
from smtp_gateway.api.errors import (
    AuthenticationError,
    NetworkError,
    ServerError,
)


@pytest.mark.unit
class TestValidateCredentials:
    """Tests for validate_credentials function."""

    @respx.mock
    async def test_validate_credentials_success(self):
        """Test successful credential validation."""
        # Mock successful API response
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(
                200,
                json={"api_key": "test-api-key-12345"},
            )
        )

        api_key = await validate_credentials("user@example.com", "password123")

        assert api_key == "test-api-key-12345"

    @respx.mock
    async def test_validate_credentials_auth_failure_401(self):
        """Test authentication failure with 401 status."""
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(401, json={"error": "Invalid credentials"})
        )

        with pytest.raises(AuthenticationError, match="Invalid credentials"):
            await validate_credentials("user@example.com", "wrongpassword")

    @respx.mock
    async def test_validate_credentials_auth_failure_403(self):
        """Test authentication failure with 403 status."""
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(403, json={"error": "Forbidden"})
        )

        with pytest.raises(AuthenticationError, match="Invalid credentials"):
            await validate_credentials("user@example.com", "wrongpassword")

    @respx.mock
    async def test_validate_credentials_server_error_retries(self):
        """Test server error triggers retries and eventually fails."""
        # Mock 3 consecutive 500 errors (initial + 2 retries)
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(500, json={"error": "Internal server error"})
        )

        with pytest.raises(ServerError, match="API server error: 500"):
            await validate_credentials("user@example.com", "password123")

        # Verify we made 3 attempts (initial + 2 retries)
        calls = respx.calls
        assert len(calls) == 3

    @respx.mock
    async def test_validate_credentials_server_error_recovers(self):
        """Test server error retries and succeeds on retry."""
        # First two attempts fail, third succeeds
        route = respx.post("https://api.cakemail.com/v1/auth/validate")
        route.side_effect = [
            Response(500, json={"error": "Server error"}),
            Response(500, json={"error": "Server error"}),
            Response(200, json={"api_key": "test-api-key-recovered"}),
        ]

        api_key = await validate_credentials("user@example.com", "password123")

        assert api_key == "test-api-key-recovered"
        assert len(respx.calls) == 3

    @respx.mock
    async def test_validate_credentials_timeout(self):
        """Test timeout error triggers retries."""
        import httpx

        # Mock timeout on all attempts
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            side_effect=httpx.TimeoutException("Request timeout")
        )

        with pytest.raises(NetworkError, match="API request timeout"):
            await validate_credentials("user@example.com", "password123")

        # Verify we made 3 attempts (initial + 2 retries)
        assert len(respx.calls) == 3

    @respx.mock
    async def test_validate_credentials_network_error(self):
        """Test network error triggers retries."""
        import httpx

        # Mock network error on all attempts
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(NetworkError, match="Network error"):
            await validate_credentials("user@example.com", "password123")

        # Verify we made 3 attempts (initial + 2 retries)
        assert len(respx.calls) == 3

    @respx.mock
    async def test_validate_credentials_missing_api_key(self):
        """Test response with 200 but missing api_key field."""
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(200, json={"success": True})  # Missing api_key
        )

        with pytest.raises(ServerError, match="missing api_key"):
            await validate_credentials("user@example.com", "password123")

    @respx.mock
    async def test_validate_credentials_unexpected_status_code(self):
        """Test unexpected status code (e.g., 400, 404)."""
        respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(400, json={"error": "Bad request"})
        )

        with pytest.raises(ServerError, match="Unexpected API response: 400"):
            await validate_credentials("user@example.com", "password123")

    @respx.mock
    async def test_validate_credentials_network_recovers_on_retry(self):
        """Test network error recovers on retry."""
        import httpx

        # First attempt times out, second succeeds
        route = respx.post("https://api.cakemail.com/v1/auth/validate")
        route.side_effect = [
            httpx.TimeoutException("Timeout"),
            Response(200, json={"api_key": "test-api-key-retry"}),
        ]

        api_key = await validate_credentials("user@example.com", "password123")

        assert api_key == "test-api-key-retry"
        assert len(respx.calls) == 2

    @respx.mock
    async def test_validate_credentials_sends_correct_payload(self):
        """Test that correct username and password are sent to API."""
        route = respx.post("https://api.cakemail.com/v1/auth/validate").mock(
            return_value=Response(200, json={"api_key": "test-key"})
        )

        await validate_credentials("test@example.com", "secret123")

        # Verify request payload
        request = respx.calls.last.request
        assert request.method == "POST"
        assert request.headers["Content-Type"] == "application/json"

        import json

        payload = json.loads(request.content)
        assert payload == {"username": "test@example.com", "password": "secret123"}

    @respx.mock
    async def test_validate_credentials_uses_configured_url(self, monkeypatch):
        """Test that configured auth URL is used."""
        import os

        # Set custom auth URL
        monkeypatch.setenv("CAKEMAIL_AUTH_URL", "https://custom-api.example.com/auth")

        # Clear settings cache to pick up new env var
        from smtp_gateway.config import get_settings

        get_settings.cache_clear()

        # Mock the custom URL
        respx.post("https://custom-api.example.com/auth/validate").mock(
            return_value=Response(200, json={"api_key": "custom-key"})
        )

        api_key = await validate_credentials("user@example.com", "password")

        assert api_key == "custom-key"

        # Clean up
        get_settings.cache_clear()
