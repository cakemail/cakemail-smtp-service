"""SMTP authentication handlers."""

import base64
from typing import Tuple

import structlog


logger = structlog.get_logger()


def parse_auth_plain(auth_string: str) -> Tuple[str, str]:
    """Parse AUTH PLAIN credentials.

    AUTH PLAIN format: base64(\\x00username\\x00password)

    Args:
        auth_string: Base64-encoded authentication string

    Returns:
        Tuple of (username, password)

    Raises:
        ValueError: If auth_string is invalid or malformed
    """
    try:
        # Decode base64
        decoded = base64.b64decode(auth_string).decode("utf-8")

        # AUTH PLAIN format: \x00username\x00password
        parts = decoded.split("\x00")

        # Should have 3 parts: [authorization_id, username, password]
        # We ignore authorization_id (first part, often empty)
        if len(parts) != 3:
            raise ValueError(f"Invalid AUTH PLAIN format: expected 3 parts, got {len(parts)}")

        _, username, password = parts

        if not username or not password:
            raise ValueError("Username and password cannot be empty")

        logger.debug("AUTH PLAIN parsed successfully", username=username)
        return username, password

    except (base64.binascii.Error, UnicodeDecodeError) as e:
        logger.warning("Failed to decode AUTH PLAIN", error=str(e))
        raise ValueError(f"Invalid base64 encoding: {e}")


def parse_auth_login_username(username_b64: str) -> str:
    """Parse AUTH LOGIN username (base64-encoded).

    Args:
        username_b64: Base64-encoded username

    Returns:
        Decoded username string

    Raises:
        ValueError: If username_b64 is invalid
    """
    try:
        username = base64.b64decode(username_b64).decode("utf-8")
        if not username:
            raise ValueError("Username cannot be empty")
        logger.debug("AUTH LOGIN username parsed", username=username)
        return username
    except (base64.binascii.Error, UnicodeDecodeError) as e:
        logger.warning("Failed to decode AUTH LOGIN username", error=str(e))
        raise ValueError(f"Invalid base64 encoding: {e}")


def parse_auth_login_password(password_b64: str) -> str:
    """Parse AUTH LOGIN password (base64-encoded).

    Args:
        password_b64: Base64-encoded password

    Returns:
        Decoded password string

    Raises:
        ValueError: If password_b64 is invalid
    """
    try:
        password = base64.b64decode(password_b64).decode("utf-8")
        if not password:
            raise ValueError("Password cannot be empty")
        logger.debug("AUTH LOGIN password parsed")
        return password
    except (base64.binascii.Error, UnicodeDecodeError) as e:
        logger.warning("Failed to decode AUTH LOGIN password", error=str(e))
        raise ValueError(f"Invalid base64 encoding: {e}")


def encode_auth_challenge(prompt: str) -> str:
    """Encode an AUTH challenge prompt in base64.

    Args:
        prompt: Plain text prompt (e.g., "Username:", "Password:")

    Returns:
        Base64-encoded prompt
    """
    return base64.b64encode(prompt.encode("utf-8")).decode("ascii")
