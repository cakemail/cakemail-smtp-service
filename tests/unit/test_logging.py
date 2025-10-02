"""Unit tests for logging configuration."""

import pytest

from smtp_gateway.logging import setup_logging


@pytest.mark.unit
def test_setup_logging_info():
    """Test logging setup with INFO level."""
    setup_logging(log_level="INFO", log_format="console")
    # If no exception raised, test passes


@pytest.mark.unit
def test_setup_logging_debug():
    """Test logging setup with DEBUG level."""
    setup_logging(log_level="DEBUG", log_format="json")
    # If no exception raised, test passes
