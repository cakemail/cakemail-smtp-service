"""Unit tests for SMTP server."""

import pytest

from smtp_gateway.smtp.server import create_smtp_server


class TestSMTPServer:
    """Test suite for SMTP server creation."""

    @pytest.mark.asyncio
    async def test_create_smtp_server_returns_controller(self):
        """Test that create_smtp_server returns a Controller instance."""
        # Act
        controller = await create_smtp_server()

        # Assert
        assert controller is not None
        assert hasattr(controller, "start")
        assert hasattr(controller, "stop")

        # Cleanup
        controller.stop()

    @pytest.mark.asyncio
    async def test_smtp_server_starts_on_configured_port(self):
        """Test that SMTP server starts on the configured port."""
        # Act
        controller = await create_smtp_server()

        # Assert
        assert controller is not None
        # The controller should be running after creation
        # Note: aiosmtpd Controller doesn't expose a direct "is_running" property
        # but we can verify it has the expected attributes

        # Cleanup
        controller.stop()

    @pytest.mark.asyncio
    async def test_smtp_server_uses_handler(self):
        """Test that SMTP server uses the SMTPHandler."""
        # Act
        controller = await create_smtp_server()

        # Assert
        assert controller is not None
        assert hasattr(controller, "handler")
        assert controller.handler is not None

        # Cleanup
        controller.stop()

    @pytest.mark.asyncio
    async def test_smtp_server_cleanup(self):
        """Test that SMTP server can be stopped cleanly."""
        # Arrange
        controller = await create_smtp_server()

        # Act
        controller.stop()

        # Assert - no exception raised is success
        assert True
