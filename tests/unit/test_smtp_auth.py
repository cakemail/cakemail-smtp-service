"""Unit tests for SMTP authentication."""

import base64

import pytest

from smtp_gateway.smtp.auth import (
    encode_auth_challenge,
    parse_auth_login_password,
    parse_auth_login_username,
    parse_auth_plain,
)


class TestAuthPlain:
    """Tests for AUTH PLAIN parsing."""

    def test_parse_auth_plain_valid(self):
        """Test parsing valid AUTH PLAIN credentials."""
        # Create AUTH PLAIN string: \x00username\x00password
        auth_data = "\x00user@example.com\x00secret123"
        auth_string = base64.b64encode(auth_data.encode("utf-8")).decode("ascii")

        username, password = parse_auth_plain(auth_string)

        assert username == "user@example.com"
        assert password == "secret123"

    def test_parse_auth_plain_with_authorization_id(self):
        """Test AUTH PLAIN with non-empty authorization ID."""
        # Authorization ID (first part) is usually empty but can be set
        auth_data = "authz\x00user@example.com\x00secret123"
        auth_string = base64.b64encode(auth_data.encode("utf-8")).decode("ascii")

        username, password = parse_auth_plain(auth_string)

        # Authorization ID is ignored, we use username
        assert username == "user@example.com"
        assert password == "secret123"

    def test_parse_auth_plain_invalid_base64(self):
        """Test parsing invalid base64 string."""
        with pytest.raises(ValueError, match="Invalid base64"):
            parse_auth_plain("not-valid-base64!!!")

    def test_parse_auth_plain_wrong_format(self):
        """Test AUTH PLAIN with wrong format (missing parts)."""
        # Only 2 parts instead of 3
        auth_data = "username\x00password"
        auth_string = base64.b64encode(auth_data.encode("utf-8")).decode("ascii")

        with pytest.raises(ValueError, match="expected 3 parts"):
            parse_auth_plain(auth_string)

    def test_parse_auth_plain_empty_username(self):
        """Test AUTH PLAIN with empty username."""
        auth_data = "\x00\x00password"
        auth_string = base64.b64encode(auth_data.encode("utf-8")).decode("ascii")

        with pytest.raises(ValueError, match="cannot be empty"):
            parse_auth_plain(auth_string)

    def test_parse_auth_plain_empty_password(self):
        """Test AUTH PLAIN with empty password."""
        auth_data = "\x00username\x00"
        auth_string = base64.b64encode(auth_data.encode("utf-8")).decode("ascii")

        with pytest.raises(ValueError, match="cannot be empty"):
            parse_auth_plain(auth_string)


class TestAuthLogin:
    """Tests for AUTH LOGIN parsing."""

    def test_parse_auth_login_username_valid(self):
        """Test parsing valid AUTH LOGIN username."""
        username_b64 = base64.b64encode(b"user@example.com").decode("ascii")
        username = parse_auth_login_username(username_b64)
        assert username == "user@example.com"

    def test_parse_auth_login_username_invalid_base64(self):
        """Test parsing invalid base64 username."""
        with pytest.raises(ValueError, match="Invalid base64"):
            parse_auth_login_username("not-valid-base64!!!")

    def test_parse_auth_login_username_empty(self):
        """Test parsing empty username."""
        empty_b64 = base64.b64encode(b"").decode("ascii")
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_auth_login_username(empty_b64)

    def test_parse_auth_login_password_valid(self):
        """Test parsing valid AUTH LOGIN password."""
        password_b64 = base64.b64encode(b"secret123").decode("ascii")
        password = parse_auth_login_password(password_b64)
        assert password == "secret123"

    def test_parse_auth_login_password_invalid_base64(self):
        """Test parsing invalid base64 password."""
        with pytest.raises(ValueError, match="Invalid base64"):
            parse_auth_login_password("not-valid-base64!!!")

    def test_parse_auth_login_password_empty(self):
        """Test parsing empty password."""
        empty_b64 = base64.b64encode(b"").decode("ascii")
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_auth_login_password(empty_b64)


class TestAuthChallenges:
    """Tests for AUTH challenge encoding."""

    def test_encode_auth_challenge(self):
        """Test encoding AUTH challenges."""
        challenge = encode_auth_challenge("Username:")
        decoded = base64.b64decode(challenge).decode("utf-8")
        assert decoded == "Username:"

    def test_encode_auth_challenge_password(self):
        """Test encoding password challenge."""
        challenge = encode_auth_challenge("Password:")
        decoded = base64.b64decode(challenge).decode("utf-8")
        assert decoded == "Password:"
