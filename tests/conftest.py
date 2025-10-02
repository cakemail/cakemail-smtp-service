"""Pytest configuration and shared fixtures."""

import pytest


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    from smtp_gateway.config import Settings

    return Settings(
        cakemail_api_url="https://api.test.cakemail.com/v1",
        cakemail_auth_url="https://api.test.cakemail.com/v1/auth",
        smtp_host="127.0.0.1",
        smtp_port=8587,
        tls_cert_path="/tmp/cert.pem",
        tls_key_path="/tmp/key.pem",
        http_host="127.0.0.1",
        http_port=8888,
        log_level="DEBUG",
    )


@pytest.fixture
def sample_email():
    """Sample email message for testing."""
    return {
        "from": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Test Email",
        "body_text": "This is a test email.",
        "body_html": "<p>This is a test email.</p>",
    }
