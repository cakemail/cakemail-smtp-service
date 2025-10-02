"""Unit tests for SMTP handler."""

from unittest.mock import Mock

import pytest

from smtp_gateway.smtp.handler import SMTPHandler


class TestSMTPHandler:
    """Test suite for SMTPHandler class."""

    @pytest.fixture
    def handler(self):
        """Create an SMTPHandler instance for testing."""
        return SMTPHandler()

    @pytest.fixture
    def mock_session(self):
        """Create a mock SMTP session."""
        session = Mock()
        session.peer = ("127.0.0.1", 12345)
        session.host_name = None
        return session

    @pytest.fixture
    def mock_server(self):
        """Create a mock SMTP server."""
        return Mock()

    @pytest.fixture
    def mock_envelope(self):
        """Create a mock SMTP envelope."""
        return Mock()

    @pytest.mark.asyncio
    async def test_handle_ehlo_sets_hostname(self, handler, mock_server, mock_session, mock_envelope):
        """Test that EHLO command sets the session hostname."""
        # Arrange
        client_hostname = "client.example.com"
        responses = ["250-smtp.cakemail.com", "250 HELP"]

        # Act
        response = await handler.handle_EHLO(
            mock_server,
            mock_session,
            mock_envelope,
            client_hostname,
            responses,
        )

        # Assert
        assert mock_session.host_name == client_hostname
        assert response == responses

    @pytest.mark.asyncio
    async def test_handle_ehlo_returns_responses(self, handler, mock_server, mock_session, mock_envelope):
        """Test that EHLO command returns the responses list."""
        # Arrange
        responses = ["250-smtp.cakemail.com", "250 HELP"]

        # Act
        response = await handler.handle_EHLO(
            mock_server,
            mock_session,
            mock_envelope,
            "client.example.com",
            responses,
        )

        # Assert
        assert response == responses

    @pytest.mark.asyncio
    async def test_handle_quit_returns_bye(self, handler, mock_server, mock_session, mock_envelope):
        """Test that QUIT command returns proper response."""
        # Act
        response = await handler.handle_QUIT(
            mock_server,
            mock_session,
            mock_envelope,
        )

        # Assert
        assert response == "221 Bye"

    def test_connection_made_logs_peer(self, handler, mock_session):
        """Test that connection_made logs the peer address."""
        # Act
        handler.connection_made(mock_session)

        # Assert
        peer_address = mock_session.peer[0]
        assert peer_address in handler._connection_start_time

    def test_connection_lost_cleans_up(self, handler, mock_session):
        """Test that connection_lost removes tracking data."""
        # Arrange
        handler.connection_made(mock_session)
        peer_address = mock_session.peer[0]
        assert peer_address in handler._connection_start_time

        # Act
        handler.connection_lost(mock_session)

        # Assert
        assert peer_address not in handler._connection_start_time

    def test_connection_lost_with_error(self, handler, mock_session):
        """Test that connection_lost handles errors gracefully."""
        # Arrange
        handler.connection_made(mock_session)
        error = Exception("Test error")

        # Act - should not raise
        handler.connection_lost(mock_session, error)

        # Assert
        peer_address = mock_session.peer[0]
        assert peer_address not in handler._connection_start_time

    def test_connection_lost_without_prior_made(self, handler, mock_session):
        """Test that connection_lost handles missing session gracefully."""
        # Act - should not raise even if connection_made was never called
        handler.connection_lost(mock_session)

        # Assert - no exception raised is success
        assert True

    @pytest.mark.asyncio
    async def test_handle_data_not_implemented(self, handler, mock_server, mock_session, mock_envelope):
        """Test that DATA command returns not implemented for Story 1.2."""
        # Act
        response = await handler.handle_DATA(
            mock_server,
            mock_session,
            mock_envelope,
        )

        # Assert
        assert "500" in response
        assert "not implemented" in response.lower()
