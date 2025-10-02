"""Unit tests for metrics."""

import pytest

from smtp_gateway import metrics


@pytest.mark.unit
def test_metrics_defined():
    """Test that all metrics are properly defined."""
    assert hasattr(metrics, "smtp_connections_total")
    assert hasattr(metrics, "smtp_emails_received_total")
    assert hasattr(metrics, "smtp_emails_forwarded_total")
    assert hasattr(metrics, "smtp_auth_failures_total")
    assert hasattr(metrics, "smtp_api_errors_total")
    assert hasattr(metrics, "smtp_processing_duration_seconds")
    assert hasattr(metrics, "smtp_api_latency_seconds")
    assert hasattr(metrics, "smtp_connection_duration_seconds")
    assert hasattr(metrics, "smtp_active_connections")
    assert hasattr(metrics, "smtp_api_key_cache_size")
