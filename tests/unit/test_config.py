"""Unit tests for configuration."""

import pytest

from smtp_gateway.config import Settings


@pytest.mark.unit
def test_settings_defaults():
    """Test default settings values."""
    settings = Settings()

    assert settings.smtp_port == 587
    assert settings.http_port == 8080
    assert settings.log_level == "INFO"
    assert settings.rate_limit_per_ip == 100
    assert settings.max_connections_per_pod == 1000


@pytest.mark.unit
def test_settings_override():
    """Test settings can be overridden."""
    settings = Settings(
        smtp_port=2525,
        log_level="DEBUG",
    )

    assert settings.smtp_port == 2525
    assert settings.log_level == "DEBUG"
